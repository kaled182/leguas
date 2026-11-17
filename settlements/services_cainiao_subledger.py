"""Sub-ledger Cainiao (portal CES): importação, pré-fatura e conferências.

O CSV vem de "Download Sub-Ledger" em b.eu.cainiao.com/finance/bill.
Cada linha é uma guia (LP) e uma rubrica. Os valores já incluem IVA.
"""
import csv
import hashlib
import io
from collections import Counter, defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count, Max, Min, Q, Sum
from django.utils import timezone

from .models import (
    CainiaoBill, CainiaoBillCharge, CainiaoClientPreInvoice,
    CainiaoSubledgerImport,
)

VAT = Decimal("0.23")
CENT = Decimal("0.01")

# Rubrica Cainiao → (código, código do documento, descrição no documento,
# documento, IVA). Os textos seguem a folha que a equipa usava.
ITEMS = {
    "末端配送费": (CainiaoBillCharge.ITEM_LASTMILE, "001",
              "Serviço de Distribuição — entrega last-mile", "FATURA", VAT),
    "挂号服务费": (CainiaoBillCharge.ITEM_ENVIO, "002",
              "Serviço de Distribuição — envio registado", "FATURA", VAT),
    "逆向揽配揽收费": (CainiaoBillCharge.ITEM_REVERSE, "003",
                "Recolha reversa", "FATURA", VAT),
    "卡班运输费": (CainiaoBillCharge.ITEM_LINEHAUL, "004",
              "Transporte de linha", "FATURA", VAT),
    "APP使用费": (CainiaoBillCharge.ITEM_APP_FEE, "COMP", "app fee", "NC", VAT),
    "货值赔付": (CainiaoBillCharge.ITEM_COMPENSATION, "COMP",
             "compensacion (claims)", "NC", Decimal("0")),
}
BY_CODE = {v[0]: (raw, *v[1:]) for raw, v in ITEMS.items()}

COLUMNS = {
    "settlement": 1,  # o 2.º "Settlement ID" é único por linha
    "billing_time": 2, "item": 3, "business_time": 4, "amount": 6,
    "lp": 9, "employee": 11, "weight": 12, "first_order": 13,
    "postal_code": 14, "formula": 15, "claim": 18, "bill_id": 19,
}
EXPECTED_HEADER = ("Settlement ID", "Bill Item", "Bill Amount", "The bill ID")


class SubledgerError(ValueError):
    pass


def _clean(value):
    return (value or "").strip().lstrip("'").strip()


def _dt(value):
    value = _clean(value)
    if not value:
        return None
    return timezone.make_aware(datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S"))


def parse_subledger(raw):
    """Lê o CSV e devolve uma lista de dicionários, um por linha."""
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, [])
    if not all(h in header for h in EXPECTED_HEADER) or len(header) < 20:
        raise SubledgerError(
            "O ficheiro não é um sub-ledger do portal CES "
            "(faltam as colunas Settlement ID, Bill Item, Bill Amount ou The bill ID)."
        )
    rows = []
    for n, r in enumerate(reader, start=2):
        if not r or not any(r):
            continue
        c = {k: _clean(r[i]) if i < len(r) else "" for k, i in COLUMNS.items()}
        try:
            amount = Decimal(c["amount"])
        except Exception as e:
            raise SubledgerError(f"Linha {n}: valor inválido '{c['amount']}'.") from e
        item = ITEMS.get(c["item"], (CainiaoBillCharge.ITEM_OTHER,))[0]
        weight = c["weight"].split(".")[0]
        rows.append({
            "settlement_id": c["settlement"],
            "bill_id": c["bill_id"],
            "item": item,
            "item_raw": c["item"][:60],
            "business_at": _dt(c["business_time"]),
            "billing_at": _dt(c["billing_time"]),
            "amount": amount,
            "lp_number": c["lp"][:60],
            "employee_id": c["employee"][:40],
            "weight_g": int(weight) if weight.isdigit() else None,
            "first_order": c["first_order"][:1],
            "postal_code": c["postal_code"][:10],
            "formula": c["formula"][:200],
            "claim_comment": c["claim"][:300],
        })
    if not rows:
        raise SubledgerError("O ficheiro não tem linhas.")
    return rows


