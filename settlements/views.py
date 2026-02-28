from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q, Avg
from django.utils.dateparse import parse_date
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
import csv

from .models import SettlementRun, PartnerInvoice, DriverSettlement, DriverClaim
from .services import compute_payouts
from .reports.pdf_generator import PDFGenerator

def _parse_dates(request):
    dfrom = parse_date(request.GET.get("date_from")) if request.GET.get("date_from") else None
    dto   = parse_date(request.GET.get("date_to"))   if request.GET.get("date_to")   else None
    return dfrom, dto

def summary(request):
    dfrom, dto = _parse_dates(request)
    qs = SettlementRun.objects.all()
    if dfrom: qs = qs.filter(run_date__gte=dfrom)
    if dto:   qs = qs.filter(run_date__lte=dto)
    if request.GET.get("driver"): qs = qs.filter(driver__name=request.GET["driver"])
    if request.GET.get("client"): qs = qs.filter(client=request.GET["client"])

    agg = qs.aggregate(
        runs=Sum(1),
        qtd_pact=Sum("qtd_pact"),
        qtd_entregue=Sum("qtd_entregue"),
        bruto=Sum("total_pct"),
        gasoleo=Sum("gasoleo"),
        desconto_tickets=Sum("desconto_tickets"),
        rec_liq_tickets=Sum("rec_liq_tickets"),
        outros=Sum("outros"),
        liquido=Sum("vl_final"),
    )
    qtd_pact = float(agg.get("qtd_pact") or 0)
    qtd_ent  = float(agg.get("qtd_entregue") or 0)
    taxa = round((qtd_ent / qtd_pact) * 100, 2) if qtd_pact > 0 else 0.0
    media = round((float(agg.get("liquido") or 0) / qtd_ent), 2) if qtd_ent > 0 else 0.0
    
    # Para requisições AJAX, retorna JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            "runs": int(agg.get("runs") or 0),
            "qtd_pact": int(agg.get("qtd_pact") or 0),
            "qtd_entregue": int(agg.get("qtd_entregue") or 0),
            "bruto": float(agg.get("bruto") or 0),
            "gasoleo": float(agg.get("gasoleo") or 0),
            "desconto_tickets": float(agg.get("desconto_tickets") or 0),
            "rec_liq_tickets": float(agg.get("rec_liq_tickets") or 0),
            "outros": float(agg.get("outros") or 0),
            "liquido": float(agg.get("liquido") or 0),
            "taxa_sucesso_pct": taxa,
            "avg_liq_por_pacote": media
        })
    
    # Para requisições normais, renderiza o template
    return render(request, 'settlements/summary.html')

def drivers_rank(request):
    dfrom, dto = _parse_dates(request)
    qs = SettlementRun.objects.all()
    if dfrom: qs = qs.filter(run_date__gte=dfrom)
    if dto:   qs = qs.filter(run_date__lte=dto)

    data = (qs.values("driver__name")
              .annotate(
                  entregues=Sum("qtd_entregue"),
                  qtd_pact=Sum("qtd_pact"),
                  liquido=Sum("vl_final"),
              ))
    result = []
    for row in data:
        entregues = int(row["entregues"] or 0)
        pact = int(row["qtd_pact"] or 0)
        taxa = round((entregues / pact) * 100, 2) if pact else 0.0
        result.append({
            "driver": row["driver__name"],
            "entregues": entregues,
            "taxa_media": taxa,
            "liquido": float(row["liquido"] or 0)
        })
    result.sort(key=lambda r: (-r["liquido"], r["driver"]))
    
    # Para requisições AJAX, retorna JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result, safe=False)
    
    # Para requisições normais, renderiza o template
    return render(request, 'settlements/drivers_rank.html')

def runs_list(request):
    dfrom, dto = _parse_dates(request)
    qs = SettlementRun.objects.select_related("driver").all()
    if dfrom: qs = qs.filter(run_date__gte=dfrom)
    if dto:   qs = qs.filter(run_date__lte=dto)
    if request.GET.get("driver"): qs = qs.filter(driver__name=request.GET["driver"])
    if request.GET.get("client"): qs = qs.filter(client=request.GET["client"])
    if request.GET.get("area"):   qs = qs.filter(area_code=request.GET["area"])

    data = list(qs.values(
        "run_date","client","area_code","driver__name",
        "qtd_saida","qtd_pact","qtd_entregue","vl_pct","total_pct",
        "gasoleo","desconto_tickets","rec_liq_tickets","outros","vl_final","notes"
    ).order_by("-run_date")[:1000])
    
    # Para requisições AJAX, retorna JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(data, safe=False)
    
    # Para requisições normais, renderiza o template
    return render(request, 'settlements/runs_list.html')

