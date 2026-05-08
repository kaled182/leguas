"""Portal da Frota (EmpresaParceira) — views.

Páginas dedicadas a uma empresa parceira específica, espelhando a
estrutura do portal do motorista. Por enquanto só admin tem acesso;
fase 2 abre login próprio para a frota.

Páginas:
    /settlements/empresas/<id>/portal/                 → dashboard
    /settlements/empresas/<id>/portal/faturas/         → lista + detalhe
    /settlements/empresas/<id>/portal/relatorios/      → heatmap + mensal
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from drivers_app.models import DriverProfile, EmpresaParceira

from .models import (
    CainiaoOperationTask,
    FleetInvoice,
    FleetInvoiceAttachment,
    Holiday,
    PreInvoiceBonus,
)


# ════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════
def _admin_required(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def _empresa_or_404(empresa_id):
    return get_object_or_404(EmpresaParceira, id=empresa_id)


def _common_ctx(empresa):
    """Contexto partilhado por todas as páginas do portal de empresa."""
    drivers_active = DriverProfile.objects.filter(
        empresa_parceira=empresa, is_active=True,
    ).count()
    return {
        "empresa": empresa,
        "drivers_active": drivers_active,
        "is_admin_view": True,
    }


# ════════════════════════════════════════════════════════════════════════
# Dashboard
# ════════════════════════════════════════════════════════════════════════
@login_required
def empresa_portal_dashboard(request, empresa_id):
    if not _admin_required(request.user):
        return redirect("paack-dashboard")
    empresa = _empresa_or_404(empresa_id)

    today = timezone.now().date()
    week_start = today - timedelta(days=6)
    month_start = today - timedelta(days=29)
    year_start = today.replace(month=1, day=1)

    # Drivers da frota (ids para filtrar entregas)
    driver_ids = list(
        DriverProfile.objects.filter(
            empresa_parceira=empresa,
        ).values_list("id", flat=True)
    )

    # Couriers identificáveis (id ou apelido) — espelho de empresa_lote_compute
    courier_ids = set()
    courier_names = set()
    for d in DriverProfile.objects.filter(empresa_parceira=empresa):
        if d.courier_id_cainiao:
            courier_ids.add(d.courier_id_cainiao)
        if d.apelido:
            courier_names.add(d.apelido)
        for m in d.courier_mappings.filter(partner__name__iexact="CAINIAO"):
            if m.courier_id:
                courier_ids.add(m.courier_id)
            if m.courier_name:
                courier_names.add(m.courier_name)

    base_qs = CainiaoOperationTask.objects.filter(task_status="Delivered")
    if courier_ids or courier_names:
        f = Q()
        if courier_ids:
            f |= Q(courier_id_cainiao__in=courier_ids)
        if courier_names:
            f |= Q(courier_name__in=courier_names)
        base_qs = base_qs.filter(f)
    else:
        base_qs = base_qs.none()

    def _count_in(start, end):
        return base_qs.filter(task_date__range=(start, end)).count()

    kpis = {
        "today": _count_in(today, today),
        "week": _count_in(week_start, today),
        "month": _count_in(month_start, today),
        "year": _count_in(year_start, today),
    }

    # FleetInvoices recentes (últimos 6 meses)
    six_months_ago = today - timedelta(days=180)
    recent_invoices = list(
        FleetInvoice.objects.filter(
            empresa=empresa,
            periodo_fim__gte=six_months_ago,
        ).order_by("-periodo_fim")[:10]
    )

    # Resumo financeiro YTD (year-to-date)
    ytd = FleetInvoice.objects.filter(
        empresa=empresa,
        periodo_inicio__gte=year_start,
    ).exclude(status="CANCELADO").aggregate(
        total_invoices=Count("id"),
        total_deliveries=Sum("total_deliveries"),
        total_a_receber=Sum("total_a_receber"),
        total_bonus=Sum("total_bonus"),
        total_claims=Sum("total_claims"),
    )

    # Histograma últimos 30 dias para gráfico
    by_day = list(
        base_qs.filter(task_date__range=(month_start, today))
        .values("task_date").annotate(n=Count("id"))
        .order_by("task_date")
    )
    day_lookup = {r["task_date"]: r["n"] for r in by_day}
    days_data = []
    d = month_start
    while d <= today:
        n = day_lookup.get(d, 0)
        h = Holiday.get_holiday(d)
        days_data.append({
            "date": d.strftime("%Y-%m-%d"),
            "label": d.strftime("%d/%m"),
            "n": n,
            "is_sunday": d.weekday() == 6,
            "is_holiday": bool(h),
            "holiday_name": h.name if h else "",
        })
        d += timedelta(days=1)

    max_n = max((d["n"] for d in days_data), default=0)

    ctx = _common_ctx(empresa)
    ctx.update({
        "kpis": kpis,
        "drivers_total": len(driver_ids),
        "recent_invoices": recent_invoices,
        "ytd": ytd,
        "days_data": days_data,
        "max_n": max_n,
        "active_tab": "dashboard",
    })
    return render(request, "settlements/portal_empresa/dashboard.html", ctx)


# ════════════════════════════════════════════════════════════════════════
# Faturas (lista + detalhe)
# ════════════════════════════════════════════════════════════════════════
@login_required
def empresa_portal_invoices(request, empresa_id):
    if not _admin_required(request.user):
        return redirect("paack-dashboard")
    empresa = _empresa_or_404(empresa_id)

    invoices = list(
        FleetInvoice.objects.filter(empresa=empresa)
        .order_by("-periodo_fim")
    )

    # Detalhe (se ?id= fornecido)
    detail = None
    detail_id = request.GET.get("id")
    if detail_id:
        try:
            detail = FleetInvoice.objects.prefetch_related(
                "lines", "lines__bonus_days_detail",
                "lines__claims_detail", "attachments",
            ).get(id=detail_id, empresa=empresa)
        except FleetInvoice.DoesNotExist:
            detail = None

    ctx = _common_ctx(empresa)
    ctx.update({
        "invoices": invoices,
        "detail": detail,
        "active_tab": "invoices",
    })
    return render(request, "settlements/portal_empresa/invoices.html", ctx)


@login_required
@require_http_methods(["POST"])
def empresa_portal_attachment_upload(request, empresa_id, fleet_invoice_id):
    if not _admin_required(request.user):
        return JsonResponse({"success": False, "error": "Sem permissão."}, status=403)
    empresa = _empresa_or_404(empresa_id)
    fi = get_object_or_404(
        FleetInvoice, id=fleet_invoice_id, empresa=empresa,
    )
    f = request.FILES.get("file")
    kind = (request.POST.get("kind") or "OUTRO").strip().upper()
    description = (request.POST.get("description") or "").strip()
    if not f:
        return JsonResponse(
            {"success": False, "error": "Sem ficheiro."}, status=400,
        )
    valid_kinds = {k for k, _ in FleetInvoiceAttachment.KIND_CHOICES}
    if kind not in valid_kinds:
        kind = "OUTRO"
    att = FleetInvoiceAttachment.objects.create(
        fleet_invoice=fi, kind=kind, file=f, description=description,
        uploaded_by=request.user,
    )
    return JsonResponse({
        "success": True,
        "attachment": {
            "id": att.id,
            "kind": att.kind,
            "kind_display": att.get_kind_display(),
            "filename": att.filename,
            "url": att.file.url,
            "description": att.description,
            "uploaded_at": att.uploaded_at.strftime("%Y-%m-%d %H:%M"),
        },
    })


@login_required
@require_http_methods(["POST"])
def empresa_portal_attachment_delete(request, empresa_id, attachment_id):
    if not _admin_required(request.user):
        return JsonResponse({"success": False, "error": "Sem permissão."}, status=403)
    empresa = _empresa_or_404(empresa_id)
    att = get_object_or_404(
        FleetInvoiceAttachment,
        id=attachment_id, fleet_invoice__empresa=empresa,
    )
    if att.file:
        try:
            att.file.delete(save=False)
        except Exception:
            pass
    att.delete()
    return JsonResponse({"success": True})


# ════════════════════════════════════════════════════════════════════════
# Relatórios (heatmap + breakdown mensal)
# ════════════════════════════════════════════════════════════════════════
@login_required
def empresa_portal_reports(request, empresa_id):
    if not _admin_required(request.user):
        return redirect("paack-dashboard")
    empresa = _empresa_or_404(empresa_id)

    today = timezone.now().date()
    try:
        year = int(request.GET.get("year") or today.year)
    except (TypeError, ValueError):
        year = today.year

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    # Identidades Cainiao (ids + nomes) de toda a frota
    courier_ids = set()
    courier_names = set()
    for d in DriverProfile.objects.filter(empresa_parceira=empresa):
        if d.courier_id_cainiao:
            courier_ids.add(d.courier_id_cainiao)
        if d.apelido:
            courier_names.add(d.apelido)
        for m in d.courier_mappings.filter(partner__name__iexact="CAINIAO"):
            if m.courier_id:
                courier_ids.add(m.courier_id)
            if m.courier_name:
                courier_names.add(m.courier_name)

    base_qs = CainiaoOperationTask.objects.filter(
        task_date__range=(year_start, year_end),
        task_status="Delivered",
    )
    if courier_ids or courier_names:
        f = Q()
        if courier_ids:
            f |= Q(courier_id_cainiao__in=courier_ids)
        if courier_names:
            f |= Q(courier_name__in=courier_names)
        base_qs = base_qs.filter(f)
    else:
        base_qs = base_qs.none()

    # Heatmap por dia
    by_day = {
        r["task_date"]: r["n"]
        for r in base_qs.values("task_date").annotate(n=Count("id"))
    }
    max_n = max(by_day.values()) if by_day else 0

    def _level(n):
        if not n:
            return 0
        ratio = n / max_n if max_n else 0
        if ratio <= 0.25:
            return 1
        if ratio <= 0.50:
            return 2
        if ratio <= 0.75:
            return 3
        return 4

    days = []
    total_year = 0
    days_active = 0
    d = year_start
    while d <= year_end:
        n = by_day.get(d, 0)
        h = Holiday.get_holiday(d)
        days.append({
            "date": d.strftime("%Y-%m-%d"),
            "weekday": d.weekday(),
            "n": n,
            "level": _level(n),
            "is_sunday": d.weekday() == 6,
            "is_holiday": bool(h),
            "holiday_name": h.name if h else "",
        })
        total_year += n
        if n > 0:
            days_active += 1
        d += timedelta(days=1)

    # Breakdown mensal
    monthly = []
    for month in range(1, 13):
        m_start = date(year, month, 1)
        if month == 12:
            m_end = date(year, 12, 31)
        else:
            m_end = date(year, month + 1, 1) - timedelta(days=1)
        n = sum(by_day.get(m_start + timedelta(days=i), 0)
                for i in range((m_end - m_start).days + 1))
        # FleetInvoices que cobrem este mês
        invs = list(FleetInvoice.objects.filter(
            empresa=empresa,
            periodo_inicio__lte=m_end,
            periodo_fim__gte=m_start,
        ).exclude(status="CANCELADO"))
        invoice_total = sum(
            (i.total_a_receber for i in invs), Decimal("0")
        )
        invoice_count = len(invs)
        monthly.append({
            "month": month,
            "month_name": [
                "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                "Jul", "Ago", "Set", "Out", "Nov", "Dez",
            ][month - 1],
            "deliveries": n,
            "invoice_count": invoice_count,
            "invoice_total": invoice_total,
        })

    ctx = _common_ctx(empresa)
    ctx.update({
        "year": year,
        "year_prev": year - 1,
        "year_next": year + 1,
        "available_years": list(range(today.year - 3, today.year + 1)),
        "heatmap_days": days,
        "max_n": max_n,
        "total_year": total_year,
        "days_active": days_active,
        "monthly": monthly,
        "active_tab": "reports",
    })
    return render(request, "settlements/portal_empresa/reports.html", ctx)