def refresh_bill_totals(bills):
    for bill in bills:
        agg = bill.charges.aggregate(
            n=Count("id"), total=Sum("amount"), first=Min("business_at"),
            last=Max("business_at"), billed=Max("billing_at"),
        )
        main = (
            bill.charges.values("item").annotate(n=Count("id"))
            .order_by("-n").values_list("item", flat=True).first()
        )
        bill.n_lines = agg["n"] or 0
        bill.total_amount = agg["total"] or Decimal("0")
        bill.first_business_at = agg["first"]
        bill.last_business_at = agg["last"]
        bill.last_billing_at = agg["billed"]
        bill.main_item = main or ""
        bill.save()


def import_subledger(uploaded, user):
    """Grava as linhas novas. Devolve (import, n_novas, n_repetidas, faturas)."""
    raw = uploaded.read()
    rows = parse_subledger(raw)
    file_hash = hashlib.sha256(raw).hexdigest()
    existing = set(
        CainiaoBillCharge.objects.filter(
            settlement_id__in=[r["settlement_id"] for r in rows],
        ).values_list("settlement_id", flat=True)
    )
    new_rows = [r for r in rows if r["settlement_id"] not in existing]
    with transaction.atomic():
        imp = CainiaoSubledgerImport.objects.create(
            file_name=(uploaded.name or "")[:255],
            file_hash=file_hash,
            n_lines=len(rows),
            n_new=len(new_rows),
            total_amount=sum((r["amount"] for r in rows), Decimal("0")),
            imported_by=user if getattr(user, "is_authenticated", False) else None,
        )
        bills = {}
        for bill_id in {r["bill_id"] for r in rows}:
            bills[bill_id], _ = CainiaoBill.objects.get_or_create(bill_id=bill_id)
        CainiaoBillCharge.objects.bulk_create(
            [
                CainiaoBillCharge(
                    bill=bills[r["bill_id"]], source=imp,
                    **{k: v for k, v in r.items() if k != "bill_id"},
                )
                for r in new_rows
            ],
            batch_size=2000,
        )
        refresh_bill_totals(bills.values())
    return imp, len(new_rows), len(rows) - len(new_rows), list(bills.values())


# ─── Pré-fatura à ESDP ─────────────────────────────────────────────────────────

def _money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def charges_for(pre_invoice):
    return CainiaoBillCharge.objects.filter(bill__pre_invoice=pre_invoice)


def documents(charges):
    """Fatura e nota de crédito, como na folha "Faturacao"."""
    sums = {
        row["item"]: (row["n"], row["total"])
        for row in charges.values("item").annotate(n=Count("id"), total=Sum("amount"))
    }
    invoice, credit = [], []
    for code, (raw, doc_code, label, doc, vat) in BY_CODE.items():
        n, gross = sums.get(code, (0, Decimal("0")))
        if doc == "FATURA":
            base = _money(gross / (1 + vat))
            invoice.append({"code": doc_code, "label": label, "qty": n, "base": base,
                            "vat_rate": vat, "vat": _money(gross) - base,
                            "gross": _money(gross), "raw": raw})
        else:
            gross = -gross
            base = _money(gross / (1 + vat))
            credit.append({"code": doc_code, "label": label, "qty": n, "base": base,
                           "vat_rate": vat, "vat": _money(gross) - base,
                           "gross": _money(gross), "raw": raw})

    def total(lines):
        return {k: sum((l[k] for l in lines), Decimal("0")) if k != "qty"
                else sum(l["qty"] for l in lines) for k in ("qty", "base", "vat", "gross")}

    inv_t, cr_t = total(invoice), total(credit)
    net = {k: inv_t[k] - cr_t[k] for k in ("base", "vat", "gross")}
    other_n, other_total = sums.get(CainiaoBillCharge.ITEM_OTHER, (0, Decimal("0")))
    all_total = _money(sum((t for _, t in sums.values()), Decimal("0")))
    return {
        "invoice": invoice, "invoice_total": inv_t,
        "credit": credit, "credit_total": cr_t,
        "net": net, "cainiao_total": all_total,
        "control": all_total - net["gross"],
        "other_n": other_n, "other_total": _money(other_total),
    }


