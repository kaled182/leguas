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
    return {
        "by_bill": by_bill,
        "by_day": sorted(by_day.items()),
        "by_tariff": by_tariff,
        "periods": periods,
        "compensations": compensations,
    }


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


def export_xlsx(pre_invoice):
    """Excel com as folhas Faturacao, Dinamica, Compensacoes e Linhas."""
    from openpyxl import Workbook

    charges = charges_for(pre_invoice)
    docs = documents(charges)
    dyn = dynamic(charges, pre_invoice.period_from, pre_invoice.period_to)
    period = f"Entregas de {pre_invoice.period_from:%d/%m/%Y} a {pre_invoice.period_to:%d/%m/%Y}"

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Faturacao")
    ws.append(["Documentos a emitir à ESDP"])
    ws.append([period])
    ws.append(["Os valores Cainiao já incluem IVA: base = valor ÷ 1,23. Compensações a 0 % de IVA."])
    ws.append([])
    head = ["Código", "Descrição", "Qtd.", "Base (s/ IVA)", "IVA %", "Valor IVA", "Valor c/ IVA", "Rubrica Cainiao"]
    for title, lines, total in (
        ("DOCUMENTO 1 — FATURA", docs["invoice"], docs["invoice_total"]),
        ("DOCUMENTO 2 — NOTA DE CRÉDITO", docs["credit"], docs["credit_total"]),
    ):
        ws.append([title])
        ws.append(head)
        for l in lines:
            ws.append([l["code"], l["label"], l["qty"], float(l["base"]), float(l["vat_rate"]),
                       float(l["vat"]), float(l["gross"]), l["raw"]])
        ws.append(["", "TOTAL", total["qty"], float(total["base"]), "", float(total["vat"]), float(total["gross"])])
        ws.append([])
    ws.append(["", "LÍQUIDO A RECEBER", "", float(docs["net"]["base"]), "", float(docs["net"]["vat"]), float(docs["net"]["gross"])])
    ws.append(["", "Controlo vs. total Cainiao (deve ser 0,00)", "", "", "", "", float(docs["control"])])

    ws = wb.create_sheet("Dinamica")
    ws.append([period])
    ws.append([])
    ws.append(["Bill ID", "Nº linhas", "Valor (€)", "Rubrica", "1.ª entrega", "Última entrega", "Faturado em"])
    for b in dyn["by_bill"]:
        ws.append([b["bill__bill_id"], b["n"], float(b["total"]), b["bill__main_item"],
                   timezone.localtime(b["first"]).replace(tzinfo=None) if b["first"] else None,
                   timezone.localtime(b["last"]).replace(tzinfo=None) if b["last"] else None,
                   timezone.localtime(b["billed"]).replace(tzinfo=None) if b["billed"] else None])
    ws.append([])
    ws.append(["Dia de entrega", "Entregas", "Valor entregas (€)", "Outras rubricas (€)"])
    for day, v in dyn["by_day"]:
        ws.append([day, v["n"], float(v["deliveries"]), float(v["other"])])
    ws.append([])
    ws.append(["Tarifa c/ IVA (€)", "Registos", "Valor (€)", "% registos"])
    for t in dyn["by_tariff"]:
        ws.append([float(t["amount"]), t["n"], float(t["total"]), float(round(t["share"], 2))])
    ws.append([])
    ws.append(["Período de entrega", "Registos", "Valor c/ IVA", "Base s/ IVA", "Observação"])
    for p in dyn["periods"]:
        ws.append([p["label"], p["n"], float(p["gross"]), float(p["base"]), p["note"]])

    ws = wb.create_sheet("Compensacoes")
    ws.append(["Data", "Nº encomenda (LP)", "Valor", "Bill ID", "Comentário Cainiao"])
    for c in dyn["compensations"]:
        ws.append([timezone.localtime(c.business_at).replace(tzinfo=None), c.lp_number,
                   float(c.amount), c.bill.bill_id, c.claim_comment])

    ws = wb.create_sheet("Linhas")
    ws.append(["Settlement ID", "Bill ID", "Rubrica", "Rubrica Cainiao", "Data de negócio",
               "Faturado em", "Valor", "LP", "Employee ID", "Peso (g)", "1.ª na porta",
               "CP", "Fórmula", "Comentário"])
    tz = timezone.get_current_timezone()
    labels = dict(CainiaoBillCharge.ITEM_CHOICES)

    def local(value):
        return value.astimezone(tz).replace(tzinfo=None) if value else None

    for row in charges.order_by("business_at").values_list(
        "settlement_id", "bill__bill_id", "item", "item_raw", "business_at", "billing_at",
        "amount", "lp_number", "employee_id", "weight_g", "first_order", "postal_code",
        "formula", "claim_comment",
    ).iterator(chunk_size=5000):
        row = list(row)
        row[2] = labels.get(row[2], row[2])
        row[4], row[5] = local(row[4]), local(row[5])
        row[6] = float(row[6])
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
