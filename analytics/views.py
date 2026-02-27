"""
Views para dashboards de analytics e relatórios.
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Avg, Count, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import DailyMetrics, VolumeForecast, PerformanceAlert, DriverPerformance
from core.models import Partner
from orders_manager.models import Order, OrderIncident
from fleet_management.models import Vehicle, VehicleIncident


@login_required
def dashboard_overview(request):
    """
    Dashboard principal consolidado multi-partner.
    Mostra visão geral de todos os partners.
    """
    # Período padrão: últimos 30 dias
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Filtros opcionais
    partner_id = request.GET.get('partner')
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    # Query base
    metrics_query = DailyMetrics.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    )
    
    if partner_id:
        metrics_query = metrics_query.filter(partner_id=partner_id)
    
    # Agregações por partner
    partner_stats = metrics_query.values('partner__name').annotate(
        total_orders=Sum('total_orders'),
        delivered=Sum('delivered_orders'),
        failed=Sum('failed_orders'),
        revenue=Sum('total_revenue'),
        avg_success_rate=Avg('success_rate')
    ).order_by('-total_orders')
    
    # Métricas totais
    totals = metrics_query.aggregate(
        total_orders=Sum('total_orders'),
        delivered_orders=Sum('delivered_orders'),
        failed_orders=Sum('failed_orders'),
        total_revenue=Sum('total_revenue'),
        total_bonuses=Sum('total_bonuses'),
        total_penalties=Sum('total_penalties'),
        avg_success_rate=Avg('success_rate'),
        avg_delivery_time=Avg('average_delivery_time_hours')
    )
    
    # Alertas ativos (não reconhecidos)
    active_alerts = PerformanceAlert.objects.filter(
        is_acknowledged=False
    ).order_by('-severity', '-created_at')[:10]
    
    # Top 5 motoristas do período
    top_drivers = DriverPerformance.objects.filter(
        month__gte=start_date.replace(day=1),
        month__lte=end_date.replace(day=1)
    ).select_related('driver').annotate(
        total_deliveries_sum=Sum('total_deliveries'),
        success_rate_avg=Avg('success_rate')
    ).order_by('-total_deliveries_sum')[:5]
    
    # Previsão próximos 7 dias (método MA7)
    forecast_7d = VolumeForecast.objects.filter(
        forecast_date__gte=end_date,
        forecast_date__lte=end_date + timedelta(days=7),
        method='MA7'
    ).order_by('forecast_date')
    
    # Lista de partners para filtro
    all_partners = Partner.objects.all().order_by('name')
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'selected_partner': partner_id,
        'all_partners': all_partners,
        'partner_stats': partner_stats,
        'totals': totals,
        'active_alerts': active_alerts,
        'top_drivers': top_drivers,
        'forecast_7d': forecast_7d,
        'date_range_days': (end_date - start_date).days + 1,
    }
    
    return render(request, 'analytics/dashboard_overview.html', context)


@login_required
def metrics_dashboard(request):
    """
    Dashboard detalhado de métricas diárias.
    Gráficos de evolução temporal.
    """
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    partner_id = request.GET.get('partner')
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    metrics_query = DailyMetrics.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    )
    
    if partner_id:
        metrics_query = metrics_query.filter(partner_id=partner_id)
    
    # Dados para gráficos (agrupados por data)
    daily_data = metrics_query.values('date').annotate(
        total_orders=Sum('total_orders'),
        delivered=Sum('delivered_orders'),
        failed=Sum('failed_orders'),
        revenue=Sum('total_revenue'),
        success_rate=Avg('success_rate'),
        active_drivers=Sum('active_drivers_count')
    ).order_by('date')
    
    # KPIs principais
    totals = metrics_query.aggregate(
        total_orders=Sum('total_orders'),
        delivered_orders=Sum('delivered_orders'),
        failed_orders=Sum('failed_orders'),
        total_revenue=Sum('total_revenue'),
        avg_success_rate=Avg('success_rate'),
        peak_drivers=Sum('active_drivers_count')
    )
    
    all_partners = Partner.objects.all().order_by('name')
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'selected_partner': partner_id,
        'all_partners': all_partners,
        'daily_data': list(daily_data),
        'totals': totals,
    }
    
    return render(request, 'analytics/metrics_dashboard.html', context)


@login_required
def forecasts_dashboard(request):
    """
    Dashboard de previsões (forecasts).
    Mostra os 5 métodos e compara precisão.
    """
    end_date = timezone.now().date()
    start_date = end_date
    forecast_end = end_date + timedelta(days=30)
    
    partner_id = request.GET.get('partner')
    
    # Previsões futuras
    forecasts_query = VolumeForecast.objects.filter(
        forecast_date__gte=start_date,
        forecast_date__lte=forecast_end
    )
    
    if partner_id:
        forecasts_query = forecasts_query.filter(partner_id=partner_id)
    
    # Previsões por método
    forecasts_by_method = {}
    for method in ['MA7', 'MA30', 'EMA', 'TREND', 'SEASONAL']:
        forecasts_by_method[method] = list(
            forecasts_query.filter(method=method).values(
                'forecast_date', 'predicted_volume', 'lower_bound', 'upper_bound'
            ).order_by('forecast_date')
        )
    
    # Melhor método (MA7 como padrão)
    best_forecasts = list(
        forecasts_query.filter(method='MA7').values(
            'forecast_date', 'predicted_volume', 'method', 'lower_bound', 'upper_bound'
        ).order_by('forecast_date')
    )
    
    # Histórico real vs previsto (últimos 7 dias para validação)
    validation_start = start_date - timedelta(days=7)
    actual_data = DailyMetrics.objects.filter(
        date__gte=validation_start,
        date__lt=start_date
    )
    
    if partner_id:
        actual_data = actual_data.filter(partner_id=partner_id)
    
    actual_vs_predicted = list(
        actual_data.values('date').annotate(
            actual_volume=Sum('total_orders')
        ).order_by('date')
    )
    
    all_partners = Partner.objects.all().order_by('name')
    
    context = {
        'selected_partner': partner_id,
        'all_partners': all_partners,
        'forecasts_by_method': forecasts_by_method,
        'best_forecasts': best_forecasts,
        'actual_vs_predicted': actual_vs_predicted,
        'forecast_start': start_date,
        'forecast_end': forecast_end,
    }
    
    return render(request, 'analytics/forecasts_dashboard.html', context)


@login_required
def alerts_dashboard(request):
    """
    Dashboard de alertas de performance.
    Lista alertas ativos e histórico.
    """
    status_filter = request.GET.get('status', 'ACTIVE')
    severity_filter = request.GET.get('severity')
    alert_type_filter = request.GET.get('alert_type')
    
    alerts_query = PerformanceAlert.objects.all()
    
    if status_filter:
        # Map status to is_acknowledged field
        if status_filter == 'ACTIVE':
            alerts_query = alerts_query.filter(is_acknowledged=False)
        elif status_filter == 'RESOLVED':
            alerts_query = alerts_query.filter(is_acknowledged=True)
    if severity_filter:
        alerts_query = alerts_query.filter(severity=severity_filter)
    if alert_type_filter:
        alerts_query = alerts_query.filter(alert_type=alert_type_filter)
    
    alerts = alerts_query.order_by('-severity', '-created_at')[:100]
    
    # Estatísticas de alertas
    alert_stats = {
        'total_active': PerformanceAlert.objects.filter(is_acknowledged=False).count(),
        'total_resolved': PerformanceAlert.objects.filter(is_acknowledged=True).count(),
        'critical': PerformanceAlert.objects.filter(severity='CRITICAL', is_acknowledged=False).count(),
        'warning': PerformanceAlert.objects.filter(severity='WARNING', is_acknowledged=False).count(),
        'info': PerformanceAlert.objects.filter(severity='INFO', is_acknowledged=False).count(),
    }
    
    # Alertas por tipo
    alerts_by_type = PerformanceAlert.objects.filter(
        status='ACTIVE'
    ).values('alert_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    context = {
        'alerts': alerts,
        'alert_stats': alert_stats,
        'alerts_by_type': alerts_by_type,
        'status_filter': status_filter,
        'severity_filter': severity_filter,
        'alert_type_filter': alert_type_filter,
    }
    
    return render(request, 'analytics/alerts_dashboard.html', context)


@login_required
def drivers_performance_dashboard(request):
    """
    Dashboard de performance de motoristas.
    Rankings e evolução individual.
    """
    # Mês atual por padrão
    today = timezone.now().date()
    current_month = today.replace(day=1)
    
    month_param = request.GET.get('month')
    if month_param:
        current_month = datetime.strptime(month_param, '%Y-%m').date().replace(day=1)
    
    # Performance do mês selecionado
    month_performance = DriverPerformance.objects.filter(
        month=current_month
    ).select_related('driver').order_by('-rank_in_team')
    
    # Top 10 por sucesso
    top_by_success = month_performance.order_by('-success_rate')[:10]
    
    # Top 10 por volume
    top_by_volume = month_performance.order_by('-total_deliveries')[:10]
    
    # Top 10 por receita
    top_by_revenue = month_performance.order_by('-total_earnings')[:10]
    
    # Estatísticas gerais
    stats = month_performance.aggregate(
        total_drivers=Count('id'),
        avg_success_rate=Avg('success_rate'),
        total_deliveries=Sum('total_deliveries'),
        total_earnings=Sum('total_earnings')
    )
    
    # Últimos 6 meses para evolução
    six_months_ago = current_month - timedelta(days=180)
    historical_data = DriverPerformance.objects.filter(
        month__gte=six_months_ago,
        month__lte=current_month
    ).values('month').annotate(
        avg_success_rate=Avg('success_rate'),
        total_deliveries=Sum('total_deliveries')
    ).order_by('month')
    
    context = {
        'current_month': current_month,
        'month_performance': month_performance,
        'top_by_success': top_by_success,
        'top_by_volume': top_by_volume,
        'top_by_revenue': top_by_revenue,
        'stats': stats,
        'historical_data': list(historical_data),
    }
    
    return render(request, 'analytics/drivers_performance_dashboard.html', context)


@login_required
def incidents_report(request):
    """
    Relatório de incidências (top motivos de falha).
    """
    # Período padrão: últimos 30 dias
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    # Top motivos de falha em pedidos
    order_incidents = OrderIncident.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).values('incident_type', 'description').annotate(
        count=Count('id'),
        affected_orders=Count('order', distinct=True)
    ).order_by('-count')[:20]
    
    # Incidências por partner
    incidents_by_partner = OrderIncident.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).values('order__partner__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Incidências de veículos
    vehicle_incidents = VehicleIncident.objects.filter(
        incident_date__gte=start_date,
        incident_date__lte=end_date
    ).values('incident_type').annotate(
        count=Count('id'),
        total_cost=Sum('fine_amount')
    ).order_by('-count')
    
    # Estatísticas gerais
    total_order_incidents = OrderIncident.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).count()
    
    total_vehicle_incidents = VehicleIncident.objects.filter(
        incident_date__gte=start_date,
        incident_date__lte=end_date
    ).count()
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'order_incidents': order_incidents,
        'incidents_by_partner': incidents_by_partner,
        'vehicle_incidents': vehicle_incidents,
        'total_order_incidents': total_order_incidents,
        'total_vehicle_incidents': total_vehicle_incidents,
    }
    
    return render(request, 'analytics/incidents_report.html', context)


@login_required
def vehicles_performance_report(request):
    """
    Relatório de performance de veículos (Custo x Entregas).
    """
    # Período padrão: últimos 30 dias
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    # Performance por veículo
    vehicles = Vehicle.objects.filter(
        status='ACTIVE'
    ).annotate(
        # Contar atribuições (assignments)
        total_shifts=Count('assignments', distinct=True, filter=Q(
            assignments__date__gte=start_date,
            assignments__date__lte=end_date
        )),
        # Custo total de manutenções
        maintenance_cost=Sum(
            'maintenances__cost',
            filter=Q(
                maintenances__date__gte=start_date,
                maintenances__date__lte=end_date
            )
        ),
        # Custo de incidentes
        incident_cost=Sum(
            'incidents__fine_amount',
            filter=Q(
                incidents__incident_date__gte=start_date,
                incidents__incident_date__lte=end_date
            )
        ),
        # Número de incidentes
        incident_count=Count(
            'incidents',
            filter=Q(
                incidents__incident_date__gte=start_date,
                incidents__incident_date__lte=end_date
            )
        )
    ).order_by('-total_shifts')
    
    # Calcular custo total e custo por shift
    vehicles_data = []
    for vehicle in vehicles:
        maintenance = vehicle.maintenance_cost or Decimal('0')
        incidents = vehicle.incident_cost or Decimal('0')
        total_cost = maintenance + incidents
        cost_per_shift = total_cost / vehicle.total_shifts if vehicle.total_shifts > 0 else Decimal('0')
        
        vehicles_data.append({
            'vehicle': vehicle,
            'total_shifts': vehicle.total_shifts,
            'maintenance_cost': maintenance,
            'incident_cost': incidents,
            'total_cost': total_cost,
            'cost_per_shift': cost_per_shift,
            'incident_count': vehicle.incident_count,
        })
    
    # Ordenar por custo total (decrescente)
    vehicles_data.sort(key=lambda x: x['total_cost'], reverse=True)
    
    # Estatísticas gerais
    total_vehicles = len(vehicles_data)
    total_cost = sum(v['total_cost'] for v in vehicles_data)
    avg_cost_per_vehicle = total_cost / total_vehicles if total_vehicles > 0 else Decimal('0')
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'vehicles_data': vehicles_data,
        'total_vehicles': total_vehicles,
        'total_cost': total_cost,
        'avg_cost_per_vehicle': avg_cost_per_vehicle,
    }
    
    return render(request, 'analytics/vehicles_performance_report.html', context)


# ============================================================================
# API ENDPOINTS (JSON) para gráficos dinâmicos
# ============================================================================

@login_required
def api_metrics_data(request):
    """API endpoint para dados de métricas (JSON)."""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    partner_id = request.GET.get('partner')
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    metrics_query = DailyMetrics.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    )
    
    if partner_id:
        metrics_query = metrics_query.filter(partner_id=partner_id)
    
    data = list(metrics_query.values('date').annotate(
        total_orders=Sum('total_orders'),
        delivered=Sum('delivered_orders'),
        failed=Sum('failed_orders'),
        revenue=Sum('total_revenue'),
        success_rate=Avg('success_rate')
    ).order_by('date'))
    
    # Converter date para string
    for item in data:
        item['date'] = item['date'].isoformat()
        item['revenue'] = float(item['revenue'] or 0)
        item['success_rate'] = float(item['success_rate'] or 0)
    
    return JsonResponse({'data': data})


@login_required
def api_forecasts_data(request):
    """API endpoint para dados de previsões (JSON)."""
    end_date = timezone.now().date()
    start_date = end_date
    forecast_end = end_date + timedelta(days=30)
    
    partner_id = request.GET.get('partner')
    method = request.GET.get('method', 'BEST')
    
    forecasts_query = VolumeForecast.objects.filter(
        forecast_date__gte=start_date,
        forecast_date__lte=forecast_end
    )
    
    if partner_id:
        forecasts_query = forecasts_query.filter(partner_id=partner_id)
    
    if method == 'BEST':
        forecasts_query = forecasts_query.filter(method='MA7')
    else:
        forecasts_query = forecasts_query.filter(method=method)
    
    data = list(forecasts_query.values(
        'forecast_date', 'predicted_volume', 'lower_bound', 'upper_bound', 'method'
    ).order_by('forecast_date'))
    
    for item in data:
        item['forecast_date'] = item['forecast_date'].isoformat()
        item['predicted_volume'] = float(item['predicted_volume'])
        item['lower_bound'] = float(item['lower_bound'] or 0)
        item['upper_bound'] = float(item['upper_bound'] or 0)
    
    return JsonResponse({'data': data})


@login_required
def api_alerts_data(request):
    """API endpoint para dados de alertas (JSON)."""
    status = request.GET.get('status', 'ACTIVE')
    
    alerts = PerformanceAlert.objects.filter(status=status)
    
    data = list(alerts.values(
        'alert_type', 'severity', 'message', 'created_at', 'partner__name'
    ).order_by('-created_at')[:50])
    
    for item in data:
        item['created_at'] = item['created_at'].isoformat()
    
    return JsonResponse({'data': data})


@login_required
def api_drivers_data(request):
    """API endpoint para dados de motoristas (JSON)."""
    today = timezone.now().date()
    current_month = today.replace(day=1)
    
    month_param = request.GET.get('month')
    if month_param:
        current_month = datetime.strptime(month_param, '%Y-%m').date().replace(day=1)
    
    drivers = DriverPerformance.objects.filter(
        month=current_month
    ).select_related('driver').values(
        'driver__nome_completo',
        'total_deliveries',
        'success_rate',
        'total_earnings',
        'rank_in_team'
    ).order_by('-rank_in_team')
    
    data = list(drivers)
    
    for item in data:
        item['success_rate'] = float(item['success_rate'] or 0)
        item['total_earnings'] = float(item['total_earnings'] or 0)
    
    return JsonResponse({'data': data})


# ============================================================================
# EXPORTAÇÕES (Excel e PDF)
# ============================================================================

@login_required
def export_metrics_excel(request):
    """Exportar métricas para Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill
    except ImportError:
        return HttpResponse(
            'Biblioteca openpyxl não instalada. Execute: pip install openpyxl',
            status=500
        )
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    partner_id = request.GET.get('partner')
    
    metrics_query = DailyMetrics.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    )
    
    if partner_id:
        metrics_query = metrics_query.filter(partner_id=partner_id)
    
    metrics = metrics_query.order_by('date')
    
    # Criar workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Métricas Diárias'
    
    # Cabeçalhos
    headers = [
        'Data', 'Parceiro', 'Total Pedidos', 'Entregues', 'Falhados',
        'Taxa Sucesso (%)', 'Receita (€)', 'Bónus (€)', 'Penalidades (€)',
        'Motoristas Ativos', 'Veículos Ativos'
    ]
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        cell.font = Font(bold=True, color='FFFFFF')
        cell.alignment = Alignment(horizontal='center')
    
    # Dados
    for row, metric in enumerate(metrics, 2):
        ws.cell(row=row, column=1, value=metric.date.strftime('%d/%m/%Y'))
        ws.cell(row=row, column=2, value=metric.partner.name)
        ws.cell(row=row, column=3, value=metric.total_orders)
        ws.cell(row=row, column=4, value=metric.delivered_orders)
        ws.cell(row=row, column=5, value=metric.failed_orders)
        ws.cell(row=row, column=6, value=float(metric.success_rate))
        ws.cell(row=row, column=7, value=float(metric.total_revenue))
        ws.cell(row=row, column=8, value=float(metric.total_bonuses))
        ws.cell(row=row, column=9, value=float(metric.total_penalties))
        ws.cell(row=row, column=10, value=metric.active_drivers_count)
        ws.cell(row=row, column=11, value=metric.active_vehicles_count)
    
    # Ajustar largura das colunas
    for col in range(1, 12):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 15
    
    # Preparar resposta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="metricas_{start_date}_{end_date}.xlsx"'
    
    wb.save(response)
    return response