def dynamic(charges, period_from=None, period_to=None):
    """Quadros da folha "Dinamica": por fatura, por dia, por tarifa e por período."""
    by_bill = list(
        charges.values("bill__bill_id", "bill__main_item").annotate(
            n=Count("id"), total=Sum("amount"), first=Min("business_at"),
            last=Max("business_at"), billed=Max("billing_at"),
        ).order_by("bill__bill_id")
    )
    deliveries = charges.filter(item__in=CainiaoBillCharge.DELIVERY_ITEMS)
    by_day = defaultdict(lambda: {"n": 0, "deliveries": Decimal("0"), "other": Decimal("0")})
    for item, at, amount in charges.values_list("item", "business_at", "amount").iterator():
        day = timezone.localtime(at).date()
        if item in CainiaoBillCharge.DELIVERY_ITEMS:
            by_day[day]["n"] += 1
            by_day[day]["deliveries"] += amount
        else:
            by_day[day]["other"] += amount
    by_tariff = list(
        deliveries.values("amount").annotate(n=Count("id"), total=Sum("amount"))
        .order_by("-n")
    )
    n_deliveries = sum(t["n"] for t in by_tariff) or 1
    for t in by_tariff:
        t["share"] = Decimal(t["n"] * 100) / n_deliveries
        t["base"] = _money(t["amount"] / (1 + VAT))
    periods = []
    if period_from and period_to:
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(period_from, datetime.min.time()), tz)
        end = timezone.make_aware(datetime.combine(period_to, datetime.max.time()), tz)
        for label, q, note in (
            ("No período", Q(business_at__range=(start, end)), "Período a faturar"),
            ("Antes do período", Q(business_at__lt=start), "Acerto retroativo: confirmar antes de incluir"),
            ("Depois do período", Q(business_at__gt=end), "Confirmar antes de incluir"),
        ):
            agg = charges.filter(q).aggregate(n=Count("id"), total=Sum("amount"))
            if agg["n"]:
                periods.append({"label": label, "n": agg["n"], "gross": _money(agg["total"]),
                                "base": _money(agg["total"] / (1 + VAT)), "note": note})
    compensations = list(
        charges.filter(item=CainiaoBillCharge.ITEM_COMPENSATION)
        .select_related("bill").order_by("business_at")
    )
    by_owner = attach_compensation_owners(compensations)
    return {
        "by_bill": by_bill,
        "by_day": sorted(by_day.items()),
        "by_tariff": by_tariff,
        "periods": periods,
        "compensations": compensations,
        "compensations_by_owner": by_owner,
    }


def attach_compensation_owners(compensations):
    """Junta a cada compensação o dono da guia e os descontos já lançados.

    A Cainiao não envia o Employee ID nas compensações. O dono vem da
    entrega com o mesmo número LP: o login usado e a ficha desse ID.
    """
    from .models import CainiaoOperationTask, DriverClaim

    lps = [c.lp_number for c in compensations]
    tasks = {}
    for lp, status, name, courier_id, day, waybill in (
        CainiaoOperationTask.objects.filter(lp_number__in=lps)
        .order_by("task_date")
        .values_list("lp_number", "task_status", "courier_name", "courier_id_cainiao",
                     "task_date", "waybill_number")
    ):
        if lp not in tasks or tasks[lp]["status"] != "Delivered" or status == "Delivered":
            tasks[lp] = {"status": status, "login": name, "courier_id": courier_id,
                         "day": day, "waybill": waybill}
    claims = defaultdict(list)
    waybills = [t["waybill"] for t in tasks.values()] + lps
    for claim in DriverClaim.objects.filter(waybill_number__in=waybills).select_related("driver"):
        claims[claim.waybill_number].append(claim)

    index = _driver_index()
    by_owner = defaultdict(lambda: {"n": 0, "total": Decimal("0"), "claimed": 0})
    for c in compensations:
        c.owner = tasks.get(c.lp_number)
        if c.owner:
            c.owner["driver"] = index.get(c.owner["courier_id"])
        c.claims = claims.get(c.owner["waybill"] if c.owner else "", []) + claims.get(c.lp_number, [])
        driver = c.owner and c.owner["driver"]
        key = driver.nome_completo if driver else (c.owner["login"] if c.owner else "Sem dono identificado")
        by_owner[key]["n"] += 1
        by_owner[key]["total"] += c.amount
        by_owner[key]["claimed"] += 1 if c.claims else 0
    return sorted(by_owner.items(), key=lambda kv: kv[1]["total"])


# ─── Conferências com os dados da operação ─────────────────────────────────────