def payouts(request):
    date_from = request.GET.get("date_from"); date_to = request.GET.get("date_to")
    
    # Para requisições normais sem parâmetros de data, apenas renderiza o template
    if not (date_from and date_to) and request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return render(request, 'settlements/payouts.html')
        
    # Para requisições AJAX, exige os parâmetros de data
    if not (date_from and date_to):
        return JsonResponse({"error":"date_from & date_to são obrigatórios (YYYY-MM-DD)"}, status=400)
        
    client = request.GET.get("client"); area = request.GET.get("area")
    pf = datetime.strptime(date_from, "%Y-%m-%d").date()
    pt = datetime.strptime(date_to, "%Y-%m-%d").date()
    data = compute_payouts(pf, pt, client, area)
    
    # Para requisições AJAX, retorna JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(data, safe=False)
    
    # Para requisições normais, renderiza o template
    return render(request, 'settlements/payouts.html')

def payouts_csv(request):
    date_from = request.GET.get("date_from"); date_to = request.GET.get("date_to")
    if not (date_from and date_to):
        return JsonResponse({"error":"date_from & date_to são obrigatórios (YYYY-MM-DD)"}, status=400)
    client = request.GET.get("client"); area = request.GET.get("area")
    pf = datetime.strptime(date_from, "%Y-%m-%d").date()
    pt = datetime.strptime(date_to, "%Y-%m-%d").date()
    data = compute_payouts(pf, pt, client, area)

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"payouts_{pf}_{pt}.csv"
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    w = csv.writer(resp, delimiter=';')
    w.writerow(["driver","period_from","period_to","entregues","bruto_pkg","bonus","fixo","bruto_total","descontos","liquido","media_liq_por_pacote"])
    for r in data:
        w.writerow([r["driver"], r["period_from"], r["period_to"], r["entregues"], r["bruto_pkg"], r["bonus"], r["fixo"], r["bruto_total"], r["descontos"], r["liquido"], r["media_liq_por_pacote"]])
    return resp


# ==========================================
# FINANCIAL SYSTEM VIEWS (Fase 6)
# ==========================================

