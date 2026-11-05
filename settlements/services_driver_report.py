"""Relatório de motoristas por hub, para conferir o pagamento.

O valor de cada entrega usa as mesmas regras de `driver_breakdown` (preço
por CP, mesma porta, PUDO, preço fixo por guia). O hub de cada entrega é o
hub do CP4 da morada (`CainiaoHubCP4`): um motorista que entrega em 2 hubs
aparece nos 2 relatórios, cada um com as suas entregas.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

NO_HUB = "Sem hub"
VAT_RATE = Decimal("0.23")
CENT = Decimal("0.01")


def hub_index():
    """CP4 → nome do hub."""
    from .models import CainiaoHubCP4
    return dict(CainiaoHubCP4.objects.values_list("cp4", "hub__name"))


def _cainiao():
    from core.models import Partner
    return Partner.objects.filter(name__iexact="CAINIAO").first()


def task_lines(driver, date_from, date_to, partner, hubs):
    """Uma linha por tarefa do motorista, com o tipo e o valor sem IVA."""
    from core.finance import resolve_driver_price
    from drivers_app.portal_views import _driver_base_queryset
    from drivers_app.services_cp_pricing import CpPricer

    from .models import PackagePriceOverride
    from .services_driver_breakdown import split_counts
    from .services_pudo import compute_pudo_payment, pudo_key

    tasks = list(
        _driver_base_queryset(driver, date_from, date_to).only(
            "id", "waybill_number", "lp_number", "task_date", "task_status",
            "delivery_type", "delivery_time", "detailed_address", "zip_code",
            "receiver_latitude", "receiver_longitude", "courier_name",
            "task_group_order",
        )
    )
    _counts, extra_ids, pudo_tasks, door_delivered, groups = split_counts(tasks, partner)
    group_of = {t.id: i for i, g in enumerate(groups) for t in g}

    base_price, _src = resolve_driver_price(driver, partner)
    pricer = CpPricer(driver, partner, date_from, date_to)
    sd_price = getattr(partner, "same_door_additional_price", None) or Decimal("0")
    overrides = dict(
        PackagePriceOverride.objects.filter(
            task_date__range=(date_from, date_to),
            waybill_number__in=[t.waybill_number for t in door_delivered],
        ).values_list("waybill_number", "price")
    )

    kind, amount, source = {}, {}, {}
    # Contagem igual à do portal: a guia extra de mesma porta conta como
    # mesma porta, mesmo quando tem preço fixo por guia.
    for t in door_delivered:
        if t.waybill_number in overrides:
            k = "mesma porta" if t.id in extra_ids else "porta"
            kind[t.id], amount[t.id], source[t.id] = k, overrides[t.waybill_number], "fixo por guia"
        elif t.id in extra_ids:
            kind[t.id], amount[t.id], source[t.id] = "mesma porta", sd_price, "mesma porta"
        else:
            unit, src, _cp = pricer.price(t.zip_code)
            kind[t.id], amount[t.id], source[t.id] = "porta", unit or Decimal("0"), src

    # O PUDO paga-se por grupo (1.ª + adicionais); o valor do grupo
    # divide-se pelas guias e o resto do arredondamento vai para a última.
    pudo_groups = defaultdict(list)
    for t in pudo_tasks:
        pudo_groups[(t.task_date, pudo_key(t) or ("solo", t.id))].append(t)
    for g in pudo_groups.values():
        total = compute_pudo_payment(len(g), partner)
        each = (total / len(g)).quantize(CENT, ROUND_HALF_UP)
        for t in g:
            kind[t.id], amount[t.id], source[t.id] = "PUDO", each, "PUDO"
        amount[g[-1].id] = total - each * (len(g) - 1)

    lines = []
    for t in tasks:
        cp4 = (t.zip_code or "").strip()[:4]
        if t.id in kind:
            k = kind[t.id]
        elif t.task_status == "Attempt Failure":
            k = "falha"
        else:
            k = "outro"
        lines.append({
            "task_id": t.id, "date": t.task_date, "waybill": t.waybill_number,
            "lp": t.lp_number or "", "status": t.task_status, "login": t.courier_name or "",
            "kind": k, "cp4": cp4, "zip": t.zip_code or "",
            "address": (t.detailed_address or "").strip(),
            "hub": hubs.get(cp4, NO_HUB),
            "amount": amount.get(t.id, Decimal("0")),
            "source": source.get(t.id, ""),
            "time": t.delivery_time,
            "sd_group": group_of.get(t.id),
        })
    return lines, base_price or Decimal("0")


def summarize(lines):
    """Contagens e valor de uma lista de linhas."""
    s = {"tasks": len(lines), "delivered": 0, "door_normal": 0, "same_door": 0,
         "pudo": 0, "failures": 0, "amount": Decimal("0")}
    days = set()
    for l in lines:
        s["amount"] += l["amount"]
        if l["kind"] == "falha":
            s["failures"] += 1
        elif l["kind"] in ("porta", "mesma porta", "PUDO"):
            s["delivered"] += 1
            days.add(l["date"])
            s[{"porta": "door_normal", "mesma porta": "same_door", "PUDO": "pudo"}[l["kind"]]] += 1
    s["days"] = len(days)
    s["success_pct"] = (
        (Decimal(s["delivered"]) * 100 / (s["delivered"] + s["failures"])).quantize(Decimal("0.1"))
        if s["delivered"] + s["failures"] else None
    )
    return s


def vat_for(driver, amount):
    """IVA 23 % só no regime normal (mesma regra da PF)."""
    if (driver.vat_regime or "isento") == "normal":
        return (amount * VAT_RATE).quantize(CENT, ROUND_HALF_UP)
    return Decimal("0.00")


def irs_for(driver, amount):
    pct = driver.irs_retention_pct or Decimal("0")
    return (amount * pct / 100).quantize(CENT, ROUND_HALF_UP) if pct > 0 else Decimal("0.00")


def candidate_drivers(date_from, date_to):
    """Motoristas com login nas tarefas do período ou com guias transferidas."""
    from django.db.models import Q

    from drivers_app.models import DriverProfile

    from .models import CainiaoOperationTask, CourierNameAlias, WaybillAttributionOverride

    pairs = set(
        CainiaoOperationTask.objects.filter(task_date__range=(date_from, date_to))
        .values_list("courier_name", "courier_id_cainiao").distinct()
    )
    names = {n for n, _ in pairs if n}
    ids = {i for _, i in pairs if i}
    alias_ids = set(
        CourierNameAlias.objects.filter(partner__name__iexact="CAINIAO", courier_name__in=names)
        .values_list("courier_id", flat=True)
    )
    ids |= {i for i in alias_ids if i}
    moved = WaybillAttributionOverride.objects.filter(
        task_date__range=(date_from, date_to),
    ).values_list("attributed_to_driver_id", flat=True)
    return (
        DriverProfile.objects.filter(
            Q(apelido__in=names) | Q(courier_id_cainiao__in=ids)
            | Q(courier_mappings__courier_id__in=ids)
            | Q(courier_mappings__courier_name__in=names)
            | Q(id__in=moved)
        )
        .distinct()
        .select_related("empresa_parceira")
        .order_by("nome_completo")
    )


@dataclass
class DriverData:
    driver: object
    lines: list
    base_price: Decimal
    by_hub: dict = field(default_factory=dict)
    pf: object = None
    claims: list = field(default_factory=list)
    advances: list = field(default_factory=list)

    @property
    def total(self):
        return summarize(self.lines)


def _pf_for(driver_ids, date_from, date_to):
    """PF de cada motorista que cobre o período (a mais recente, sem reprovadas)."""
    from .models import DriverPreInvoice
    out = {}
    for pf in DriverPreInvoice.objects.filter(
        driver_id__in=driver_ids, periodo_inicio__lte=date_to, periodo_fim__gte=date_from,
    ).exclude(status="REPROVADO").order_by("periodo_inicio", "id"):
        out[pf.driver_id] = pf
    return out


CLAIM_OPEN = ("PENDING", "APPEALED", "QUARANTINE")


def _claims_for(driver_ids, date_from, date_to, hubs):
    """Claims de cada motorista com data no período (regra da PF).

    A data é a da entrega (`operation_task_date`) ou, sem ela, a da
    ocorrência. Só os aprovados descontam; um claim passado para uma fatura
    seguinte (`billing_after` >= início do período) não desconta aqui.
    """
    from django.db.models import Q

    from .models import CainiaoOperationTask, DriverClaim

    claims = list(
        DriverClaim.objects.filter(
            **({"driver_id__in": driver_ids} if driver_ids is not None else {})
        ).filter(
            Q(operation_task_date__range=(date_from, date_to))
            | Q(operation_task_date__isnull=True, occurred_at__date__range=(date_from, date_to))
        ).order_by("operation_task_date", "occurred_at", "id")
    )
    zips = dict(
        CainiaoOperationTask.objects.filter(
            waybill_number__in={c.waybill_number for c in claims if c.waybill_number},
        ).values_list("waybill_number", "zip_code")
    )
    out = defaultdict(list)
    for c in claims:
        deferred = bool(c.billing_after and c.billing_after >= date_from)
        out[c.driver_id].append({
            "id": c.id, "waybill": c.waybill_number or "",
            "date": c.operation_task_date or (c.occurred_at.date() if c.occurred_at else None),
            "type": c.get_claim_type_display(), "status": c.status,
            "status_label": c.get_status_display(), "amount": c.amount or Decimal("0"),
            "hub": hubs.get((zips.get(c.waybill_number) or "")[:4], NO_HUB) if c.waybill_number in zips else None,
            "deducted": c.status == "APPROVED" and not deferred,
            "deferred": c.status == "APPROVED" and deferred,
            "description": (c.description or "").strip(),
        })
    return out


def _advances_for(pfs, driver_ids, date_to):
    """Adiantamentos de cada motorista (conta-corrente, descontam depois do IVA).

    Com PF do período: os lançamentos incluídos nessa PF. Sem PF: os pendentes
    com data até ao fim do período (a PF nova inclui os pendentes ao ser criada).
    Os pendentes de um motorista com PF aparecem, mas não descontam.
    """
    from django.db.models import Q

    from .models import PreInvoiceAdvance

    qs = PreInvoiceAdvance.objects.filter(driver_id__in=driver_ids).filter(
        Q(pre_invoice_id__in=[pf.id for pf in pfs.values()], status="INCLUIDO_PF")
        | Q(status="PENDENTE") & (Q(data__lte=date_to) | Q(data__isnull=True))
    ).select_related("pre_invoice").order_by("data", "id")
    out = defaultdict(list)
    for a in qs:
        pf = pfs.get(a.driver_id)
        in_pf = a.status == "INCLUIDO_PF"
        out[a.driver_id].append({
            "id": a.id, "date": a.data, "type": a.get_tipo_display(),
            "description": (a.descricao or "").strip(), "amount": a.valor,
            "status_label": f"Na {pf.numero}" if in_pf and pf else a.get_status_display(),
            "deducted": in_pf or pf is None, "hub": None,
        })
    return out


def collect(date_from, date_to):
    """Linhas de todos os motoristas do período. Devolve (dados, alertas)."""
    from .models import CainiaoOperationTask

    partner = _cainiao()
    hubs = hub_index()
    data = []
    owners = Counter()
    for d in candidate_drivers(date_from, date_to):
        lines, base_price = task_lines(d, date_from, date_to, partner, hubs)
        if not lines:
            continue
        dd = DriverData(d, lines, base_price)
        for l in lines:
            dd.by_hub.setdefault(l["hub"], []).append(l)
            owners[l["task_id"]] += 1
        data.append(dd)
    pfs = _pf_for([dd.driver.id for dd in data], date_from, date_to)
    claims = _claims_for(None, date_from, date_to, hubs)
    advances = _advances_for(pfs, [dd.driver.id for dd in data], date_to)
    for dd in data:
        dd.pf = pfs.get(dd.driver.id)
        dd.claims = claims.get(dd.driver.id, [])
        dd.advances = advances.get(dd.driver.id, [])
        # Claim sem tarefa conhecida e adiantamentos: ficam no hub com mais entregas do motorista.
        main_hub = max(dd.by_hub, key=lambda h: len(dd.by_hub[h]))
        for c in dd.claims + dd.advances:
            c["hub"] = c["hub"] or main_hub
    known = {dd.driver.id for dd in data}
    lost_claims = [c for d_id, cs in claims.items() if d_id not in known for c in cs]

    orphans = Counter()
    for tid, login, zip_code in CainiaoOperationTask.objects.filter(
        task_date__range=(date_from, date_to), task_status="Delivered",
    ).values_list("id", "courier_name", "zip_code"):
        if tid not in owners:
            orphans[(login or "(sem login)", hubs.get((zip_code or "")[:4], NO_HUB))] += 1
    alerts = {
        "orphans": sorted(orphans.items(), key=lambda kv: -kv[1]),
        "orphans_n": sum(orphans.values()),
        "shared_n": sum(1 for n in owners.values() if n > 1),
        "no_price": [dd.driver for dd in data if not dd.base_price],
        "claims_without_tasks": lost_claims,
    }
    return data, alerts


def values(driver, amount, claims, advances=()):
    """Como na PF: produção menos claims aprovados = base sem IVA; IVA e IRS sobre a base;
    os adiantamentos descontam depois do IVA."""
    claims_amount = sum((c["amount"] for c in claims if c["deducted"]), Decimal("0"))
    advances_amount = sum((a["amount"] for a in advances if a["deducted"]), Decimal("0"))
    billable = amount - claims_amount
    vat = vat_for(driver, billable)
    return {
        "claims_n": len(claims),
        "claims_open_n": sum(1 for c in claims if c["status"] in CLAIM_OPEN),
        "claims_amount": claims_amount,
        "billable": billable, "vat": vat, "with_vat": billable + vat,
        "advances_n": sum(1 for a in advances if a["deducted"]),
        "advances_amount": advances_amount,
        "advances_pending_n": sum(1 for a in advances if not a["deducted"]),
        "to_pay": billable + vat - advances_amount,
        "irs": irs_for(driver, billable),
    }


def row_for(dd, hub, date_from, date_to):
    """Linha do relatório: as entregas e os claims do motorista no hub (ou em todos)."""
    lines = dd.lines if hub is None else dd.by_hub.get(hub, [])
    claims = dd.claims if hub is None else [c for c in dd.claims if c["hub"] == hub]
    advances = dd.advances if hub is None else [a for a in dd.advances if a["hub"] == hub]
    s = summarize(lines)
    s.update(values(dd.driver, s["amount"], claims, advances))
    pf = dd.pf
    pf_prod = (pf.base_entregas + pf.total_pudo) if pf else None
    same_period = bool(pf and pf.periodo_inicio == date_from and pf.periodo_fim == date_to)
    total_all = summarize(dd.lines)["amount"]
    return {
        "driver": dd.driver,
        "fleet": dd.driver.empresa_parceira,
        "hubs": sorted(dd.by_hub),
        "other_hubs": sorted(h for h in dd.by_hub if h != hub) if hub else [],
        "pf": pf,
        "pf_production": pf_prod,
        "pf_diff": (total_all - pf_prod) if same_period else None,
        **s,
    }


def build(date_from, date_to, hub=None, fleet_id=None, vat=None, pf_status=None, q=None,
          collected=None):
    """Relatório filtrado: grupos por frota (diretos primeiro) e totais."""
    data, alerts = collected or collect(date_from, date_to)
    rows = []
    for dd in data:
        if hub and hub not in dd.by_hub and not any(c["hub"] == hub for c in dd.claims):
            continue
        d = dd.driver
        if fleet_id == "none" and d.empresa_parceira_id:
            continue
        if fleet_id and fleet_id != "none" and str(d.empresa_parceira_id) != str(fleet_id):
            continue
        if vat and (d.vat_regime or "isento") != vat:
            continue
        if pf_status == "none" and dd.pf:
            continue
        if pf_status and pf_status != "none" and (not dd.pf or dd.pf.status != pf_status):
            continue
        if q and q.lower() not in f"{d.nome_completo} {d.apelido}".lower():
            continue
        row = row_for(dd, hub, date_from, date_to)
        if row["delivered"] or row["failures"] or row["claims_n"]:  # só canceladas: fora
            rows.append(row)

    groups = defaultdict(list)
    for r in rows:
        groups[r["fleet"]].append(r)
    ordered = sorted(groups.items(), key=lambda kv: (kv[0] is not None, kv[0].nome if kv[0] else ""))
    return {
        "groups": [{"fleet": f, "rows": rs, "total": _sum(rs)} for f, rs in ordered],
        "rows": rows,
        "total": _sum(rows),
        "alerts": alerts,
        "data": data,
    }


_SUM_INT = ("tasks", "delivered", "door_normal", "same_door", "pudo", "failures",
            "claims_n", "claims_open_n", "advances_n", "advances_pending_n")
_SUM_EUR = ("amount", "claims_amount", "billable", "vat", "with_vat", "advances_amount", "to_pay", "irs")


def _sum(rows):
    t = {k: sum((r[k] for r in rows), 0) for k in _SUM_INT}
    t.update({k: sum((r[k] for r in rows), Decimal("0")) for k in _SUM_EUR})
    t["drivers"] = len(rows)
    return t


def driver_detail(dd, date_from, date_to):
    """Dados do PDF de um motorista: por hub, por dia, por CP4 e mesma porta."""
    from django.utils import timezone

    hubs = [{"hub": h, **summarize(ls)} for h, ls in sorted(dd.by_hub.items())]
    days = defaultdict(list)
    for l in dd.lines:
        days[l["date"]].append(l)
    by_day = []
    for day, ls in sorted(days.items()):
        times = [timezone.localtime(l["time"]) for l in ls
                 if l["time"] and l["kind"] in ("porta", "mesma porta", "PUDO")]
        by_day.append({"date": day, **summarize(ls),
                       "first": min(times) if times else None, "last": max(times) if times else None})
    cps = defaultdict(list)
    for l in dd.lines:
        if l["kind"] in ("porta", "mesma porta", "PUDO"):
            cps[(l["cp4"], l["hub"])].append(l)
    by_cp = [{"cp4": cp, "hub": h, **summarize(ls),
              "unit": sorted({x["amount"] for x in ls if x["kind"] == "porta"})}
             for (cp, h), ls in sorted(cps.items())]
    sd = defaultdict(list)
    for l in dd.lines:
        if l["sd_group"] is not None:
            sd[l["sd_group"]].append(l)
    same_door = [{"date": g[0]["date"], "address": g[0]["address"], "zip": g[0]["zip"],
                  "n": sum(1 for x in g if x["kind"] == "mesma porta"),
                  "waybills": [x["waybill"] for x in g]}
                 for g in sorted(sd.values(), key=lambda g: (g[0]["date"], g[0]["address"]))]
    total = summarize(dd.lines)
    for h in hubs:
        h["claims_amount"] = sum((c["amount"] for c in dd.claims if c["deducted"] and c["hub"] == h["hub"]),
                                 Decimal("0"))
    return {
        "driver": dd.driver, "hubs": hubs, "by_day": by_day, "by_cp": by_cp,
        "same_door": same_door, "total": total, "claims": dd.claims, "advances": dd.advances,
        **values(dd.driver, total["amount"], dd.claims, dd.advances),
        "base_price": dd.base_price, "pf": dd.pf,
        "logins": sorted({l["login"] for l in dd.lines if l["login"]}),
        "period": (date_from, date_to),
    }


def collect_cached(date_from, date_to, refresh=False):
    """`collect` com cache de 10 min: a página, os PDF e o Excel usam os mesmos dados."""
    from django.core.cache import cache

    key = f"driver-report:v2:{date_from:%Y%m%d}:{date_to:%Y%m%d}"
    hit = None if refresh else cache.get(key)
    if hit is None:
        hit = collect(date_from, date_to)
        cache.set(key, hit, 600)
    return hit