@login_required
def export_drivers_excel(request):
    """Exportar performance de motoristas para Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill
    except ImportError:
        return HttpResponse(
            'Biblioteca openpyxl não instalada. Execute: pip install openpyxl',
            status=500
        )
    
    today = timezone.now().date()
    current_month = today.replace(day=1)
    
    month_param = request.GET.get('month')
    if month_param:
        current_month = datetime.strptime(month_param, '%Y-%m').date().replace(day=1)
    
    drivers = DriverPerformance.objects.filter(
        month=current_month
    ).select_related('driver').order_by('-rank_in_team')
    
    # Criar workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'Performance {current_month.strftime("%m-%Y")}'
    
    # Cabeçalhos
    headers = [
        'Ranking', 'Motorista', 'Total Entregas', 'Entregas com Sucesso',
        'Entregas Falhadas', 'Taxa Sucesso (%)', 'Tempo Médio (h)',
        'Receita Total (€)', 'Bónus (€)', 'Penalidades (€)', 'Ganhos Liquidos (€)'
    ]
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        cell.font = Font(bold=True, color='FFFFFF')
        cell.alignment = Alignment(horizontal='center')
    
    # Dados
    for row, perf in enumerate(drivers, 2):
        driver_name = f"{perf.driver.user.first_name} {perf.driver.user.last_name}"
        
        ws.cell(row=row, column=1, value=perf.ranking)
        ws.cell(row=row, column=2, value=driver_name)
        ws.cell(row=row, column=3, value=perf.total_deliveries)
        ws.cell(row=row, column=4, value=perf.successful_deliveries)
        ws.cell(row=row, column=5, value=perf.failed_deliveries)
        ws.cell(row=row, column=6, value=float(perf.success_rate))
        ws.cell(row=row, column=7, value=float(perf.average_delivery_time or 0))
        ws.cell(row=row, column=8, value=float(perf.total_earnings))
        ws.cell(row=row, column=9, value=float(perf.total_bonuses))
        ws.cell(row=row, column=10, value=float(perf.total_penalties))
        ws.cell(row=row, column=11, value=float(perf.net_earnings))
    
    # Ajustar largura das colunas
    for col in range(1, 12):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18
    
    # Preparar resposta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="motoristas_{current_month.strftime("%m_%Y")}.xlsx"'
    
    wb.save(response)
    return response


@login_required
def export_report_pdf(request):
    """Exportar relatório consolidado em PDF."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from io import BytesIO
    except ImportError:
        return HttpResponse(
            'Biblioteca reportlab não instalada. Execute: pip install reportlab',
            status=500
        )
    
    # Criar PDF em memória
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title = Paragraph('Relatório de Analytics - Léguas Franzinas', styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.5 * cm))
    
    # Período
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    period = Paragraph(
        f'Período: {start_date.strftime("%d/%m/%Y")} - {end_date.strftime("%d/%m/%Y")}',
        styles['Normal']
    )
    elements.append(period)
    elements.append(Spacer(1, 0.5 * cm))
    
    # Métricas totais
    metrics = DailyMetrics.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).aggregate(
        total_orders=Sum('total_orders'),
        delivered=Sum('delivered_orders'),
        failed=Sum('failed_orders'),
        revenue=Sum('total_revenue')
    )
    
    data = [
        ['Métrica', 'Valor'],
        ['Total de Pedidos', str(metrics['total_orders'] or 0)],
        ['Pedidos Entregues', str(metrics['delivered'] or 0)],
        ['Pedidos Falhados', str(metrics['failed'] or 0)],
        ['Receita Total', f"€{metrics['revenue'] or 0:.2f}"],
    ]
    
    table = Table(data, colWidths=[10 * cm, 5 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    
    # Gerar PDF
    doc.build(elements)
    
    # Preparar resposta
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_{start_date}_{end_date}.pdf"'
    
    return response
