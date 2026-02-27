from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import timedelta, datetime
import json

from ordersmanager_paack.models import Order, Driver, Dispatch


class DashboardCalculator:
    """
    Classe responsável pelos cálculos das métricas do dashboard.
    Centraliza a lógica de negócio para evitar duplicação de código.
    """
    
    def __init__(self, target_date=None):
        """
        Inicializa o calculador com uma data específica.
        
        Args:
            target_date (date, optional): Data para cálculos. Se None, usa data atual.
        """
        self.now = timezone.now()
        self.target_date = target_date or self.now.date()
        self.week_start = self._calculate_week_start()
    
    def _calculate_week_start(self):
        """Calcula o início da semana (segunda-feira) para a data alvo."""
        days_since_monday = self.target_date.weekday()
        return self.target_date - timedelta(days=days_since_monday)
    
    def _parse_date_filter(self, date_filter):
        """
        Converte string de data para objeto date.
        
        Args:
            date_filter (str): Data no formato 'YYYY-MM-DD'
            
        Returns:
            date: Data convertida ou data atual se inválida
        """
        if not date_filter:
            return self.now.date()
        
        try:
            return datetime.strptime(date_filter, '%Y-%m-%d').date()
        except ValueError:
            return self.now.date()
    
    def get_daily_metrics(self):
        """
        Calcula métricas do dia alvo.
        
        Returns:
            dict: Dicionário com métricas diárias
        """
        # Entregas realizadas
        deliveries = Order.objects.filter(
            actual_delivery_date=self.target_date,
            is_delivered=True,
            status='delivered'
        ).count()
        
        # Falhas
        fails = Order.objects.filter(
            actual_delivery_date=self.target_date
        ).filter(
            Q(status__in=['failed', 'returned', 'cancelled']) |
            Q(simplified_order_status__in=['failed', 'undelivered'])
        ).count()
        
        # Pendências agendadas
        to_attempt = Order.objects.filter(
            intended_delivery_date=self.target_date,
            simplified_order_status='to_attempt'
        ).count()
        
        # Recuperações
        recovered = Dispatch.objects.filter(
            recovered=True,
            dispatch_time__date=self.target_date
        ).count()
        
        # Cálculos derivados
        total_orders = deliveries + fails + to_attempt
        total_attempts = deliveries + fails
        success_rate = f"{(deliveries / total_attempts * 100):.1f}%" if total_attempts > 0 else "0.0%"
        
        return {
            'deliveries': deliveries,
            'fails': fails,
            'to_attempt': to_attempt,
            'recovered': recovered,
            'total_orders': total_orders,
            'total_attempts': total_attempts,
            'success_rate': success_rate
        }
    
    def get_weekly_metrics(self):
        """
        Calcula métricas da semana atual.
        
        Returns:
            dict: Dicionário com métricas semanais
        """
        week_end = self.target_date
        
        # Entregas da semana
        week_deliveries = Order.objects.filter(
            actual_delivery_date__gte=self.week_start,
            actual_delivery_date__lte=week_end,
            is_delivered=True,
            status='delivered'
        ).count()
        
        # Recuperações da semana
        week_recovered = Dispatch.objects.filter(
            recovered=True,
            dispatch_time__date__gte=self.week_start,
            dispatch_time__date__lte=week_end
        ).count()
        
        # Eficiência semanal (média das taxas diárias)
        week_efficiency = self._calculate_weekly_efficiency()
        
        return {
            'deliveries': week_deliveries,
            'recovered': week_recovered,
            'efficiency': week_efficiency
        }
    
    def _calculate_weekly_efficiency(self):
        """
        Calcula a eficiência semanal como média das taxas de sucesso diárias.
        
        Returns:
            str: Taxa de eficiência formatada (ex: "85.2%")
        """
        week_end = self.target_date if self.target_date.weekday() == 6 else self.target_date
        efficiency_rates = []
        current_day = self.week_start
        
        while current_day <= week_end:
            day_deliveries = Order.objects.filter(
                actual_delivery_date=current_day,
                is_delivered=True,
                status='delivered'
            ).count()
            
            day_fails = Order.objects.filter(
                actual_delivery_date=current_day
            ).filter(
                Q(status__in=['failed', 'returned', 'cancelled']) |
                Q(simplified_order_status__in=['failed', 'undelivered'])
            ).count()
            
            day_total_attempts = day_deliveries + day_fails
            
            if day_total_attempts > 0:
                day_success_rate = (day_deliveries / day_total_attempts) * 100
                efficiency_rates.append(day_success_rate)
            
            current_day += timedelta(days=1)
        
        if efficiency_rates:
            avg_efficiency = sum(efficiency_rates) / len(efficiency_rates)
            return f"{avg_efficiency:.1f}%"
        
        return "0.0%"
    
    def get_top_drivers(self, limit=10):
        """
        Obtém os melhores motoristas do dia alvo.
        
        Args:
            limit (int): Número máximo de motoristas retornados
            
        Returns:
            QuerySet: Motoristas com estatísticas anotadas
        """
        return Driver.objects.filter(
            Q(dispatch__order__actual_delivery_date=self.target_date) |
            Q(dispatch__dispatch_time__date=self.target_date)
        ).annotate(
            deliveries_count=Count(
                'dispatch__order',
                filter=Q(
                    dispatch__order__actual_delivery_date=self.target_date,
                    dispatch__order__is_delivered=True,
                    dispatch__order__status='delivered'
                ),
                distinct=True
            ),
            fails_count=Count(
                'dispatch__order',
                filter=Q(dispatch__order__actual_delivery_date=self.target_date) &
                       (Q(dispatch__order__status__in=['failed', 'returned', 'cancelled']) |
                        Q(dispatch__order__simplified_order_status__in=['failed', 'undelivered'])),
                distinct=True
            ),
            pending_count=Count(
                'dispatch__order',
                filter=Q(
                    dispatch__order__intended_delivery_date=self.target_date,
                    dispatch__order__simplified_order_status='to_attempt'
                ),
                distinct=True
            )
        ).filter(
            Q(deliveries_count__gt=0) | Q(fails_count__gt=0) | Q(pending_count__gt=0)
        ).order_by('-deliveries_count', 'fails_count')[:limit]
    
    def get_best_driver(self, drivers_queryset):
        """
        Identifica o melhor motorista baseado na taxa de sucesso.
        
        Args:
            drivers_queryset: QuerySet de motoristas com estatísticas
            
        Returns:
            str: Nome do melhor motorista com taxa de sucesso ou "—"
        """
        if not drivers_queryset:
            return "—"
        
        best_driver = None
        best_success_rate = 0
        
        # Procura motorista com pelo menos 2 tentativas e melhor taxa
        for driver in drivers_queryset:
            total_attempts = driver.deliveries_count + driver.fails_count
            if total_attempts >= 2:
                success_pct = (driver.deliveries_count / total_attempts) * 100
                if success_pct > best_success_rate:
                    best_success_rate = success_pct
                    best_driver = driver
        
        # Se não encontrou ninguém com 2+ tentativas, pega o primeiro
        if not best_driver:
            best_driver = drivers_queryset[0]
            total_attempts = best_driver.deliveries_count + best_driver.fails_count
            best_success_rate = (
                (best_driver.deliveries_count / total_attempts * 100) 
                if total_attempts > 0 else 0
            )
        
        if best_driver:
            clean_name = self._clean_driver_name(best_driver.name)
            return f"{clean_name} ({best_success_rate:.1f}%)"
        
        return "—"
    
    def get_driver_success_chart_data(self, drivers_queryset):
        """
        Gera dados para gráfico de sucesso dos motoristas.
        
        Args:
            drivers_queryset: QuerySet de motoristas com estatísticas
            
        Returns:
            list: Lista de dicionários com dados dos motoristas
        """
        chart_data = []
        
        for driver in drivers_queryset:
            total_attempts = driver.deliveries_count + driver.fails_count
            
            if total_attempts > 0:
                success_pct = (driver.deliveries_count / total_attempts) * 100
                chart_data.append({
                    'driver_name': driver.name,
                    'name': self._clean_driver_name(driver.name),
                    'success_pct': round(success_pct, 1),
                    'deliveries': driver.deliveries_count,
                    'fails': driver.fails_count,
                    'total_attempts': total_attempts,
                    'success_rate_display': f"{success_pct:.1f}%"
                })
        
        return chart_data
    
    def _clean_driver_name(self, name):
        """
        Remove prefixos/sufixos padrão dos nomes dos motoristas.
        
        Args:
            name (str): Nome completo do motorista
            
        Returns:
            str: Nome limpo
        """
        return name.replace("SC OPO LF M ", "").replace(" LMO", "").strip()