def _driver_index():
    """Employee ID → motorista (ficha ou mapeamento Cainiao)."""
    from drivers_app.models import DriverProfile
    from .models import DriverCourierMapping
    index = {}
    for m in DriverCourierMapping.objects.select_related("driver"):
        index[m.courier_id] = m.driver
    for d in DriverProfile.objects.exclude(courier_id_cainiao=""):
        index[d.courier_id_cainiao] = d
    return index


def checks(pre_invoice, sample=20):
    """Compara a pré-fatura com as entregas registadas no sistema."""
    from .models import CainiaoOperationTask

    charges = charges_for(pre_invoice).filter(item__in=CainiaoBillCharge.DELIVERY_ITEMS)
    billed = dict(charges.values_list("lp_number", "employee_id"))

    tasks = {}
    lps = list(billed)
    for i in range(0, len(lps), 5000):
        for lp, status, courier_id, name, day in CainiaoOperationTask.objects.filter(
            lp_number__in=lps[i:i + 5000],
        ).values_list("lp_number", "task_status", "courier_id_cainiao", "courier_name", "task_date"):
            if lp not in tasks or status == "Delivered":
                tasks[lp] = (status, courier_id, name, day)

    not_delivered = [lp for lp in lps if tasks.get(lp, ("",))[0] != "Delivered"]
    status_count = Counter(tasks[lp][0] if lp in tasks else "Não existe no sistema" for lp in not_delivered)

    all_billed = CainiaoBillCharge.objects.filter(item__in=CainiaoBillCharge.DELIVERY_ITEMS)
    delivered = CainiaoOperationTask.objects.filter(
        task_status="Delivered",
        task_date__range=(pre_invoice.period_from, pre_invoice.period_to),
    ).exclude(lp_number="")
    unbilled = list(
        delivered.exclude(lp_number__in=all_billed.values("lp_number"))
        .values("lp_number", "waybill_number", "task_date", "courier_name", "zip_code")
        .order_by("task_date")
    )

    index = _driver_index()
    mismatch = Counter()
    for lp, employee in billed.items():
        task = tasks.get(lp)
        if task and task[0] == "Delivered" and employee and task[1] and task[1] != employee:
            mismatch[(task[2], task[1], employee)] += 1
    mismatch_rows = [
        {"courier_name": name, "our_id": ours, "billed_id": theirs, "n": n,
         "billed_driver": index.get(theirs), "our_driver": index.get(ours)}
        for (name, ours, theirs), n in mismatch.most_common()
    ]
    employees = Counter(e for e in billed.values() if e)
    unknown = [{"employee_id": e, "n": n} for e, n in employees.most_common() if e not in index]

    return {
        "n_billed": len(billed),
        "not_delivered_n": len(not_delivered),
        "not_delivered_status": status_count.most_common(),
        "not_delivered_sample": not_delivered[:sample],
        "unbilled_n": len(unbilled),
        "unbilled_by_day": sorted(Counter(u["task_date"] for u in unbilled).items()),
        "unbilled_sample": unbilled[:sample],
        "mismatch_n": sum(mismatch.values()),
        "mismatch_rows": mismatch_rows,
        "unknown_ids": unknown,
    }


def unassigned_bills():
    return CainiaoBill.objects.filter(pre_invoice__isnull=True).order_by("-last_business_at")


def create_pre_invoice(bill_ids, period_from, period_to, user):
    bills = list(CainiaoBill.objects.filter(bill_id__in=bill_ids, pre_invoice__isnull=True))
    if not bills:
        raise SubledgerError("Escolha pelo menos uma fatura Cainiao ainda sem pré-fatura.")
    with transaction.atomic():
        pre = CainiaoClientPreInvoice.objects.create(
            period_from=period_from, period_to=period_to,
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
        CainiaoBill.objects.filter(pk__in=[b.pk for b in bills]).update(pre_invoice=pre)
    return pre


# ─── Excel da pré-fatura ───────────────────────────────────────────────────────
# O visual segue a folha que a equipa usava (cn9-leguas-franzinas-unipessoal-out_2q.xlsx).

XLSX_PREFIX = "cn9-leguas-franzinas-unipessoal"
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
MONTH_NAMES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
               "agosto", "setembro", "outubro", "novembro", "dezembro")
PURPLE, ORANGE, HIGHLIGHT = "2E0A3E", "F7941D", "FDE9D0"
FMT_EUR = "#,##0.00\\ \\€"
FMT_DATE = "mm-dd-yy"
FMT_DATETIME = "yyyy\\-mm\\-dd\\ hh:mm:ss"


