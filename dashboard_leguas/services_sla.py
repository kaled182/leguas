"""SLA de entrega T+1 por CP4.

T = dia em que o pacote chegou ao hub (receipt_time, hora local).
Prazo = fim do N.º dia útil depois de T. N vem da regra do CP4
(SlaZoneRule, página "Prazos SLA"); sem regra, N = 1 (T+1). Dias não úteis: domingos e
feriados nacionais (settlements.Holiday, sem região). Com
working_days=False conta dias de calendário.

Por pacote entregue:
  atraso (dias úteis) = dias úteis entre T e a entrega;
  no prazo = entrega até ao dia do prazo.
Em aberto fora do prazo = pacote do dia ainda não entregue cujo prazo
já passou.
"""
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

SLA_DAYS = 1
OPEN_STATUSES = ("Driver_received", "Assigned", "Unassign", "Attempt Failure")


def non_working_days(start, end):
    """Domingos + feriados nacionais (únicos e anuais) no intervalo."""
    from settlements.models import Holiday

    out = set()
    d = start
    while d <= end:
        if d.weekday() == 6:
            out.add(d)
        d += timedelta(days=1)
    for h in Holiday.objects.filter(region=""):
        if h.is_recurring_yearly:
            for y in range(start.year, end.year + 1):
                try:
                    hd = h.date.replace(year=y)
                except ValueError:
                    continue
                if start <= hd <= end:
                    out.add(hd)
        elif start <= h.date <= end:
            out.add(h.date)
    return out


class SlaCalendar:
    def __init__(self, start, end, working_days=True):
        self.working = working_days
        self.off = non_working_days(start - timedelta(days=40), end + timedelta(days=10)) if working_days else set()

    def deadline(self, t, sla_days=SLA_DAYS):
        d, n = t, 0
        while n < sla_days:
            d += timedelta(days=1)
            if d not in self.off:
                n += 1
        return d

    def elapsed(self, t, delivered):
        """Dias (úteis) entre T e a entrega: 0 = no próprio dia."""
        if delivered <= t:
            return 0
        n, d = 0, t
        while d < delivered:
            d += timedelta(days=1)
            if d not in self.off:
                n += 1
        return n


def _bucket(days):
    return min(days, 3)  # 0, 1, 2, 3+


CACHE_SECONDS = 600  # dados Cainiao entram de 30 em 30 min

_SQL_DELIVERED = """
SELECT SUBSTRING(zip_code, 1, 4) AS cp,
       DATE(receipt_time) AS rd, HOUR(receipt_time) = 23 AS rl,
       DATE(delivery_time) AS dd, HOUR(delivery_time) = 23 AS dl,
       COUNT(*) AS n
FROM settlements_cainiaooperationtask FORCE INDEX (settl_task_sla_cover_idx)
WHERE task_status = 'Delivered' AND task_date BETWEEN %s AND %s
  AND receipt_time IS NOT NULL AND delivery_time IS NOT NULL
GROUP BY cp, rd, rl, dd, dl
"""


def _delivered_groups(date_from, date_to, tz):
    """(cp4, dia de chegada, dia de entrega, n) — datas em hora local.

    MySQL: agregação no servidor (milhares de linhas em vez de ~50 mil).
    As datas vêm em UTC; em Portugal só a hora 23 UTC pode cair no dia
    local seguinte (horário de verão, +1 h). Outros motores: Python.
    """
    from datetime import datetime as _dt

    from django.db import connection

    from settlements.models import CainiaoOperationTask as T

    if connection.vendor != "mysql":
        for zip_code, receipt, delivery in T.objects.filter(
            task_status="Delivered", task_date__range=(date_from, date_to),
            receipt_time__isnull=False, delivery_time__isnull=False,
        ).values_list("zip_code", "receipt_time", "delivery_time").iterator():
            yield (zip_code or "")[:4], receipt.astimezone(tz).date(), delivery.astimezone(tz).date(), 1
        return

    shift = {}

    def local(d, late):
        if not late:
            return d
        if d not in shift:
            off = tz.utcoffset(_dt(d.year, d.month, d.day, 23, 30))
            shift[d] = off.total_seconds() >= 3600
        return d + timedelta(days=1) if shift[d] else d

    with connection.cursor() as cur:
        cur.execute(_SQL_DELIVERED, [date_from, date_to])
        for cp, rd, rl, dd, dl, n in cur.fetchall():
            if rd is None or dd is None:
                continue
            yield cp or "", local(rd, rl), local(dd, dl), n


def zone_rules():
    """{cp4: (dias, etiqueta)} das regras configuradas (SlaZoneRule)."""
    from .models import SlaZoneRule

    return {
        r.cp4: (r.sla_days, r.label or r.get_sla_days_display())
        for r in SlaZoneRule.objects.all()
    }


def rule_for(rules, cp):
    days, label = rules.get(cp, (SLA_DAYS, ""))
    return days, label or f"T+{days}"