@login_required
def dashboard_view(request):
    """
    Renderiza o dashboard principal com foco nos dados do dia atual.
    Suporte para filtros por data via parâmetros GET.
    
    Template: dashboard.html
    """
    # Inicializar calculadora com data filtrada
    calculator = DashboardCalculator()
    date_filter = request.GET.get('date')
    if date_filter:
        calculator.target_date = calculator._parse_date_filter(date_filter)
        calculator.week_start = calculator._calculate_week_start()
    
    # Obter métricas
    daily_metrics = calculator.get_daily_metrics()
    weekly_metrics = calculator.get_weekly_metrics()
    top_drivers = calculator.get_top_drivers()
    best_driver = calculator.get_best_driver(top_drivers)
    driver_chart_data = calculator.get_driver_success_chart_data(top_drivers)
    
    # Preparar contexto para template
    is_today = calculator.target_date == calculator.now.date()
    total_orders_description = (
        "Pedidos processados hoje" if is_today 
        else f"Pedidos de {calculator.target_date.strftime('%d/%m/%Y')}"
    )
    
    context = {
        # Métricas diárias
        'total_orders': daily_metrics['total_orders'],
        'to_attempt': daily_metrics['to_attempt'],
        'failed': daily_metrics['fails'],
        'delivered': daily_metrics['deliveries'],
        'total_recovered': daily_metrics['recovered'],
        'success_rate': daily_metrics['success_rate'],
        
        # Métricas semanais
        'week_deliveries': weekly_metrics['deliveries'],
        'week_efficiency': weekly_metrics['efficiency'],
        'week_recovered': weekly_metrics['recovered'],
        
        # Dados dos motoristas
        'top_drivers_today': top_drivers,
        'best_driver_today': best_driver,
        'driver_success_chart': driver_chart_data,
        'driver_success_chart_json': json.dumps(driver_chart_data),
        
        # Metadados
        'current_date': calculator.target_date,
        'is_today': is_today,
        'last_updated': calculator.now.strftime('%H:%M:%S'),
        'date_filter': calculator.target_date.strftime('%Y-%m-%d'),
        'total_orders_description': total_orders_description,
    }
    
    return render(request, 'dashboard.html', context)