def _period_kind(period_from, period_to):
    """'1q', '2q', 'mes' ou None (período livre)."""
    import calendar
    if (period_from.year, period_from.month) != (period_to.year, period_to.month):
        return None
    last = calendar.monthrange(period_to.year, period_to.month)[1]
    return {(1, 15): "1q", (16, last): "2q", (1, last): "mes"}.get((period_from.day, period_to.day))


def period_title(period_from, period_to):
    kind = _period_kind(period_from, period_to)
    month = MONTH_NAMES[period_from.month - 1]
    if kind == "1q":
        return f"1.ª quinzena {month}"
    if kind == "2q":
        return f"2.ª quinzena {month}"
    if kind == "mes":
        return f"{month} {period_from.year}"
    return f"{period_from:%d/%m/%Y} a {period_to:%d/%m/%Y}"


def export_filename(pre_invoice):
    """Ex.: cn9-leguas-franzinas-unipessoal-nov_1q.xlsx (mesmo padrão da folha da equipa)."""
    pf, pt = pre_invoice.period_from, pre_invoice.period_to
    kind = _period_kind(pf, pt)
    month = MONTHS[pf.month - 1]
    if kind in ("1q", "2q"):
        suffix = f"{month}_{kind}"
    elif kind == "mes":
        suffix = month
    else:
        suffix = f"{pf:%Y%m%d}-{pt:%Y%m%d}"
    return f"{XLSX_PREFIX}-{suffix}.xlsx"


class _Sheet:
    """Folha write-only com os estilos da folha da equipa (Arial, roxo e laranja)."""

    def __init__(self, wb, title, widths):
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        self.ws = wb.create_sheet(title)
        for letter, width in widths.items():
            self.ws.column_dimensions[letter].width = width
        purple_fill = PatternFill("solid", fgColor=PURPLE)
        self.styles = {
            "title": {"font": Font(name="Arial", size=14, bold=True, color=PURPLE)},
            "note": {"font": Font(name="Arial", size=9, italic=True)},
            "section": {"font": Font(name="Arial", size=11, bold=True, color=ORANGE)},
            "head": {"font": Font(name="Arial", size=11, bold=True, color="FFFFFF"), "fill": purple_fill,
                     "alignment": Alignment(wrap_text=True, vertical="center")},
            "body": {"font": Font(name="Arial", size=10)},
            "total": {"font": Font(name="Arial", size=10, bold=True),
                      "border": Border(top=Side(style="thin"))},
            "net": {"font": Font(name="Arial", size=11, bold=True, color=PURPLE)},
            "net_hl": {"font": Font(name="Arial", size=11, bold=True, color=PURPLE),
                       "fill": PatternFill("solid", fgColor=HIGHLIGHT)},
            "plain": {"font": Font(name="Arial", size=11)},
        }

    def cell(self, value, style="body", fmt=None):
        from openpyxl.cell import WriteOnlyCell
        c = WriteOnlyCell(self.ws, value=value)
        for attr, v in self.styles[style].items():
            setattr(c, attr, v)
        if fmt:
            c.number_format = fmt
        return c

    def row(self, values, style="body", fmts=None, width=None):
        """Escreve uma linha. `fmts` é {índice: formato}; `width` estende o estilo (ex.: borda do total)."""
        fmts = fmts or {}
        values = list(values) + [None] * max(0, (width or 0) - len(values))
        self.ws.append([self.cell(v, style, fmts.get(i)) for i, v in enumerate(values)])

    def text(self, value, style):
        self.ws.append([self.cell(value, style)])

    def blank(self):
        self.ws.append([])


def _naive(value):
    return timezone.localtime(value).replace(tzinfo=None) if value else None


