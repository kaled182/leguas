"""Página inicial: dashboard operacional agregado (todos os parceiros).

Veio de paack_dashboard/views.py (DashboardView) quando a Paack foi removida;
não usa dados da Paack.

v2 (2026-10-26): KPIs com comparação ao mesmo dia da semana anterior,
gráficos (30 dias, estado do dia, ritmo por hora, hubs) e um bloco de
gestão (motoristas, PF, pagamentos, contratos). Agregações numa só
query por eixo (dia, CP4, hora) em vez de uma query por dia/hub.
"""
from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import Substr
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

SERIES_DAYS = 30
WAREHOUSE_KW = ("ARMAZEM", "ARMAZÉM", "HUB", "WAREHOUSE", "DEPOSITO", "DEPÓSITO")
MIN_ATTEMPTS = 5
STATUS_LABELS = [
    ("Delivered", "Entregue"),
    ("Attempt Failure", "Falha"),
    ("Driver_received", "Em rota"),
    ("Assigned", "Atribuído"),
    ("Stale_Armazem", "Stale"),
]


def _rate(d, f):
    return (d / (d + f) * 100) if (d + f) else 0


def _pct_delta(a, b):
    return ((a - b) / b * 100) if b else None


def _is_warehouse(name):
    if not name:
        return True
    up = name.upper()
    return any(kw in up for kw in WAREHOUSE_KW)