@login_required
def dashboard_api_view(request):
    """
    API endpoint para atualização dinâmica dos dados do dashboard.
    Suporta filtros por data via parâmetros GET.
    
    Returns:
        JsonResponse: Dados do dashboard em formato JSON
    """
    try:
        # Inicializar calculadora com data filtrada
        calculator = DashboardCalculator()
        date_filter = request.GET.get('date')
        if date_filter:
            calculator.target_date = calculator._parse_date_filter(date_filter)
            calculator.week_start = calculator._calculate_week_start()
        
        # Obter métricas
        daily_metrics = calculator.get_daily_metrics()
        weekly_metrics = calculator.get_weekly_metrics()
        top_drivers = calculator.get_top_drivers()
        best_driver = calculator.get_best_driver(top_drivers)
        driver_chart_data = calculator.get_driver_success_chart_data(top_drivers)
        
        # Preparar resposta da API
        api_data = {
            'success': True,
            'data': {
                'total_orders': daily_metrics['total_orders'],
                'to_attempt': daily_metrics['to_attempt'],
                'failed': daily_metrics['fails'],
                'delivered': daily_metrics['deliveries'],
                'total_recovered': daily_metrics['recovered'],
                'success_rate': daily_metrics['success_rate'],
                'week_deliveries': weekly_metrics['deliveries'],
                'week_efficiency': weekly_metrics['efficiency'],
                'best_driver_today': best_driver,
                'last_updated': calculator.now.strftime('%H:%M:%S'),
            },
            'chart_data': driver_chart_data,
            'driver_success_chart': driver_chart_data,  # Para compatibilidade
            'metadata': {
                'current_date': calculator.target_date.strftime('%Y-%m-%d'),
                'is_today': calculator.target_date == calculator.now.date(),
            }
        }
        
        return JsonResponse(api_data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def recovery_api(request):
    """
    API endpoint para dados de recuperação de drivers.
    
    Returns:
        JsonResponse: Dados de recuperação em formato JSON
    """
    try:
        # TODO: Implementar lógica de recuperação
        recovery_data = {
            'success': True,
            'data': {
                'total_recoveries': 0,
                'message': 'API em desenvolvimento'
            }
        }
        return JsonResponse(recovery_data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def debug_week_efficiency(request):
    """
    View de debug para verificar o cálculo da eficiência semanal.
    Útil para desenvolvimento e troubleshooting.
    
    Acesse: /management/debug-week-efficiency/
    """
    # Inicializar calculadora
    calculator = DashboardCalculator()
    date_filter = request.GET.get('date')
    if date_filter:
        calculator.target_date = calculator._parse_date_filter(date_filter)
        calculator.week_start = calculator._calculate_week_start()
    
    # Preparar dados para debug
    week_end = calculator.target_date if calculator.target_date.weekday() == 6 else calculator.target_date
    efficiency_rates = []
    daily_data = []
    
    current_day = calculator.week_start
    while current_day <= week_end:
        # Cálculos do dia
        day_deliveries = Order.objects.filter(
            actual_delivery_date=current_day,
            is_delivered=True,
            status='delivered'
        ).count()
        
        day_fails = Order.objects.filter(
            actual_delivery_date=current_day
        ).filter(
            Q(status__in=['failed', 'returned', 'cancelled']) |
            Q(simplified_order_status__in=['failed', 'undelivered'])
        ).count()
        
        day_total_attempts = day_deliveries + day_fails
        
        if day_total_attempts > 0:
            day_success_rate = (day_deliveries / day_total_attempts) * 100
            efficiency_rates.append(day_success_rate)
            status = "✅ Incluído"
            css_class = "success"
        else:
            day_success_rate = 0
            status = "⚠️ Ignorado (0 tentativas)"
            css_class = "error"
        
        daily_data.append({
            'date': current_day,
            'deliveries': day_deliveries,
            'fails': day_fails,
            'total_attempts': day_total_attempts,
            'success_rate': day_success_rate,
            'status': status,
            'css_class': css_class,
            'is_target': current_day == calculator.target_date
        })
        
        current_day += timedelta(days=1)
    
    # Calcular eficiência final
    if efficiency_rates:
        week_avg = sum(efficiency_rates) / len(efficiency_rates)
        week_efficiency = f"{week_avg:.1f}%"
    else:
        week_efficiency = "0.0%"
    
    # Gerar HTML de debug
    html = _generate_debug_html(
        calculator.target_date, 
        calculator.week_start, 
        week_end,
        daily_data, 
        efficiency_rates, 
        week_efficiency
    )
    
    return HttpResponse(html)


def _generate_debug_html(target_date, week_start, week_end, daily_data, efficiency_rates, week_efficiency):
    """
    Gera HTML para a página de debug da eficiência semanal.
    
    Args:
        target_date (date): Data alvo
        week_start (date): Início da semana
        week_end (date): Fim da semana
        daily_data (list): Dados diários
        efficiency_rates (list): Taxas de eficiência válidas
        week_efficiency (str): Eficiência semanal calculada
        
    Returns:
        str: HTML completo da página de debug
    """
    html = f"""
    <html>
    <head>
        <title>Debug Eficiência Semanal</title>
        <style>
            body {{ font-family: monospace; margin: 20px; }}
            .highlight {{ background-color: yellow; }}
            .success {{ color: green; font-weight: bold; }}
            .error {{ color: red; }}
            table {{ border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>🔍 Debug Eficiência Semanal</h1>
        <p><strong>Data alvo:</strong> {target_date} ({target_date.strftime('%A')})</p>
        <p><strong>Início da semana:</strong> {week_start} ({week_start.strftime('%A')})</p>
        <p><strong>Fim da semana:</strong> {week_end} ({week_end.strftime('%A')})</p>
        
        <h2>📊 Dados por Dia</h2>
        <table>
            <tr>
                <th>Data</th>
                <th>Dia da Semana</th>
                <th>Entregas</th>
                <th>Falhas</th>
                <th>Total Tentativas</th>
                <th>Taxa de Sucesso</th>
                <th>Status</th>
            </tr>
    """
    
    # Adicionar linhas da tabela
    for day_data in daily_data:
        highlight = "highlight" if day_data['is_target'] else ""
        html += f"""
            <tr class="{highlight}">
                <td>{day_data['date']}</td>
                <td>{day_data['date'].strftime('%A')}</td>
                <td>{day_data['deliveries']}</td>
                <td>{day_data['fails']}</td>
                <td>{day_data['total_attempts']}</td>
                <td>{day_data['success_rate']:.1f}%</td>
                <td class="{day_data['css_class']}">{day_data['status']}</td>
            </tr>
        """
    
    html += "</table>"
    
    # Seção de cálculo
    if efficiency_rates:
        html += f"""
        <h2>🧮 Cálculo da Média</h2>
        <p><strong>Taxas válidas:</strong> {[f'{rate:.1f}%' for rate in efficiency_rates]}</p>
        <p><strong>Soma:</strong> {sum(efficiency_rates):.1f}</p>
        <p><strong>Quantidade de dias:</strong> {len(efficiency_rates)}</p>
        <p><strong>Fórmula:</strong> {sum(efficiency_rates):.1f} ÷ {len(efficiency_rates)} = {sum(efficiency_rates)/len(efficiency_rates):.1f}%</p>
        <p class="success"><strong>RESULTADO FINAL:</strong> {week_efficiency}</p>
        """
    else:
        html += '<p class="error">❌ Nenhum dia com tentativas - eficiência = 0.0%</p>'
    
    # Formulário de teste
    html += f"""
        <h2>🔧 Teste com outras datas</h2>
        <form method="get">
            <label>Data (YYYY-MM-DD): 
                <input type="date" name="date" value="{target_date}" />
            </label>
            <button type="submit">Testar</button>
        </form>
        
        <hr>
        <p><small>💡 Esta view está apenas para debug. Para ver o resultado real, vá para o <a href="/management/dashboard/">Dashboard</a></small></p>
    </body>
    </html>
    """
    
    return html