def sla_report(end, days=7, trend_days=30, working_days=True, cp_hub=None):
    """Relatório SLA (em cache 10 min). Ver _sla_report."""
    from django.core.cache import cache

    import hashlib

    rules = zone_rules()
    sig = hashlib.md5(repr(sorted(rules.items())).encode()).hexdigest()[:8]
    key = f"sla:v3:{end.isoformat()}:{days}:{trend_days}:{int(working_days)}:{sig}"
    data = cache.get(key)
    if data is None:
        data = _sla_report(end, days, trend_days, working_days, cp_hub, rules)
        cache.set(key, data, CACHE_SECONDS)
    return data


def _sla_report(end, days=7, trend_days=30, working_days=True, cp_hub=None, rules=None):
    """Relatório SLA para entregas com task_date em [end-days+1, end]
    e tendência diária de `trend_days` dias."""
    from settlements.models import CainiaoHubCP4, CainiaoOperationTask as T

    tz = timezone.get_current_timezone()  # 1 vez: localtime() por linha é lento
    if rules is None:
        rules = zone_rules()

    if cp_hub is None:
        cp_hub = dict(CainiaoHubCP4.objects.values_list("cp4", "hub__name"))
    start = end - timedelta(days=days - 1)
    trend_start = end - timedelta(days=trend_days - 1)
    cal = SlaCalendar(min(start, trend_start), end, working_days)

    def new_row():
        # le = entregas em ≤1, ≤2, ≤3 dias (para simular outro prazo)
        return {"n": 0, "on_time": 0, "b": [0, 0, 0, 0], "le": [0, 0, 0],
                "late_days": 0, "late": 0, "open_late": 0}

    by_cp = defaultdict(new_row)
    by_hub = defaultdict(new_row)
    total = new_row()
    trend = defaultdict(lambda: [0, 0])  # data de entrega → [n, no prazo]

    for cp, t, dd, k in _delivered_groups(min(start, trend_start), end, tz):
        cp = cp or "—"
        sla_days = rule_for(rules, cp)[0]
        on_time = dd <= cal.deadline(t, sla_days)
        if trend_start <= dd <= end:
            trend[dd][0] += k
            trend[dd][1] += k if on_time else 0
        if not (start <= dd <= end):
            continue
        el = cal.elapsed(t, dd)
        for row in (by_cp[cp], by_hub[cp_hub.get(cp, "Sem hub")], total):
            row["n"] += k
            row["on_time"] += k if on_time else 0
            row["b"][_bucket(el)] += k
            for i in range(3):
                row["le"][i] += k if el <= i + 1 else 0
            if not on_time:
                row["late"] += k
                row["late_days"] += max(el - sla_days, 0) * k

    # Em aberto fora do prazo (estado actual do dia `end`).
    for zip_code, receipt in T.objects.filter(
        task_date=end, task_status__in=OPEN_STATUSES, receipt_time__isnull=False,
    ).values_list("zip_code", "receipt_time").iterator():
        t = receipt.astimezone(tz).date()
        cp = (zip_code or "")[:4] or "—"
        if cal.deadline(t, rule_for(rules, cp)[0]) < end:
            for row in (by_cp[cp], by_hub[cp_hub.get(cp, "Sem hub")], total):
                row["open_late"] += 1

    def finish(key, row, **extra):
        n = row["n"]
        return {
            "key": key, **extra, **row,
            "sla": (row["on_time"] / n * 100) if n else None,
            "pct": [(x / n * 100) if n else 0 for x in row["b"]],
            "avg_late": (row["late_days"] / row["late"]) if row["late"] else 0,
            # SLA se o prazo fosse T+1 / T+2 / T+3
            "sim": [(x / n * 100) if n else None for x in row["le"]],
        }

    cps = [
        finish(cp, r, hub=cp_hub.get(cp, ""), rule_days=rule_for(rules, cp)[0], rule_label=rule_for(rules, cp)[1])
        for cp, r in by_cp.items()
    ]
    cps.sort(key=lambda r: (r["sla"] is None, r["sla"] if r["sla"] is not None else 0, -r["n"]))
    hubs = [finish(h, r) for h, r in by_hub.items()]
    hubs.sort(key=lambda r: -r["n"])
    trend_days_list = [trend_start + timedelta(days=i) for i in range(trend_days)]
    return {
        "start": start, "end": end, "days": days, "working_days": working_days,
        "rules": {cp: {"days": d, "label": label} for cp, (d, label) in rules.items()},
        "total": finish("total", total),
        "cps": cps,
        "hubs": hubs,
        "trend": {
            "labels": [d.strftime("%d/%m") for d in trend_days_list],
            "sla": [round(trend[d][1] / trend[d][0] * 100, 1) if trend[d][0] else None for d in trend_days_list],
            "n": [trend[d][0] for d in trend_days_list],
        },
    }
