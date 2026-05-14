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
from django.db.models import Count, Q, Sum
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from customauth.empresa_auth_views import empresa_login_required
from drivers_app.models import DriverProfile, EmpresaParceira

from .models import (
    CainiaoOperationTask,
    DriverClaim,
    FleetContract,
    FleetDocument,
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
@empresa_login_required
def empresa_portal_dashboard(request, empresa_id):
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
@empresa_login_required
def empresa_portal_invoices(request, empresa_id):
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

    # Transições de estado disponíveis para a fatura em detalhe
    status_transitions = []
    if detail:
        status_display = dict(FleetInvoice.STATUS_CHOICES)
        status_transitions = [
            (s, status_display.get(s, s))
            for s in FleetInvoice.TRANSICOES.get(detail.status, [])
        ]

    ctx = _common_ctx(empresa)
    ctx.update({
        "invoices": invoices,
        "detail": detail,
        "status_transitions": status_transitions,
        "active_tab": "invoices",
    })
    return render(request, "settlements/portal_empresa/invoices.html", ctx)


@empresa_login_required
@require_http_methods(["POST"])
def empresa_portal_attachment_upload(request, empresa_id, fleet_invoice_id):
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


@empresa_login_required
@require_http_methods(["POST"])
def empresa_portal_attachment_delete(request, empresa_id, attachment_id):
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
@empresa_login_required
def empresa_portal_reports(request, empresa_id):
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


# ════════════════════════════════════════════════════════════════════════
# Motoristas da frota
# ════════════════════════════════════════════════════════════════════════
@empresa_login_required
def empresa_portal_drivers(request, empresa_id):
    empresa = _empresa_or_404(empresa_id)

    today = timezone.now().date()
    month_start = today - timedelta(days=29)

    drivers = list(
        DriverProfile.objects.filter(empresa_parceira=empresa)
        .order_by("-is_active", "nome_completo")
    )

    # Para cada motorista: entregas últimos 30d + claims pendentes
    driver_stats = []
    for d in drivers:
        # Entregas 30d
        n_30d = 0
        f = Q()
        if d.courier_id_cainiao:
            f |= Q(courier_id_cainiao=d.courier_id_cainiao)
        if d.apelido:
            f |= Q(courier_name=d.apelido)
        if d.courier_id_cainiao or d.apelido:
            n_30d = CainiaoOperationTask.objects.filter(
                f, task_status="Delivered",
                task_date__range=(month_start, today),
            ).count()

        # Claims pendentes
        claims_pending = DriverClaim.objects.filter(
            driver=d, status="PENDING",
        ).count()
        claims_total_open = DriverClaim.objects.filter(
            driver=d,
        ).exclude(status__in=("REJECTED", "APPEALED")).count()

        driver_stats.append({
            "driver": d,
            "deliveries_30d": n_30d,
            "claims_pending": claims_pending,
            "claims_total_open": claims_total_open,
        })

    ctx = _common_ctx(empresa)
    ctx.update({
        "driver_stats": driver_stats,
        "active_tab": "drivers",
    })
    return render(
        request, "settlements/portal_empresa/drivers.html", ctx,
    )


# ════════════════════════════════════════════════════════════════════════
# Claims da frota (descontos)
# ════════════════════════════════════════════════════════════════════════
@empresa_login_required
def empresa_portal_claims(request, empresa_id):
    empresa = _empresa_or_404(empresa_id)

    status_filter = (request.GET.get("status") or "").upper().strip()
    qs = DriverClaim.objects.filter(
        driver__empresa_parceira=empresa,
    ).select_related("driver").order_by("-created_at")
    if status_filter and status_filter in {"PENDING", "APPROVED", "REJECTED", "APPEALED"}:
        qs = qs.filter(status=status_filter)

    claims = list(qs[:200])

    # Agregados por status
    from django.db.models import Sum
    agg = DriverClaim.objects.filter(
        driver__empresa_parceira=empresa,
    ).values("status").annotate(
        n=Count("id"),
        total=Sum("amount"),
    )
    by_status = {row["status"]: row for row in agg}

    ctx = _common_ctx(empresa)
    ctx.update({
        "claims": claims,
        "status_filter": status_filter,
        "by_status": by_status,
        "active_tab": "claims",
    })
    return render(
        request, "settlements/portal_empresa/claims.html", ctx,
    )


# ════════════════════════════════════════════════════════════════════════
# Perfil (editar dados da empresa)
# ════════════════════════════════════════════════════════════════════════
@empresa_login_required
def empresa_portal_profile(request, empresa_id):
    empresa = _empresa_or_404(empresa_id)

    if request.method == "POST":
        FIELDS = [
            "nome", "nif", "morada", "codigo_postal", "cidade",
            "email", "telefone", "contacto_nome", "iban", "notas",
        ]
        for f in FIELDS:
            if f in request.POST:
                setattr(empresa, f, (request.POST.get(f) or "").strip())
        # Numéricos
        if "taxa_iva" in request.POST:
            try:
                empresa.taxa_iva = Decimal(request.POST.get("taxa_iva") or "0")
            except (ValueError, TypeError):
                pass
        if "driver_default_price_per_package" in request.POST:
            v = (request.POST.get("driver_default_price_per_package") or "").strip()
            if v:
                try:
                    empresa.driver_default_price_per_package = Decimal(v)
                except (ValueError, TypeError):
                    pass
            else:
                empresa.driver_default_price_per_package = None
        # Boolean
        empresa.ativo = request.POST.get("ativo") == "on"
        empresa.save()
        messages.success(request, "Perfil da frota atualizado.")
        return redirect("empresa-portal-profile", empresa_id=empresa.id)

    ctx = _common_ctx(empresa)
    ctx.update({"active_tab": "profile"})
    return render(
        request, "settlements/portal_empresa/profile.html", ctx,
    )


# ════════════════════════════════════════════════════════════════════════
# Documentos da frota
# ════════════════════════════════════════════════════════════════════════
@empresa_login_required
def empresa_portal_documents(request, empresa_id):
    empresa = _empresa_or_404(empresa_id)

    docs = list(empresa.fleet_documents.all().order_by("-uploaded_at"))
    ctx = _common_ctx(empresa)
    ctx.update({
        "documents": docs,
        "active_tab": "documents",
    })
    return render(
        request, "settlements/portal_empresa/documents.html", ctx,
    )


@empresa_login_required
@require_http_methods(["POST"])
def empresa_portal_document_upload(request, empresa_id):
    empresa = _empresa_or_404(empresa_id)
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"success": False, "error": "Sem ficheiro."}, status=400)
    kind = (request.POST.get("kind") or "OUTRO").strip().upper()
    valid_kinds = {k for k, _ in FleetDocument.KIND_CHOICES}
    if kind not in valid_kinds:
        kind = "OUTRO"
    description = (request.POST.get("description") or "").strip()
    valid_until = parse_date(request.POST.get("valid_until") or "") or None
    doc = FleetDocument.objects.create(
        empresa=empresa, kind=kind, file=f,
        description=description, valid_until=valid_until,
        uploaded_by=request.user,
    )
    return JsonResponse({
        "success": True,
        "document": {
            "id": doc.id,
            "kind_display": doc.get_kind_display(),
            "filename": doc.filename,
            "url": doc.file.url,
        },
    })