@login_required
def financial_dashboard(request):
    """Dashboard principal do sistema financeiro"""
    today = timezone.now().date()
    first_day_month = today.replace(day=1)
    
    # Total counts
    total_invoices = PartnerInvoice.objects.count()
    total_settlements = DriverSettlement.objects.count()
    total_claims = DriverClaim.objects.count()
    
    # KPIs - Invoices
    invoices_stats = {
        'total': total_invoices,
        'pending': PartnerInvoice.objects.filter(status__in=['DRAFT', 'PENDING']).count(),
        'paid': PartnerInvoice.objects.filter(status='PAID').count(),
        'overdue': PartnerInvoice.objects.filter(status='OVERDUE').count(),
    }
    
    # KPIs - Settlements
    settlements_stats = {
        'total': total_settlements,
        'paid': DriverSettlement.objects.filter(status='PAID').count(),
        'pending': DriverSettlement.objects.filter(status__in=['DRAFT', 'CALCULATED', 'APPROVED']).count(),
    }
    
    # KPIs - Claims
    claims_stats = {
        'total': total_claims,
        'pending': DriverClaim.objects.filter(status='PENDING').count(),
        'approved': DriverClaim.objects.filter(status='APPROVED').count(),
        'rejected': DriverClaim.objects.filter(status='REJECTED').count(),
    }
    
    # Recent invoices - formatted for financial_recent_items.html
    recent_invoices_qs = PartnerInvoice.objects.select_related('partner').order_by('-created_at')[:5]
    recent_invoices = []
    for inv in recent_invoices_qs:
        status_class = {
            'PAID': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
            'PENDING': 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
            'OVERDUE': 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
            'DRAFT': 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
        }.get(inv.status, 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300')
        
        recent_invoices.append({
            'title': f'{inv.partner.name if inv.partner else "N/A"} - {inv.invoice_number}',
            'description': f'{inv.period_start.strftime("%d/%m/%Y")} - {inv.period_end.strftime("%d/%m/%Y")}',
            'value': f'€{inv.net_amount:,.2f}',
            'badge': inv.get_status_display(),
            'badge_class': status_class,
        })
    
    # Pending claims - formatted for financial_recent_items.html
    pending_claims_qs = DriverClaim.objects.select_related('driver').filter(status='PENDING').order_by('-created_at')[:5]
    pending_claims = []
    for claim in pending_claims_qs:
        pending_claims.append({
            'title': f'{claim.driver.nome_completo if claim.driver else "N/A"} - {claim.get_claim_type_display()}',
            'description': claim.description[:80] + ('...' if len(claim.description) > 80 else ''),
            'value': f'€{claim.amount:,.2f}' if claim.amount else '—',
            'badge': f'#{claim.id}',
            'badge_class': 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
        })
    
    context = {
        'invoices_stats': invoices_stats,
        'settlements_stats': settlements_stats,
        'claims_stats': claims_stats,
        'recent_invoices': recent_invoices,
        'pending_claims': pending_claims,
    }
    
    return render(request, 'settlements/financial_dashboard_v2.html', context)


@login_required
def invoice_list(request):
    """Lista de invoices de partners"""
    invoices = PartnerInvoice.objects.select_related('partner').all()
    
    # Filtros
    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(status=status)
    
    partner_id = request.GET.get('partner')
    if partner_id:
        invoices = invoices.filter(partner_id=partner_id)
    
    # Filtros de data
    date_from = request.GET.get('date_from')
    if date_from:
        invoices = invoices.filter(period_start__gte=date_from)
    
    date_to = request.GET.get('date_to')
    if date_to:
        invoices = invoices.filter(period_end__lte=date_to)
    
    # Busca
    search = request.GET.get('search')
    if search:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search) |
            Q(external_reference__icontains=search) |
            Q(partner__name__icontains=search)
        )
    
    # Ordenação
    invoices = invoices.order_by('-created_at')
    
    # Paginação
    paginator = Paginator(invoices, 25)  # 25 items por página
    page = request.GET.get('page', 1)
    
    try:
        invoices = paginator.page(page)
    except PageNotAnInteger:
        invoices = paginator.page(1)
    except EmptyPage:
        invoices = paginator.page(paginator.num_pages)
    
    context = {
        'invoices': invoices,
        'status_choices': PartnerInvoice.STATUS_CHOICES,
    }
    
    return render(request, 'settlements/invoice_list_v2.html', context)


@login_required
def invoice_detail(request, invoice_id):
    """Detalhes de uma invoice"""
    invoice = get_object_or_404(PartnerInvoice.objects.select_related('partner'), id=invoice_id)
    
    # Pedidos relacionados (sample - pode precisar de ajuste conforme seu modelo Order)
    from orders_manager.models import Order
    related_orders = Order.objects.filter(
        partner=invoice.partner,
        created_at__gte=invoice.period_start,
        created_at__lte=invoice.period_end,
        current_status='DELIVERED'
    ).select_related('assigned_driver')[:50]
    
    context = {
        'invoice': invoice,
        'related_orders': related_orders,
    }
    
    return render(request, 'settlements/invoice_detail.html', context)