def export_xlsx(pre_invoice):
    """Excel com as folhas Faturacao, Dinamica, Compensacoes e Linhas."""
    from openpyxl import Workbook

    charges = charges_for(pre_invoice)
    docs = documents(charges)
    dyn = dynamic(charges, pre_invoice.period_from, pre_invoice.period_to)
    period = f"Entregas de {pre_invoice.period_from:%d/%m/%Y} a {pre_invoice.period_to:%d/%m/%Y}"
    title = f"Léguas Franzinas — Faturação Cainiao · {period_title(pre_invoice.period_from, pre_invoice.period_to)}"
    money = float

    wb = Workbook(write_only=True)

    # Faturacao
    s = _Sheet(wb, "Faturacao", {"A": 12, "B": 52, "C": 10, "D": 16, "E": 8, "F": 14, "G": 16, "H": 20})
    s.text("Documentos a emitir à ESDP", "title")
    s.text(period, "note")
    s.text("Valores Cainiao já incluem IVA — base = valor ÷ (1+IVA). Compensações a 0 % de IVA.", "note")
    s.blank()
    head = ["Código", "Descrição", "Qtd.", "Base (s/ IVA)", "IVA %", "Valor IVA", "Valor c/ IVA", "Categoria Cainiao"]
    line_fmts = {3: FMT_EUR, 4: "0%", 5: FMT_EUR, 6: FMT_EUR}
    for section, total_label, lines, total in (
        ("DOCUMENTO 1 — FATURA", "TOTAL FATURA", docs["invoice"], docs["invoice_total"]),
        ("DOCUMENTO 2 — NOTA DE CRÉDITO (descontos)", "TOTAL NOTA DE CRÉDITO", docs["credit"], docs["credit_total"]),
    ):
        s.text(section, "section")
        s.row(head, "head")
        for l in lines:
            s.row([l["code"], l["label"], l["qty"], money(l["base"]), money(l["vat_rate"]),
                   money(l["vat"]), money(l["gross"]), l["raw"]], fmts=line_fmts)
        s.row(["", total_label, total["qty"], money(total["base"]), None, money(total["vat"]),
               money(total["gross"])], "total", line_fmts, width=8)
        s.blank()
    net = docs["net"]
    s.ws.append([None, s.cell("LÍQUIDO A RECEBER", "net"), None,
                 s.cell(money(net["base"]), "net", FMT_EUR), None,
                 s.cell(money(net["vat"]), "net", FMT_EUR),
                 s.cell(money(net["gross"]), "net_hl", FMT_EUR)])
    s.ws.append([None, s.cell("Controlo vs. total Cainiao (deve ser 0,00)", "note"), None, None, None, None,
                 s.cell(money(docs["control"]), "plain", FMT_EUR)])

    # Dinamica
    s = _Sheet(wb, "Dinamica", {"A": 34, "B": 14, "C": 20, "D": 26, "E": 28, "F": 20, "G": 20})
    s.text(title, "title")
    s.text(period, "note")
    s.blank()
    labels = dict(CainiaoBillCharge.ITEM_CHOICES)
    by_item = list(charges.values("item", "item_raw").annotate(n=Count("id"), total=Sum("amount"))
                   .order_by("item"))
    s.text("Por categoria", "section")
    s.row(["Categoria", "Registos", "Valor (€)", "Categoria Cainiao"], "head")
    for r in by_item:
        s.row([labels.get(r["item"], r["item"]), r["n"], money(r["total"]), r["item_raw"]], fmts={2: FMT_EUR})
    s.row(["Total Geral", sum(r["n"] for r in by_item), money(sum((r["total"] for r in by_item), Decimal("0")))],
          "total", {2: FMT_EUR}, width=4)
    s.blank()

    s.text("Por fatura Cainiao", "section")
    s.row(["Bill ID", "Nº linhas", "Valor (€)", "Categoria", "1.ª entrega", "Última entrega", "Faturado em"], "head")
    for b in dyn["by_bill"]:
        s.row([b["bill__bill_id"], b["n"], money(b["total"]), b["bill__main_item"],
               _naive(b["first"]), _naive(b["last"]), _naive(b["billed"])],
              fmts={2: FMT_EUR, 4: FMT_DATETIME, 5: FMT_DATETIME, 6: FMT_DATETIME})
    s.row(["Total", sum(b["n"] for b in dyn["by_bill"]),
           money(sum((b["total"] for b in dyn["by_bill"]), Decimal("0")))], "total", {2: FMT_EUR}, width=7)
    s.blank()

    s.text("Por dia de entrega", "section")
    s.row(["Dia de entrega", "Entregas", "Valor entregas (€)", "Outras rubricas (€)"], "head")
    for day, v in dyn["by_day"]:
        s.row([day, v["n"], money(v["deliveries"]), money(v["other"])],
              fmts={0: FMT_DATE, 2: FMT_EUR, 3: FMT_EUR})
    s.row(["Total", sum(v["n"] for _, v in dyn["by_day"]),
           money(sum((v["deliveries"] for _, v in dyn["by_day"]), Decimal("0"))),
           money(sum((v["other"] for _, v in dyn["by_day"]), Decimal("0")))],
          "total", {2: FMT_EUR, 3: FMT_EUR}, width=4)
    s.blank()

    s.text("Por tarifa unitária (entregas)", "section")
    s.row(["Tarifa c/ IVA (€)", "Registos", "Valor (€)", "% registos"], "head")
    for t in dyn["by_tariff"]:
        s.row([money(t["amount"]), t["n"], money(t["total"]), money(t["share"] / 100)],
              fmts={0: FMT_EUR, 2: FMT_EUR, 3: "0.0%"})
    if dyn["by_tariff"]:
        s.row(["Total", sum(t["n"] for t in dyn["by_tariff"]),
               money(sum((t["total"] for t in dyn["by_tariff"]), Decimal("0"))), 1.0],
              "total", {2: FMT_EUR, 3: "0.0%"}, width=4)
    s.blank()

    s.text("Por período de entrega", "section")
    s.row(["Período", "Registos", "Valor c/ IVA", "Base s/ IVA", "Observação"], "head")
    for p in dyn["periods"]:
        s.row([p["label"], p["n"], money(p["gross"]), money(p["base"]), p["note"]],
              fmts={2: FMT_EUR, 3: FMT_EUR})
    s.row(["Total", sum(p["n"] for p in dyn["periods"]),
           money(sum((p["gross"] for p in dyn["periods"]), Decimal("0"))),
           money(sum((p["base"] for p in dyn["periods"]), Decimal("0")))],
          "total", {2: FMT_EUR, 3: FMT_EUR}, width=5)

    # Compensacoes
    s = _Sheet(wb, "Compensacoes", {"A": 19, "B": 22, "C": 12, "D": 18, "E": 40, "F": 30,
                                     "G": 30, "H": 18, "I": 14, "J": 44})
    s.ws.freeze_panes = "A2"
    s.row(["Data", "Nº encomenda (LP)", "Valor", "Bill ID", "Comentário Cainiao",
           "Motorista (ficha)", "Login", "Guia", "Dia da entrega", "Desconto ao motorista"], "head")
    for c in dyn["compensations"]:
        o = c.owner or {}
        driver = o.get("driver")
        s.row([_naive(c.business_at), c.lp_number, money(c.amount), c.bill.bill_id, c.claim_comment,
               driver.nome_completo if driver else "", o.get("login", ""), o.get("waybill", ""),
               o.get("day"),
               "; ".join(f"{cl.driver.nome_completo} · {cl.get_status_display()} · {cl.amount} €"
                         for cl in c.claims)],
              fmts={0: FMT_DATETIME, 2: FMT_EUR, 8: FMT_DATE})
    s.row(["Total", len(dyn["compensations"]),
           money(sum((c.amount for c in dyn["compensations"]), Decimal("0")))], "total", {2: FMT_EUR}, width=10)

    # Linhas
    head = ["Settlement ID", "Bill ID", "Categoria", "Categoria Cainiao", "Data de negócio",
            "Faturado em", "Valor", "LP", "Employee ID", "Peso (g)", "1.ª na porta",
            "CP", "Fórmula", "Comentário"]
    s = _Sheet(wb, "Linhas", {"A": 16, "B": 17, "C": 18, "D": 13, "E": 19, "F": 19, "G": 10,
                              "H": 22, "I": 16, "J": 10, "K": 10, "L": 9, "M": 17, "N": 30})
    s.ws.freeze_panes = "A2"
    n_rows = charges.count()
    s.ws.auto_filter.ref = f"A1:N{n_rows + 1}"
    s.row(head, "head")
    tz = timezone.get_current_timezone()

    def local(value):
        return value.astimezone(tz).replace(tzinfo=None) if value else None

    fmts = {4: FMT_DATETIME, 5: FMT_DATETIME, 6: "#,##0.00"}
    for row in charges.order_by("business_at").values_list(
        "settlement_id", "bill__bill_id", "item", "item_raw", "business_at", "billing_at",
        "amount", "lp_number", "employee_id", "weight_g", "first_order", "postal_code",
        "formula", "claim_comment",
    ).iterator(chunk_size=5000):
        row = list(row)
        row[2] = labels.get(row[2], row[2])
        row[4], row[5] = local(row[4]), local(row[5])
        row[6] = money(row[6])
        s.row(row, fmts=fmts)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