@method_decorator(login_required, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class DashboardView(TemplateView):
    """Dashboard agregado de operações. Modo TV: ?tv=1 (auto-refresh 60s)."""

    template_name = "dashboard_leguas/home.html"

    def get_context_data(self, **kwargs):
        from datetime import date as _date

        from core.models import Partner
        from settlements.models import (
            CainiaoHubCP4, CainiaoOperationBatch, CainiaoOperationTask,
            CainiaoOperationTaskHistory,
        )

        ctx = super().get_context_data(**kwargs)
        T = CainiaoOperationTask.objects

        today = timezone.localdate()
        try:
            target = _date.fromisoformat(self.request.GET.get("date", "").strip())
        except (ValueError, TypeError):
            target = today
        d1, d7 = target - timedelta(days=1), target - timedelta(days=7)

        # ─── Estado do dia (1 query) ───
        status_counts = dict(
            T.filter(task_date=target).values_list("task_status").annotate(n=Count("id"))
        )
        total = sum(status_counts.values())
        delivered = status_counts.get("Delivered", 0)
        failures = status_counts.get("Attempt Failure", 0)
        en_route = status_counts.get("Driver_received", 0)
        assigned = status_counts.get("Assigned", 0) + status_counts.get("Unassign", 0)
        attempted = delivered + failures
        success_rate = _rate(delivered, failures)

        # ─── Série de 30 dias (1 query) ───
        start = target - timedelta(days=SERIES_DAYS - 1)
        per_day = {
            r["task_date"]: r for r in
            T.filter(task_date__range=(start, target)).values("task_date").annotate(
                total=Count("id"),
                delivered=Count("id", filter=Q(task_status="Delivered")),
                failures=Count("id", filter=Q(task_status="Attempt Failure")),
            )
        }
        days = [start + timedelta(days=i) for i in range(SERIES_DAYS)]
        empty = {"total": 0, "delivered": 0, "failures": 0}
        series = [{"date": d, **{k: per_day.get(d, empty)[k] for k in empty}} for d in days]
        prev7 = [per_day.get(target - timedelta(days=i), empty) for i in range(1, 8)]
        prev7_del = sum(x["delivered"] for x in prev7)
        prev7_fail = sum(x["failures"] for x in prev7)
        worked_prev7 = [x for x in prev7 if x["total"]]
        avg7_total = (sum(x["total"] for x in worked_prev7) / len(worked_prev7)) if worked_prev7 else 0
        avg7_success = _rate(prev7_del, prev7_fail)
        r_d1, r_d7 = per_day.get(d1, empty), per_day.get(d7, empty)

        # ─── Ritmo por hora: entregas hoje vs média dos 7 dias anteriores ───
        def _by_hour(qs):
            # Em Python (hora local): o ExtractHour do MySQL precisa das
            # tabelas de fusos horários carregadas.
            out = [0] * 24
            for dt in qs.filter(
                task_status="Delivered", delivery_time__isnull=False,
            ).values_list("delivery_time", flat=True).iterator():
                out[timezone.localtime(dt).hour] += 1
            return out

        hour_today = _by_hour(T.filter(task_date=target))
        hour_prev = _by_hour(T.filter(task_date__range=(target - timedelta(days=7), d1)))
        n_prev = len(worked_prev7) or 1
        hour_avg = [round(x / n_prev, 1) for x in hour_prev]

        def _cum(xs):
            acc, out = 0, []
            for x in xs:
                acc += x
                out.append(round(acc, 1))
            return out

        hours = list(range(6, 24))
        rhythm = {
            "labels": [f"{h:02d}h" for h in hours],
            "today": [_cum(hour_today)[h] for h in hours],
            "avg": [_cum(hour_avg)[h] for h in hours],
        }
        now_hour = timezone.localtime().hour
        if target == today:
            rhythm["today"] = [v if h <= now_hour else None for h, v in zip(hours, rhythm["today"])]
            expected_now = _cum(hour_avg)[min(now_hour, 23)]
        else:
            expected_now = sum(hour_avg)
        delivered_vs_expected = _pct_delta(delivered, expected_now) if expected_now else None

        # ─── Hubs e CP4: hoje + 7 dias anteriores (1 query) ───
        cp_hub = dict(CainiaoHubCP4.objects.values_list("cp4", "hub__name"))
        hub_today = defaultdict(lambda: {"total": 0, "delivered": 0, "failures": 0, "en_route": 0})
        hub_prev = defaultdict(int)
        cp4_today = defaultdict(lambda: {"total": 0, "delivered": 0, "failures": 0})
        for r in (
            T.filter(task_date__range=(d7, target)).exclude(zip_code="")
            .annotate(cp4=Substr("zip_code", 1, 4)).values("task_date", "cp4")
            .annotate(
                total=Count("id"),
                delivered=Count("id", filter=Q(task_status="Delivered")),
                failures=Count("id", filter=Q(task_status="Attempt Failure")),
                en_route=Count("id", filter=Q(task_status="Driver_received")),
            )
        ):
            hub = cp_hub.get(r["cp4"], "Sem hub")
            if r["task_date"] == target:
                for k in ("total", "delivered", "failures", "en_route"):
                    hub_today[hub][k] += r[k]
                for k in ("total", "delivered", "failures"):
                    cp4_today[r["cp4"]][k] += r[k]
            else:
                hub_prev[hub] += r["total"]
        hubs = []
        for name, h in hub_today.items():
            avg = hub_prev.get(name, 0) / n_prev
            hubs.append({
                "name": name, **h,
                "success_rate": _rate(h["delivered"], h["failures"]),
                "avg_7d": round(avg),
                "dropping": bool(avg) and target == today and h["total"] < avg * 0.6,
            })
        hubs.sort(key=lambda h: (h["name"] == "Sem hub", -h["total"]))
        top_cp4 = sorted(
            ({"cp4": cp, "hub": cp_hub.get(cp, ""), **v, "success_rate": _rate(v["delivered"], v["failures"])}
             for cp, v in cp4_today.items()),
            key=lambda c: -c["total"],
        )[:10]
        top_cp4_max = max((c["total"] for c in top_cp4), default=1) or 1

        # ─── Motoristas (assinaturas do dia → estado actual do waybill) ───
        status_by_wb = dict(T.filter(task_date=target).values_list("waybill_number", "task_status"))
        drv = defaultdict(set)
        for cn, wb in CainiaoOperationTaskHistory.objects.filter(
            change_type="signature", task_date=target,
        ).values_list("courier_name", "waybill_number"):
            if cn and not _is_warehouse(cn):
                drv[cn].add(wb)
        drivers = []
        for cn, wbs in drv.items():
            dd = sum(1 for wb in wbs if status_by_wb.get(wb) == "Delivered")
            ff = sum(1 for wb in wbs if status_by_wb.get(wb) == "Attempt Failure")
            drivers.append({
                "name": cn, "total": len(wbs), "delivered": dd, "failures": ff,
                "attempts": dd + ff, "success_rate": _rate(dd, ff),
            })
        top_volume = sorted(drivers, key=lambda r: -r["delivered"])[:8]
        top_quality = sorted(
            [d for d in drivers if d["attempts"] >= MIN_ATTEMPTS],
            key=lambda r: (-r["success_rate"], -r["delivered"]),
        )[:8]
        attention = sorted(
            [d for d in drivers if d["failures"]],
            key=lambda r: (-r["failures"], r["success_rate"]),
        )[:8]
        with_delivery = [d for d in drivers if d["delivered"]]
        per_driver = (delivered / len(with_delivery)) if with_delivery else 0

        # ─── Alertas ───
        stale_total = T.filter(task_status="Stale_Armazem").count()
        backlog_total = T.filter(task_status="Driver_received", task_date__lt=target).count()

        # ─── Parceiros (só Cainiao tem dados hoje) ───
        partners = []
        for p in Partner.objects.all().order_by("name"):
            is_c = p.name.upper() == "CAINIAO"
            partners.append({
                "id": p.id, "name": p.name, "url": f"/core/partners/{p.id}/",
                "total": total if is_c else 0, "delivered": delivered if is_c else 0,
                "en_route": en_route if is_c else 0, "failures": failures if is_c else 0,
                "success_rate": success_rate if is_c else 0,
            })

        last_batch = CainiaoOperationBatch.objects.order_by("-created_at").first()

        # ─── SLA T+1 por CP4 ───
        from .services_sla import sla_report

        try:
            sla_days = int(self.request.GET.get("sla_days", 7))
        except ValueError:
            sla_days = 7
        sla_days = sla_days if sla_days in (1, 7, 14, 30) else 7
        sla_working = self.request.GET.get("sla_cal", "uteis") != "corridos"
        sla = sla_report(target, days=sla_days, working_days=sla_working, cp_hub=cp_hub)

        charts = {
            "days": [d.strftime("%d/%m") for d in days],
            "iso": [d.isoformat() for d in days],
            "delivered": [x["delivered"] for x in series],
            "failures": [x["failures"] for x in series],
            "other": [max(x["total"] - x["delivered"] - x["failures"], 0) for x in series],
            "success": [round(_rate(x["delivered"], x["failures"]), 1) if x["delivered"] + x["failures"] else None for x in series],
            "status": [
                {"label": label, "n": status_counts.get(code, 0) + (status_counts.get("Unassign", 0) if code == "Assigned" else 0)}
                for code, label in STATUS_LABELS
            ] + [{"label": "Outros", "n": total - sum(status_counts.get(c, 0) for c, _l in STATUS_LABELS) - status_counts.get("Unassign", 0)}],
            "rhythm": rhythm,
            "hubs": [
                {"label": h["name"], "delivered": h["delivered"], "failures": h["failures"],
                 "en_route": h["en_route"], "rate": round(h["success_rate"], 1)}
                for h in hubs
            ],
        }

        ctx.update({
            "target_date": target,
            "prev_date": d1,
            "next_date": target + timedelta(days=1) if target < today else None,
            "is_today": target == today,
            "today": today,
            "tv_mode": self.request.GET.get("tv") == "1",
            "last_sync": last_batch.created_at if last_batch else None,
            "kpis": {
                "total": total,
                "delivered": delivered,
                "failures": failures,
                "en_route": en_route,
                "assigned": assigned,
                "attempted": attempted,
                "success_rate": success_rate,
                "failure_rate": _rate(failures, delivered),
                "progress_pct": (attempted / total * 100) if total else 0,
                "drivers": len(with_delivery),
                "per_driver": per_driver,
            },
            "compare": {
                "total_d1": r_d1["total"],
                "total_d7": r_d7["total"],
                "delta_total_d7": _pct_delta(total, r_d7["total"]),
                "delta_del_d7": _pct_delta(delivered, r_d7["delivered"]),
                "avg7_total": round(avg7_total),
                "avg7_success": avg7_success,
                "delta_success_pp": (success_rate - avg7_success) if attempted and (prev7_del + prev7_fail) else None,
                "expected_now": round(expected_now),
                "delivered_vs_expected": delivered_vs_expected,
            },
            "partners": partners,
            "hubs": hubs,
            "top_cp4": top_cp4,
            "top_cp4_max": top_cp4_max,
            "top_volume": top_volume,
            "top_quality": top_quality,
            "attention": attention,
            "alerts": {
                "stale_total": stale_total,
                "backlog_total": backlog_total,
                "hubs_dropping": [h for h in hubs if h["dropping"]],
            },
            "mgmt": _management_tiles(today),
            "charts": charts,
            "sla": sla,
            "sla_chart": {**sla["trend"], "hubs": [
                {"label": h["key"], "sla": round(h["sla"], 1) if h["sla"] is not None else None, "n": h["n"]}
                for h in sla["hubs"]
            ]},
        })
        return ctx


def _management_tiles(today):
    """Atalhos de gestão: motoristas, PF, pagamentos, contratos."""
    from django.db.models import Max

    from drivers_app.central_views import _contract_driver_ids
    from drivers_app.models import DriverProfile
    from settlements.models import DriverPreInvoice

    ativos = DriverProfile.objects.filter(status="ATIVO")
    active_ids = set(ativos.filter(inactive_since__isnull=True).values_list("id", flat=True))
    open_pf = DriverPreInvoice.objects.filter(status__in=("CALCULADO", "APROVADO", "PENDENTE"))
    overdue = open_pf.filter(data_prevista_pagamento__lt=today, total_a_receber__gt=0)
    week_end = today + timedelta(days=(1 - today.weekday()) % 7)
    due_week = open_pf.filter(
        data_prevista_pagamento__range=(today, week_end), total_a_receber__gt=0,
    )
    return {
        "drivers_active": len(active_ids),
        "drivers_inactive": ativos.filter(inactive_since__isnull=False).count(),
        "with_contract": len(active_ids & _contract_driver_ids()),
        "pf_to_approve": open_pf.filter(status="CALCULADO").count(),
        "overdue_n": overdue.count(),
        "due_week_n": due_week.count(),
        "due_week_day": week_end,
        "activity_checked": DriverProfile.objects.aggregate(m=Max("activity_checked_at"))["m"],
    }