@login_required
def invoice_download_pdf(request, invoice_id):
    """Download do PDF da invoice"""
    invoice = get_object_or_404(PartnerInvoice.objects.select_related('partner'), id=invoice_id)
    
    pdf_gen = PDFGenerator()
    pdf_file = pdf_gen.generate_invoice_pdf(invoice)
    
    response = HttpResponse(pdf_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
    
    return response


@login_required
def settlement_list(request):
    """Lista de settlements de motoristas"""
    settlements = DriverSettlement.objects.select_related('driver', 'partner').all()
    
    # Filtros
    status = request.GET.get('status')
    if status:
        settlements = settlements.filter(status=status)
    
    period_type = request.GET.get('period_type')
    if period_type:
        settlements = settlements.filter(period_type=period_type)
    
    driver_id = request.GET.get('driver')
    if driver_id:
        settlements = settlements.filter(driver_id=driver_id)
    
    # Filtros de data
    date_from = request.GET.get('date_from')
    if date_from:
        settlements = settlements.filter(period_start__gte=date_from)
    
    date_to = request.GET.get('date_to')
    if date_to:
        settlements = settlements.filter(period_end__lte=date_to)
    
    # Busca
    search = request.GET.get('search')
    if search:
        settlements = settlements.filter(
            Q(driver__nome_completo__icontains=search) |
            Q(partner__name__icontains=search)
        )
    
    # Ordenação
    settlements = settlements.order_by('-year', '-week_number', '-month_number')
    
    # Paginação
    paginator = Paginator(settlements, 25)  # 25 items por página
    page = request.GET.get('page', 1)
    
    try:
        settlements = paginator.page(page)
    except PageNotAnInteger:
        settlements = paginator.page(1)
    except EmptyPage:
        settlements = paginator.page(paginator.num_pages)
    
    # Period choices inline
    period_choices = [
        ('WEEKLY', 'Semanal'),
        ('MONTHLY', 'Mensal'),
    ]
    
    context = {
        'settlements': settlements,
        'status_choices': DriverSettlement.STATUS_CHOICES,
        'period_choices': period_choices,
    }
    
    # Create simple template inline
    from django.http import HttpResponse
    return render(request, 'settlements/settlement_list_v2.html', context)


@login_required
def settlement_detail(request, settlement_id):
    """Detalhes de um settlement"""
    settlement = get_object_or_404(
        DriverSettlement.objects.select_related('driver', 'partner').prefetch_related('claims'),
        id=settlement_id
    )
    
    # Pedidos relacionados
    from orders_manager.models import Order
    related_orders = Order.objects.filter(
        assigned_driver=settlement.driver,
        created_at__gte=settlement.period_start,
        created_at__lte=settlement.period_end
    ).select_related('partner')
    
    # Estatísticas de orders
    orders_stats = related_orders.aggregate(
        total=Count('id'),
        delivered=Count('id', filter=Q(current_status='DELIVERED')),
        failed=Count('id', filter=Q(current_status__in=['CANCELLED', 'FAILED'])),
    )
    
    context = {
        'settlement': settlement,
        'related_orders': related_orders[:50],
        'orders_stats': orders_stats,
    }
    
    return render(request, 'settlements/settlement_detail.html', context)


@login_required
def settlement_download_pdf(request, settlement_id):
    """Download do PDF do settlement"""
    settlement = get_object_or_404(
        DriverSettlement.objects.select_related('driver', 'partner'),
        id=settlement_id
    )
    
    pdf_gen = PDFGenerator()
    pdf_file = pdf_gen.generate_settlement_pdf(settlement)
    
    # Gerar nome do arquivo mais descritivo
    driver_name = settlement.driver.nome_completo.replace(' ', '_')
    period = f"S{settlement.week_number}" if settlement.period_type == 'WEEKLY' else f"M{settlement.month_number}"
    filename = f"settlement_{driver_name}_{period}_{settlement.year}.pdf"
    
    response = HttpResponse(pdf_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
def claim_list(request):
    """Lista de claims de motoristas"""
    claims = DriverClaim.objects.select_related('driver', 'settlement', 'order', 'vehicle_incident').all()
    
    # Filtros
    status = request.GET.get('status')
    if status:
        claims = claims.filter(status=status)
    
    claim_type = request.GET.get('claim_type')
    if claim_type:
        claims = claims.filter(claim_type=claim_type)
    
    driver_id = request.GET.get('driver')
    if driver_id:
        claims = claims.filter(driver_id=driver_id)
    
    # Filtros de data
    date_from = request.GET.get('date_from')
    if date_from:
        claims = claims.filter(occurred_at__gte=date_from)
    
    date_to = request.GET.get('date_to')
    if date_to:
        claims = claims.filter(occurred_at__lte=date_to)
    
    # Busca
    search = request.GET.get('search')
    if search:
        claims = claims.filter(
            Q(driver__nome_completo__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Ordenação
    claims = claims.order_by('-created_at')
    
    # Paginação
    paginator = Paginator(claims, 25)  # 25 items por página
    page = request.GET.get('page', 1)
    
    try:
        claims = paginator.page(page)
    except PageNotAnInteger:
        claims = paginator.page(1)
    except EmptyPage:
        claims = paginator.page(paginator.num_pages)
    
    context = {
        'claims': claims,
        'status_choices': DriverClaim.STATUS_CHOICES,
        'type_choices': DriverClaim.CLAIM_TYPES,
    }
    
    return render(request, 'settlements/claim_list_v2.html', context)


@login_required
def claim_detail(request, claim_id):
    """Detalhes de um claim"""
    claim = get_object_or_404(
        DriverClaim.objects.select_related('driver', 'settlement', 'order', 'vehicle_incident'),
        id=claim_id
    )
    
    context = {
        'claim': claim,
    }
    
    return render(request, 'settlements/claim_detail.html', context)
