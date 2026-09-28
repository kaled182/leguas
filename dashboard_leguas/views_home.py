"""Página inicial: dashboard operacional agregado (todos os parceiros).

Veio de paack_dashboard/views.py (DashboardView) quando a Paack foi removida;
não usa dados da Paack.
"""
import os
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView


@method_decorator(login_required, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class DashboardView(TemplateView):
    """Dashboard agregado de operações — todos os parceiros.

    KPIs principais:
        - Volume total do dia, taxa de sucesso, taxa de insucesso
        - Comparação D-1 e D-7 (delta %)
        - Por parceiro (Cainiao + futuros)
        - Por hub, top drivers, top CP4
        - Alertas: backlog, stale, drivers problemáticos
        - Modo TV: ?tv=1 ativa fullscreen + auto-refresh 60s
    """

    template_name = "dashboard_leguas/home.html"

    def get_context_data(self, **kwargs):
        from datetime import date as _date, timedelta
        from collections import Counter
        from django.db.models import Count, Q
        from django.db.models.functions import Substr
        from settlements.models import (
            CainiaoOperationTask, CainiaoOperationTaskHistory,
        )
        from core.models import Partner

        ctx = super().get_context_data(**kwargs)

        # ─── Data filtrada (default = hoje) ───
        today = timezone.now().date()
        date_param = self.request.GET.get("date", "").strip()
        try:
            target_date = _date.fromisoformat(date_param) if date_param else today
        except (ValueError, TypeError):
            target_date = today

        # ─── KPIs do dia ───
        qs_today = CainiaoOperationTask.objects.filter(task_date=target_date)
        total = qs_today.count()
        delivered = qs_today.filter(task_status="Delivered").count()
        en_route = qs_today.filter(task_status="Driver_received").count()
        assigned = qs_today.filter(task_status__in=["Assigned", "Unassign"]).count()
        failures = qs_today.filter(task_status="Attempt Failure").count()
        stale = qs_today.filter(task_status="Stale_Armazem").count()

        completed = delivered + failures  # entregas tentadas
        success_rate = (delivered / completed * 100) if completed else 0
        failure_rate = (failures / completed * 100) if completed else 0
        progress_pct = ((delivered + failures) / total * 100) if total else 0

        # ─── Comparação D-1 e D-7 ───
        yest = target_date - timedelta(days=1)
        last_week = target_date - timedelta(days=7)
        qs_yest = CainiaoOperationTask.objects.filter(task_date=yest)
        qs_lastw = CainiaoOperationTask.objects.filter(task_date=last_week)
        total_yest = qs_yest.count()
        total_lastw = qs_lastw.count()
        del_yest = qs_yest.filter(task_status="Delivered").count()
        del_lastw = qs_lastw.filter(task_status="Delivered").count()

        def _pct_delta(a, b):
            if not b:
                return None
            return ((a - b) / b) * 100

        compare = {
            "total_yest": total_yest,
            "total_lastw": total_lastw,
            "delta_total_yest": _pct_delta(total, total_yest),
            "delta_total_lastw": _pct_delta(total, total_lastw),
            "delta_del_yest": _pct_delta(delivered, del_yest),
            "delta_del_lastw": _pct_delta(delivered, del_lastw),
        }

        # ─── Parceiros (Cainiao + futuros) ───
        partners = []
        for p in Partner.objects.all().order_by("name"):
            if p.name.upper() == "CAINIAO":
                p_total = total
                p_delivered = delivered
                p_en_route = en_route
                p_failures = failures
                p_success = success_rate
            else:
                # Outros parceiros: stub para futuro
                p_total = p_delivered = p_en_route = p_failures = 0
                p_success = 0
            partners.append({
                "id": p.id,
                "name": p.name,
                "total": p_total,
                "delivered": p_delivered,
                "en_route": p_en_route,
                "failures": p_failures,
                "success_rate": p_success,
                "url": f"/core/partners/{p.id}/",
            })

        # ─── Por Hub (apenas HUBs cadastrados — CainiaoHub + CP4s) ───
        from settlements.models import CainiaoHub
        hubs = []
        for hub in CainiaoHub.objects.prefetch_related("cp4_codes").all():
            cp4s = list(hub.cp4_codes.values_list("cp4", flat=True))
            if not cp4s:
                continue
            qs_h = qs_today.filter(
                zip_code__regex=r"^(" + "|".join(cp4s) + ")"
            )
            t = qs_h.count()
            if t == 0:
                continue
            d = qs_h.filter(task_status="Delivered").count()
            f = qs_h.filter(task_status="Attempt Failure").count()
            er = qs_h.filter(task_status="Driver_received").count()
            comp = d + f
            hubs.append({
                "name": hub.name,
                "total": t,
                "delivered": d,
                "failures": f,
                "en_route": er,
                "success_rate": (d / comp * 100) if comp else 0,
            })
        hubs.sort(key=lambda h: -h["total"])

        # ─── Top drivers (via signatures — todos os couriers que tocaram) ───
        sig_today = CainiaoOperationTaskHistory.objects.filter(
            change_type="signature", task_date=target_date,
        )
        # Agregar por courier_name → unique waybills
        from collections import defaultdict
        drv_data = defaultdict(lambda: {"total": set(), "delivered": 0, "failures": 0})
        sig_rows = list(sig_today.values("courier_name", "waybill_number", "task_status"))
        for s in sig_rows:
            cn = s["courier_name"]
            if not cn:
                continue
            drv_data[cn]["total"].add(s["waybill_number"])

        # Status final via current state
        status_by_wb = dict(qs_today.values_list("waybill_number", "task_status"))
        # Reconstruir delivered/failures usando estado vigente do waybill
        for cn, d in drv_data.items():
            for wb in d["total"]:
                st = status_by_wb.get(wb)
                if st == "Delivered":
                    d["delivered"] += 1
                elif st == "Attempt Failure":
                    d["failures"] += 1

        # Top motoristas — ordenados por taxa de sucesso (descendente).
        # Filtramos warehouse couriers (não fazem entregas) e exigimos pelo
        # menos 5 tentativas (delivered+failures) para evitar 100% enviesado
        # de quem só tem 1 pacote.
        WAREHOUSE_KW = ("ARMAZEM", "ARMAZÉM", "HUB", "WAREHOUSE", "DEPOSITO", "DEPÓSITO")
        def _is_warehouse(name):
            if not name:
                return True
            up = name.upper()
            return any(kw in up for kw in WAREHOUSE_KW)

        all_drivers = []
        for cn, d in drv_data.items():
            if _is_warehouse(cn):
                continue
            completed = d["delivered"] + d["failures"]
            all_drivers.append({
                "name": cn,
                "total": len(d["total"]),
                "delivered": d["delivered"],
                "failures": d["failures"],
                "completed": completed,
                "success_rate": (d["delivered"] / completed * 100) if completed else 0,
            })

        MIN_ATTEMPTS = 5
        # Top por taxa de sucesso (com mínimo de 5 tentativas concluídas)
        top_drivers = sorted(
            [d for d in all_drivers if d["completed"] >= MIN_ATTEMPTS],
            key=lambda r: (-r["success_rate"], -r["delivered"]),
        )[:10]

        # ─── Top CP4 (zonas postais) ───
        cp4_qs = (
            qs_today.exclude(zip_code="")
            .annotate(cp4=Substr("zip_code", 1, 4))
            .values("cp4")
            .annotate(
                total=Count("id"),
                delivered=Count("id", filter=Q(task_status="Delivered")),
                failures=Count("id", filter=Q(task_status="Attempt Failure")),
            )
            .order_by("-total")[:10]
        )
        top_cp4 = []
        for c in cp4_qs:
            t = c["total"]
            d = c["delivered"]
            f = c["failures"]
            comp = d + f
            top_cp4.append({
                "cp4": c["cp4"],
                "total": t,
                "delivered": d,
                "failures": f,
                "success_rate": (d / comp * 100) if comp else 0,
            })

        # ─── Histórico 7 dias ───
        history_7d = []
        for i in range(7):
            d = target_date - timedelta(days=6 - i)
            qs_d = CainiaoOperationTask.objects.filter(task_date=d)
            t = qs_d.count()
            del_count = qs_d.filter(task_status="Delivered").count()
            fail_count = qs_d.filter(task_status="Attempt Failure").count()
            comp = del_count + fail_count
            history_7d.append({
                "date": d,
                "label": d.strftime("%d/%m"),
                "total": t,
                "delivered": del_count,
                "failures": fail_count,
                "success_rate": (del_count / comp * 100) if comp else 0,
            })
        history_7d_max = max((x["total"] for x in history_7d), default=1) or 1

        # ─── Alertas ───
        # 1. Stale (>7 dias)
        stale_total = CainiaoOperationTask.objects.filter(
            task_status="Stale_Armazem"
        ).count()
        # 2. Backlog activo (Driver_received com data anterior ao filtro)
        backlog_total = CainiaoOperationTask.objects.filter(
            task_status="Driver_received",
            task_date__lt=target_date,
        ).count()
        # 3. Drivers com mais falhas hoje (top 5)
        problem_drivers = list(
            qs_today.filter(task_status="Attempt Failure")
            .exclude(courier_name="")
            .values("courier_name")
            .annotate(failures=Count("id"))
            .order_by("-failures")[:5]
        )
        # 4. Hubs com queda vs média 7 dias
        hub_avg_7d = {}
        for h in hubs:
            avg = (
                CainiaoOperationTask.objects.filter(
                    destination_area=h["name"],
                    task_date__gte=target_date - timedelta(days=7),
                    task_date__lt=target_date,
                ).count()
                / 7
            )
            if avg and h["total"] < avg * 0.6:  # 40% abaixo da média
                hub_avg_7d[h["name"]] = {"today": h["total"], "avg_7d": int(avg)}

        # ─── Última actualização (último import) ───
        from settlements.models import CainiaoOperationBatch
        last_batch = CainiaoOperationBatch.objects.order_by("-created_at").first()
        last_sync = last_batch.created_at if last_batch else None

        # Modo TV (auto-refresh)
        tv_mode = self.request.GET.get("tv") == "1"

        ctx.update({
            "target_date": target_date,
            "is_today": target_date == today,
            "today": today,
            "tv_mode": tv_mode,
            "last_sync": last_sync,
            "kpis": {
                "total": total,
                "delivered": delivered,
                "en_route": en_route,
                "assigned": assigned,
                "failures": failures,
                "stale": stale,
                "completed": completed,
                "success_rate": success_rate,
                "failure_rate": failure_rate,
                "progress_pct": progress_pct,
            },
            "compare": compare,
            "partners": partners,
            "hubs": hubs,
            "top_drivers": top_drivers,
            "top_cp4": top_cp4,
            "history_7d": history_7d,
            "history_7d_max": history_7d_max,
            "alerts": {
                "stale_total": stale_total,
                "backlog_total": backlog_total,
                "problem_drivers": problem_drivers,
                "hubs_dropping": hub_avg_7d,
            },
        })
        return ctx

