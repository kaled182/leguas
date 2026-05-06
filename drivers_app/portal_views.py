"""Portal do Driver — área pessoal moderna com KPIs e relatórios.

Acesso: admin (Django User com is_staff) pode ver qualquer driver;
        driver autenticado via DriverAccess só pode ver o seu próprio.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import DriverProfile


def portal_access_required(view_func):
    """Permite acesso ao portal de um driver:
       1. Admin (Django User staff/superuser) — pode ver qualquer driver
       2. Driver via DriverAccess — só pode ver o seu próprio (driver_id deve
          coincidir com request.session['driver_profile_id'])
    """
    @wraps(view_func)
    def wrapper(request, driver_id, *args, **kwargs):
        # Admin Django User
        if request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
        ):
            return view_func(request, driver_id, *args, **kwargs)
        # Driver autenticado via DriverAccess
        if request.session.get("is_driver_authenticated"):
            session_pid = request.session.get("driver_profile_id")
            if session_pid and int(session_pid) == int(driver_id):
                return view_func(request, driver_id, *args, **kwargs)
            # Driver autenticado mas a tentar ver outro driver — redirect
            messages.warning(request, "Só podes aceder ao teu próprio portal.")
            return redirect("drivers_app:driver_portal", driver_id=session_pid)
        # Não autenticado: para login do driver
        return redirect("customauth:driver_login")
    return wrapper


def _driver_courier_keys(driver):
    """Retorna (courier_ids, courier_names) para um driver no parceiro CAINIAO.

    Mesma lógica usada no `settlements.views.driver_delivery_report` (legacy)
    para garantir consistência de números entre todas as views.
    """
    from settlements.models import DriverCourierMapping, CourierNameAlias

    courier_ids = set()
    courier_names = set()
    if driver.courier_id_cainiao:
        courier_ids.add(driver.courier_id_cainiao)
    if driver.apelido:
        courier_names.add(driver.apelido)
    for m in driver.courier_mappings.filter(partner__name__iexact="CAINIAO"):
        if m.courier_id:
            courier_ids.add(m.courier_id)
        if m.courier_name:
            courier_names.add(m.courier_name)
    if courier_ids:
        for a in CourierNameAlias.objects.filter(
            partner__name__iexact="CAINIAO",
            courier_id__in=list(courier_ids),
        ):
            if a.courier_name:
                courier_names.add(a.courier_name)
    return courier_ids, courier_names


def _get_driver_courier_names(driver):
    """Retrocompat — retorna apenas o set de courier_names do driver."""
    _ids, names = _driver_courier_keys(driver)
    return names


def _other_driver_courier_names(this_driver):
    """Cache leve: courier_names de OUTROS drivers (apelido +
    DriverCourierMapping.courier_name). Usado para excluir tasks com
    courier_id partilhado mas courier_name de outro driver real
    (bug do EPOD em que o id do hub aparece em entregas de drivers
    normais).
    """
    from .models import DriverProfile
    from settlements.models import DriverCourierMapping

    own_id = this_driver.id
    names = set()
    for ap in DriverProfile.objects.exclude(id=own_id).exclude(
        apelido="",
    ).values_list("apelido", flat=True):
        if ap:
            names.add(ap)
    for cn in DriverCourierMapping.objects.exclude(
        driver_id=own_id,
    ).exclude(courier_name="").values_list("courier_name", flat=True):
        if cn:
            names.add(cn)
    return names


def _driver_base_queryset(driver, date_from, date_to):
    """QuerySet canónico das tarefas de um driver no intervalo.

    Regra:
      - Match directo por courier_name → task pertence ao driver
        (courier_name é específico do driver).
      - Match por courier_id → task pertence ao driver SE o
        courier_name NÃO pertencer a outro driver real (evita capturar
        entregas alheias quando o courier_id do hub é partilhado por
        bug da Cainiao).
      - exclui waybills transferidos PARA outros drivers
      - inclui (UNION) waybills transferidos PARA este driver
    """
    from settlements.models import (
        CainiaoOperationTask, WaybillAttributionOverride,
    )

    courier_ids, courier_names = _driver_courier_keys(driver)
    if not courier_ids and not courier_names:
        return CainiaoOperationTask.objects.none()

    qs = CainiaoOperationTask.objects.filter(
        task_date__range=(date_from, date_to),
    )

    # Names de outros drivers que não pertencem a este driver
    other_names = _other_driver_courier_names(driver) - set(courier_names)

    driver_q = Q()
    if courier_names:
        # Match directo por nome — específico do driver.
        driver_q |= Q(courier_name__in=list(courier_names))
    if courier_ids:
        # Match por id apenas se o nome não pertencer a outro driver
        # (evita capturar entregas alheias com cid partilhado).
        cid_q = Q(courier_id_cainiao__in=list(courier_ids))
        if other_names:
            cid_q &= ~Q(courier_name__in=list(other_names))
        driver_q |= cid_q
    qs = qs.filter(driver_q)

    # Aplicar transferências
    outgoing = set(
        WaybillAttributionOverride.objects.filter(
            task_date__range=(date_from, date_to),
        ).exclude(attributed_to_driver=driver)
        .values_list("waybill_number", flat=True),
    )
    incoming = list(
        WaybillAttributionOverride.objects.filter(
            attributed_to_driver=driver,
            task_date__range=(date_from, date_to),
        ).values_list("waybill_number", flat=True),
    )
    if outgoing:
        qs = qs.exclude(waybill_number__in=outgoing)
    if incoming:
        incoming_qs = CainiaoOperationTask.objects.filter(
            waybill_number__in=incoming,
            task_date__range=(date_from, date_to),
        )
        qs = (qs | incoming_qs).distinct()
    return qs


def _kpi_for_period(driver, start_date, end_date):
    """KPIs operacionais para um intervalo — alinhado com o relatório legacy."""
    qs = _driver_base_queryset(driver, start_date, end_date)
    total = qs.count()
    delivered = qs.filter(task_status="Delivered").count()
    failures = qs.filter(task_status="Attempt Failure").count()
    en_route = qs.filter(task_status="Driver_received").count()
    completed = delivered + failures
    return {
        "total": total,
        "delivered": delivered,
        "failures": failures,
        "en_route": en_route,
        "completed": completed,
        "success_rate": (delivered / completed * 100) if completed else 0,
    }


@portal_access_required
def driver_portal(request, driver_id):
    """Portal principal do driver — KPIs + visão geral."""
    from collections import Counter
    from django.core.paginator import Paginator
    from django.db.models import Count, Q
    from django.db.models.functions import Substr
    from settlements.models import (
        CainiaoOperationTask, CainiaoOperationTaskHistory, Holiday,
    )

    driver = get_object_or_404(DriverProfile, pk=driver_id)

    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    kpis_today = _kpi_for_period(driver, today, today)
    kpis_week = _kpi_for_period(driver, week_start, today)
    kpis_month = _kpi_for_period(driver, month_start, today)
    kpis_year = _kpi_for_period(driver, year_start, today)

    courier_ids, courier_names = _driver_courier_keys(driver)
    has_keys = bool(courier_ids or courier_names)

    # ─── Histórico 30 dias com flags domingo/feriado ───
    history_30d = []
    for i in range(30):
        d = today - timedelta(days=29 - i)
        k = _kpi_for_period(driver, d, d)
        h = Holiday.get_holiday(d)
        history_30d.append({
            "date": d,
            "label": d.strftime("%d/%m"),
            "total": k["total"],
            "delivered": k["delivered"],
            "failures": k["failures"],
            "is_sunday": d.weekday() == 6,
            "is_holiday": bool(h),
            "holiday_name": h.name if h else "",
        })

    # ─── Heatmap anual de actividade ───
    heatmap_days = []
    heatmap_total = 0
    heatmap_active_days = 0
    if has_keys:
        year_qs = _driver_base_queryset(driver, year_start, today).filter(
            task_status="Delivered",
        )
        by_day_count = dict(
            year_qs.values_list("task_date").annotate(n=Count("id"))
            .values_list("task_date", "n")
        )
        max_n = max(by_day_count.values()) if by_day_count else 0

        def _level(n):
            if not n:
                return 0
            ratio = n / max_n if max_n else 0
            if ratio <= 0.25:
                return 1
            if ratio <= 0.5:
                return 2
            if ratio <= 0.75:
                return 3
            return 4

        d = year_start
        while d <= today:
            n = by_day_count.get(d, 0)
            h = Holiday.get_holiday(d)
            heatmap_days.append({
                "date": d, "n": n, "level": _level(n),
                "is_sunday": d.weekday() == 6,
                "is_holiday": bool(h),
                "holiday_name": h.name if h else "",
            })
            heatmap_total += n
            if n > 0:
                heatmap_active_days += 1
            d += timedelta(days=1)

    # ─── Top CP4 do mês ───
    top_cp4 = []
    if has_keys:
        cp4_qs = (
            _driver_base_queryset(driver, month_start, today)
            .exclude(zip_code="")
            .annotate(cp4=Substr("zip_code", 1, 4))
            .values("cp4")
            .annotate(
                total=Count("id"),
                delivered=Count("id", filter=Q(task_status="Delivered")),
                failures=Count("id", filter=Q(task_status="Attempt Failure")),
            )
            .order_by("-total")[:10]
        )
        for c in cp4_qs:
            t = c["total"]
            d_ok = c["delivered"]
            f = c["failures"]
            comp = d_ok + f
            top_cp4.append({
                "cp4": c["cp4"],
                "total": t,
                "delivered": d_ok,
                "failures": f,
                "success_rate": (d_ok / comp * 100) if comp else 0,
            })

    # ─── Lista de waybills do mês (paginada) ───
    waybills_page = None
    if has_keys:
        wbs_qs = (
            _driver_base_queryset(driver, month_start, today)
            .order_by("-task_date", "-id")
            .values(
                "id", "waybill_number", "task_date", "task_status",
                "zip_code", "destination_city",
            )
        )
        paginator = Paginator(wbs_qs, 50)
        page_num = request.GET.get("page", 1)
        try:
            waybills_page = paginator.get_page(page_num)
        except Exception:
            waybills_page = paginator.get_page(1)

    # Ranking entre drivers (mês)
    ranking = _compute_ranking(driver, month_start, today)

    # Última PF
    last_pf = driver.pre_invoices.order_by("-periodo_inicio").first()

    # Contratos (placeholder Fase 3)
    contracts_pending = 0
    contracts_signed = 0

    return render(request, "drivers_app/portal/dashboard.html", {
        "driver": driver,
        "today": today,
        "kpis_today": kpis_today,
        "kpis_week": kpis_week,
        "kpis_month": kpis_month,
        "kpis_year": kpis_year,
        "history_30d": history_30d,
        "ranking": ranking,
        "last_pf": last_pf,
        "contracts_pending": contracts_pending,
        "contracts_signed": contracts_signed,
        # Novos
        "heatmap_days": heatmap_days,
        "heatmap_total": heatmap_total,
        "heatmap_active_days": heatmap_active_days,
        "heatmap_year": year_start.year,
        "top_cp4": top_cp4,
        "waybills_page": waybills_page,
    })


def _compute_ranking(driver, start_date, end_date):
    """Posição do driver no ranking de sucesso entre todos os drivers."""
    from settlements.models import CainiaoOperationTask
    from collections import defaultdict
    rows = (
        CainiaoOperationTask.objects
        .filter(
            task_date__range=(start_date, end_date),
            task_status__in=["Delivered", "Attempt Failure"],
        )
        .exclude(courier_name="")
        .values("courier_name", "task_status")
        .annotate(c=Count("id"))
    )
    by_courier = defaultdict(lambda: {"delivered": 0, "failures": 0})
    for r in rows:
        if r["task_status"] == "Delivered":
            by_courier[r["courier_name"]]["delivered"] = r["c"]
        else:
            by_courier[r["courier_name"]]["failures"] = r["c"]

    rated = []
    for cn, d in by_courier.items():
        comp = d["delivered"] + d["failures"]
        if comp >= 5:  # mínimo 5 tentativas
            rated.append({
                "name": cn, "completed": comp,
                "success_rate": d["delivered"] / comp * 100,
            })
    rated.sort(key=lambda r: -r["success_rate"])

    driver_names = _get_driver_courier_names(driver)
    position = None
    total_ranked = len(rated)
    driver_rate = None
    for i, r in enumerate(rated, 1):
        if r["name"] in driver_names:
            if position is None or r["success_rate"] > (driver_rate or 0):
                position = i
                driver_rate = r["success_rate"]
    return {
        "position": position,
        "total": total_ranked,
        "success_rate": driver_rate,
    }


@portal_access_required
def driver_portal_reports(request, driver_id):
    """Relatórios mensais/anuais detalhados."""
    driver = get_object_or_404(DriverProfile, pk=driver_id)
    today = timezone.now().date()

    # Filtros
    year = int(request.GET.get("year") or today.year)

    # Por mês (12 meses do ano)
    months = []
    for m in range(1, 13):
        start = date(year, m, 1)
        # Último dia do mês
        if m == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, m + 1, 1) - timedelta(days=1)
        if start > today:
            continue
        if end > today:
            end = today
        k = _kpi_for_period(driver, start, end)
        months.append({
            "month": m,
            "label": start.strftime("%B").capitalize(),
            "start": start, "end": end,
            **k,
        })

    # Total ano
    year_kpi = _kpi_for_period(driver, date(year, 1, 1), today if today.year == year else date(year, 12, 31))

    return render(request, "drivers_app/portal/reports.html", {
        "driver": driver,
        "year": year,
        "year_kpi": year_kpi,
        "months": months,
        "today": today,
        "available_years": list(range(today.year - 2, today.year + 1)),
    })


@portal_access_required
def driver_portal_invoices(request, driver_id):
    """Faturas + Financeiro unificados — visível para driver e admin.

    Driver vê: filtros período + KPIs operação + conta-corrente + PFs.
    Admin vê extra: Custo Motorista + Margem Léguas + sobreposições + revogar/etc.
    """
    from datetime import datetime, timedelta
    from decimal import Decimal
    from django.db.models import Sum
    from settlements.models import (
        PreInvoiceAdvance, CainiaoOperationTask, CainiaoOperationTaskHistory,
    )

    driver = get_object_or_404(DriverProfile, pk=driver_id)

    is_admin_view = (
        request.user.is_authenticated
        and (request.user.is_staff or request.user.is_superuser)
    )

    today = timezone.now().date()

    # ─── Filtros de período (para o KPI / relatório) ───
    period = request.GET.get("period", "30d")
    custom_from = request.GET.get("date_from", "")
    custom_to = request.GET.get("date_to", "")
    if custom_from and custom_to:
        try:
            date_from = datetime.strptime(custom_from, "%Y-%m-%d").date()
            date_to = datetime.strptime(custom_to, "%Y-%m-%d").date()
            period = "custom"
        except ValueError:
            date_from, date_to = today - timedelta(days=29), today
    elif period == "7d":
        date_from, date_to = today - timedelta(days=6), today
    elif period == "90d":
        date_from, date_to = today - timedelta(days=89), today
    else:
        date_from, date_to = today - timedelta(days=29), today

    # ─── KPIs operação no período ───
    kpis_period = _kpi_for_period(driver, date_from, date_to)

    # ─── Cálculos financeiros — cascata canónica (mesma do relatório legacy) ───
    # core.finance.resolve_driver_price aplica:
    #   1. driver.price_per_package (override)
    #   2. driver.empresa_parceira.driver_default_price_per_package (frota)
    #   3. partner.driver_default_price_per_package (parceiro)
    #   4. 0
    from core.models import Partner
    from core.finance import resolve_driver_price, resolve_partner_price
    cainiao = Partner.objects.filter(name__iexact="CAINIAO").first()
    price_per_pkg, price_source = resolve_driver_price(driver, cainiao)
    receita_per_pkg = resolve_partner_price(cainiao)
    margem_per_pkg = receita_per_pkg - price_per_pkg
    custo_motorista = price_per_pkg * kpis_period["delivered"]
    receita_estimada = receita_per_pkg * kpis_period["delivered"]
    margem = receita_estimada - custo_motorista

    # ─── Conta-Corrente (advances) ───
    advances_qs = PreInvoiceAdvance.objects.filter(driver=driver).order_by("-data", "-id")
    pending_advances = advances_qs.filter(status="PENDENTE")
    advances_total_pending = pending_advances.aggregate(s=Sum("valor"))["s"] or Decimal("0")

    # ─── Pré-faturas que sobrepõem o período (admin) ───
    overlap_pfs = []
    if is_admin_view:
        overlap_pfs = list(
            driver.pre_invoices.filter(
                periodo_inicio__lte=date_to,
                periodo_fim__gte=date_from,
            ).order_by("-periodo_inicio")[:5]
        )

    # ─── Histórico completo de PFs ───
    pfs = driver.pre_invoices.order_by("-periodo_inicio")

    # Totais por status
    totals_by_status = (
        pfs.values("status")
        .annotate(count=Count("id"), total=Sum("total_a_receber"))
    )

    return render(request, "drivers_app/portal/invoices.html", {
        "driver": driver,
        "is_admin_view": is_admin_view,
        # Filtros
        "period": period,
        "date_from": date_from,
        "date_to": date_to,
        # KPIs operação no período (driver vê)
        "kpis_period": kpis_period,
        # Cálculos financeiros (só admin)
        "price_per_pkg": price_per_pkg,
        "price_source": price_source,
        "receita_per_pkg": receita_per_pkg,
        "margem_per_pkg": margem_per_pkg,
        "custo_motorista": custo_motorista,
        "receita_estimada": receita_estimada,
        "margem": margem,
        # Conta-corrente
        "advances": advances_qs[:50],
        "pending_advances": pending_advances,
        "advances_total_pending": advances_total_pending,
        "overlap_pfs": overlap_pfs,
        # PFs
        "pfs": pfs,
        "totals_by_status": totals_by_status,
        "total_count": pfs.count(),
        "total_value": pfs.aggregate(s=Sum("total_a_receber"))["s"] or Decimal("0"),
    })


@portal_access_required
def driver_portal_profile(request, driver_id):
    """Perfil do driver — leitura + form de pedido de alteração."""
    from .models import DriverProfileChangeRequest
    driver = get_object_or_404(DriverProfile, pk=driver_id)

    if request.method == "POST":
        # Cria um pedido por cada campo alterado
        created = 0
        for field, label in DriverProfileChangeRequest.EDITABLE_FIELDS:
            new_value = (request.POST.get(field, "") or "").strip()
            old_value = (getattr(driver, field) or "")
            old_value_str = str(old_value).strip()
            if new_value == old_value_str:
                continue  # sem mudança

            # Cancela pedidos pending anteriores no mesmo campo
            DriverProfileChangeRequest.objects.filter(
                driver=driver, field=field, status="pending",
            ).update(status="cancelled", reviewed_at=timezone.now(),
                     review_notes="Substituído por novo pedido.")

            DriverProfileChangeRequest.objects.create(
                driver=driver, field=field,
                old_value=old_value_str, new_value=new_value,
                status="pending",
            )
            created += 1
        if created:
            messages.success(
                request,
                f"{created} pedido{'s' if created > 1 else ''} de alteração enviado{'s' if created > 1 else ''} para aprovação."
            )
        else:
            messages.warning(request, "Nenhum campo foi alterado.")
        return redirect("drivers_app:driver_portal_profile", driver_id=driver.id)

    # Pedidos do histórico
    requests_qs = DriverProfileChangeRequest.objects.filter(driver=driver).order_by("-requested_at")
    pending_count = requests_qs.filter(status="pending").count()

    # Pedidos pending por campo (para UI)
    pending_by_field = {}
    for r in requests_qs.filter(status="pending"):
        pending_by_field[r.field] = r

    return render(request, "drivers_app/portal/profile.html", {
        "driver": driver,
        "requests": requests_qs[:30],
        "pending_count": pending_count,
        "pending_by_field": pending_by_field,
        "editable_fields": DriverProfileChangeRequest.EDITABLE_FIELDS,
    })


@portal_access_required
def driver_caderneta_pdf(request, driver_id, year):
    """PDF caderneta anual — todas as PFs do motorista no ano."""
    from .caderneta import render_caderneta_pdf
    driver = get_object_or_404(DriverProfile, pk=driver_id)
    return render_caderneta_pdf(driver, int(year))


@portal_access_required
def driver_pre_invoice_pdf(request, driver_id, pre_invoice_id):
    """Download do PDF da pré-fatura — disponível para o próprio driver
    (via DriverAccess) ou admin."""
    from django.http import HttpResponse, JsonResponse
    from settlements.models import DriverPreInvoice
    from settlements.reports.pdf_generator import PDFGenerator

    pf = get_object_or_404(
        DriverPreInvoice.objects.select_related("driver")
        .prefetch_related(
            "linhas__parceiro", "bonificacoes",
            "pacotes_perdidos", "adiantamentos",
        ),
        id=pre_invoice_id, driver_id=driver_id,
    )
    try:
        generator = PDFGenerator()
        pdf_buffer = generator.generate_pre_invoice_pdf(pf)
        filename = (
            f"PreFatura_{pf.numero}_"
            f"{pf.driver.nome_completo.replace(' ', '_')}.pdf"
        )
        response = HttpResponse(pdf_buffer, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except ImportError:
        return JsonResponse(
            {"error": "ReportLab não está instalado no servidor."},
            status=500,
        )


@portal_access_required
def driver_pre_invoice_upload_recibo(request, driver_id, pre_invoice_id):
    """Upload da fatura-recibo emitida pelo motorista — disponível ao próprio
    driver (via DriverAccess) ou ao admin."""
    from django.http import JsonResponse
    from settlements.models import DriverPreInvoice

    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Método não permitido."}, status=405,
        )

    pf = get_object_or_404(
        DriverPreInvoice, id=pre_invoice_id, driver_id=driver_id,
    )
    ficheiro = request.FILES.get("fatura")
    if not ficheiro:
        return JsonResponse(
            {"success": False, "error": "Nenhum ficheiro enviado."},
            status=400,
        )
    if pf.fatura_ficheiro:
        pf.fatura_ficheiro.delete(save=False)
    pf.fatura_ficheiro = ficheiro
    pf.save(update_fields=["fatura_ficheiro"])
    return JsonResponse({
        "success": True,
        "fatura_url": pf.fatura_ficheiro.url,
        "fatura_name": ficheiro.name,
    })
