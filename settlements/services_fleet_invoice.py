"""Detalhe da pré-fatura da frota (FF), no padrão da PF do motorista.

Cada linha da FF é um motorista. O detalhe da linha usa as mesmas regras do
relatório de motoristas (`task_lines`): preço por CP, mesma porta por morada,
PUDO e preço fixo por guia. As reclamações e o bónus vêm da linha gravada na
FF. O IVA é da frota: aplica-se ao total da FF, não a cada motorista.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

ZERO = Decimal("0")


def line_detail(line, partner=None, hubs=None):
    """Detalhe de uma linha da FF: entregas por hub, dia, CP e mesma porta."""
    from .services_driver_report import (
        DriverData, _cainiao, driver_detail, hub_index, task_lines,
    )

    fi = line.fleet_invoice
    partner = partner or _cainiao()
    hubs = hubs if hubs is not None else hub_index()
    lines, base_price = task_lines(line.driver, fi.periodo_inicio, fi.periodo_fim, partner, hubs)
    dd = DriverData(line.driver, lines, base_price)
    for l in lines:
        dd.by_hub.setdefault(l["hub"], []).append(l)
    detail = driver_detail(dd, fi.periodo_inicio, fi.periodo_fim)
    total = detail["total"]
    # PUDO por dia e ponto: a mesma fonte da PF do motorista.
    from .services_pudo import pudo_breakdown_for_driver
    pudo = pudo_breakdown_for_driver(line.driver, fi.periodo_inicio, fi.periodo_fim, partner)
    sd_price = getattr(partner, "same_door_additional_price", None) or ZERO
    detail.update({
        "pudo_rows": sorted(pudo["rows"], key=lambda r: r["date"]),
        "pudo_totals": pudo["totals"],
        "same_door_price": sd_price,
        "same_door_amount": sum(
            (l["amount"] for l in lines if l["kind"] == "mesma porta"), ZERO,
        ),
        "pudo_amount": sum((l["amount"] for l in lines if l["kind"] == "PUDO"), ZERO),
    })
    claims = list(line.claims_detail.all())
    bonus_days = list(line.bonus_days_detail.all())
    detail.update({
        "line": line,
        "fleet_invoice": fi,
        "task_lines": lines,
        "fleet_claims": claims,
        "fleet_bonus_days": bonus_days,
        # Conferência: o que está gravado na FF vs. o cálculo de agora.
        "check": {
            "deliveries_ok": total["delivered"] == line.deliveries,
            "amount_diff": (total["amount"] - line.base_amount).quantize(Decimal("0.01")),
        },
        "door_avg": _door_avg(lines),
    })
    return detail


def _door_avg(lines):
    door = [l["amount"] for l in lines if l["kind"] == "porta"]
    return (sum(door, ZERO) / len(door)).quantize(Decimal("0.001")) if door else None


def overview(fi):
    """Contexto do detalhe da FF: linhas, totais, CP, dias, gráficos e conferência."""
    from .services_driver_report import _cainiao, hub_index

    partner = _cainiao()
    hubs = hub_index()
    rows = []
    for line in fi.lines.select_related("driver").prefetch_related(
        "claims_detail", "bonus_days_detail",
    ).order_by("-deliveries"):
        d = line_detail(line, partner, hubs)
        rows.append(d)

    # Agregados da frota a partir dos detalhes por motorista.
    tot = defaultdict(lambda: ZERO)
    by_cp = {}
    by_day = {}
    for d in rows:
        t = d["total"]
        for k in ("delivered", "door_normal", "same_door", "pudo", "failures"):
            tot[k] += t[k]
        tot["amount"] += t["amount"]
        for c in d["by_cp"]:
            key = (c["cp4"], c["hub"])
            agg = by_cp.setdefault(key, {
                "cp4": c["cp4"], "hub": c["hub"], "delivered": 0, "door_normal": 0,
                "same_door": 0, "pudo": 0, "amount": ZERO, "unit": set(), "drivers": 0,
            })
            for k in ("delivered", "door_normal", "same_door", "pudo"):
                agg[k] += c[k]
            agg["amount"] += c["amount"]
            agg["unit"] |= set(c["unit"])
            agg["drivers"] += 1
        for x in d["by_day"]:
            agg = by_day.setdefault(x["date"], {
                "date": x["date"], "delivered": 0, "door_normal": 0, "same_door": 0,
                "pudo": 0, "failures": 0, "amount": ZERO, "drivers": 0,
            })
            for k in ("delivered", "door_normal", "same_door", "pudo", "failures"):
                agg[k] += x[k]
            agg["amount"] += x["amount"]
            if x["delivered"]:
                agg["drivers"] += 1
    cps = sorted(by_cp.values(), key=lambda c: (c["hub"], c["cp4"]))
    for c in cps:
        c["unit"] = sorted(c["unit"])
    days = sorted(by_day.values(), key=lambda x: x["date"])

    n_saved = sum(d["line"].deliveries for d in rows)
    check = {
        "saved": n_saved,
        "now": int(tot["delivered"]),
        "ok": n_saved == tot["delivered"],
        "amount_diff": (tot["amount"] - fi.total_base).quantize(Decimal("0.01")),
        "drivers_off": [d for d in rows if not d["check"]["deliveries_ok"]],
    }
    return {
        "rows": rows,
        "totals": dict(tot),
        "by_cp": cps,
        "by_day": days,
        "check": check,
        "charts": {"steps": waterfall_steps(fi), "days": day_series(days)},
        "same_door": sorted(
            ({"driver": d["driver"], **g} for d in rows for g in d["same_door"]),
            key=lambda g: (g["date"], g["driver"].nome_completo, g["address"]),
        ),
        "same_door_amount": sum((d["same_door_amount"] for d in rows), ZERO),
        "same_door_price": rows[0]["same_door_price"] if rows else ZERO,
        "pudo": sorted(
            ({"driver": d["driver"], **r} for d in rows for r in d["pudo_rows"]),
            key=lambda r: (r["date"], r["driver"].nome_completo),
        ),
        "pudo_amount": sum((d["pudo_amount"] for d in rows), ZERO),
        "claims_n": sum(len(d["fleet_claims"]) for d in rows),
        "bonus_n": sum(len(d["fleet_bonus_days"]) for d in rows),
    }


def waterfall_steps(fi):
    """Conta da FF: entregas → bónus → reclamações → IVA da frota → total."""
    from .services_pf_overview import _step

    moves = [
        ("Entregas", fi.total_base),
        ("Bónus", fi.total_bonus),
        ("Reclamações", -fi.total_claims),
        ("IVA", fi.vat_amount),
    ]
    steps, running = [], ZERO
    for label, value in moves:
        if not value:
            continue
        steps.append(_step(label, running, running + value, value))
        running += value
    steps.append(_step("A pagar à frota", 0, fi.total_com_iva, fi.total_com_iva, True))
    return steps


def day_series(days):
    return {
        "labels": [d["date"].strftime("%d/%m") for d in days],
        "door": [d["door_normal"] for d in days],
        "same_door": [d["same_door"] for d in days],
        "pudo": [d["pudo"] for d in days],
        "failures": [d["failures"] for d in days],
    }