@empresa_login_required
@require_http_methods(["POST"])
def empresa_portal_document_delete(request, empresa_id, document_id):
    empresa = _empresa_or_404(empresa_id)
    doc = get_object_or_404(
        FleetDocument, id=document_id, empresa=empresa,
    )
    if doc.file:
        try:
            doc.file.delete(save=False)
        except Exception:
            pass
    doc.delete()
    return JsonResponse({"success": True})


# ════════════════════════════════════════════════════════════════════════
# Contratos da frota
# ════════════════════════════════════════════════════════════════════════
@empresa_login_required
def empresa_portal_contracts(request, empresa_id):
    empresa = _empresa_or_404(empresa_id)

    contracts = list(empresa.fleet_contracts.all().order_by("-created_at"))
    ctx = _common_ctx(empresa)
    ctx.update({
        "contracts": contracts,
        "active_tab": "contracts",
    })
    return render(
        request, "settlements/portal_empresa/contracts.html", ctx,
    )


@empresa_login_required
@require_http_methods(["POST"])
def empresa_portal_contract_create(request, empresa_id):
    empresa = _empresa_or_404(empresa_id)
    titulo = (request.POST.get("titulo") or "").strip()
    if not titulo:
        return JsonResponse({"success": False, "error": "Título obrigatório."}, status=400)
    inicio = parse_date(request.POST.get("inicio") or "") or None
    fim = parse_date(request.POST.get("fim") or "") or None
    status = (request.POST.get("status") or "RASCUNHO").strip().upper()
    valid_statuses = {s for s, _ in FleetContract.STATUS_CHOICES}
    if status not in valid_statuses:
        status = "RASCUNHO"
    notas = (request.POST.get("notas") or "").strip()
    f = request.FILES.get("file")
    contract = FleetContract.objects.create(
        empresa=empresa, titulo=titulo, status=status,
        inicio=inicio, fim=fim, notas=notas,
        file=f if f else None,
        created_by=request.user,
    )
    return JsonResponse({"success": True, "id": contract.id})


@empresa_login_required
@require_http_methods(["POST"])
def empresa_portal_contract_update(request, empresa_id, contract_id):
    empresa = _empresa_or_404(empresa_id)
    contract = get_object_or_404(
        FleetContract, id=contract_id, empresa=empresa,
    )
    if "titulo" in request.POST:
        contract.titulo = (request.POST.get("titulo") or "").strip() or contract.titulo
    if "status" in request.POST:
        new_status = (request.POST.get("status") or "").strip().upper()
        valid = {s for s, _ in FleetContract.STATUS_CHOICES}
        if new_status in valid:
            contract.status = new_status
    if "inicio" in request.POST:
        contract.inicio = parse_date(request.POST.get("inicio") or "") or None
    if "fim" in request.POST:
        contract.fim = parse_date(request.POST.get("fim") or "") or None
    if "notas" in request.POST:
        contract.notas = request.POST.get("notas") or ""
    if request.FILES.get("file"):
        if contract.file:
            try:
                contract.file.delete(save=False)
            except Exception:
                pass
        contract.file = request.FILES["file"]
    contract.save()
    return JsonResponse({"success": True})


@empresa_login_required
@require_http_methods(["POST"])
def empresa_portal_contract_delete(request, empresa_id, contract_id):
    empresa = _empresa_or_404(empresa_id)
    contract = get_object_or_404(
        FleetContract, id=contract_id, empresa=empresa,
    )
    if contract.file:
        try:
            contract.file.delete(save=False)
        except Exception:
            pass
    contract.delete()
    return JsonResponse({"success": True})
