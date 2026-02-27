from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView
from django.utils import timezone
#from api_paack import models
from django.db.models import Count, Sum, Case, When, IntegerField, Q, Avg
from django.db.models.functions import TruncDate, TruncWeek
from django.views.generic import TemplateView
from ordersmanager_paack.models import Order as apiOrder
from ordersmanager_paack.models import Dispatch as apiDispatch
from ordersmanager_paack.sync_service import SyncService
from django.db.models import F, FloatField
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
import re
import json
import os
from django.http import HttpResponse, FileResponse, Http404
from django.contrib import messages
from customauth.models import DriverAccess


class DashboardDataService:
    def __init__(self, request):
        self.request = request
        self.date_params = self._get_date_params()
        self.filter_date = self.date_params['filter_date']
        self.start_date = self.date_params['start_date']
        self.end_date = self.date_params['end_date']
        self.date_range_mode = self.date_params['date_range_mode']
        self.is_today = self._check_is_today()
        self.filter_date_obj = self._get_filter_date_as_date()
        self.start_date_obj = self._get_start_date_as_date()
        self.end_date_obj = self._get_end_date_as_date()

    def _get_date_params(self):
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        filter_date = self.request.GET.get('filter_date')
        
        # Determinar se estamos em modo de intervalo
        date_range_mode = bool(start_date or end_date)
        
        if date_range_mode:
            # Modo intervalo: usar start_date e end_date
            if not start_date:
                start_date = timezone.now().date().strftime('%Y-%m-%d')
            if not end_date:
                end_date = start_date  # Se não tiver end_date, usar start_date
            filter_date = None  # Limpar filter_date no modo intervalo
        else:
            # Modo data única: usar filter_date
            if not filter_date:
                filter_date = timezone.now().date().strftime('%Y-%m-%d')
            start_date = None
            end_date = None
        
        return {
            'filter_date': filter_date,
            'start_date': start_date,
            'end_date': end_date,
            'date_range_mode': date_range_mode
        }

    def _check_is_today(self):
        today = timezone.now().date().strftime('%Y-%m-%d')
        if self.date_range_mode:
            # Em modo intervalo, só é "hoje" se o intervalo for apenas o dia de hoje
            return self.start_date == today and self.end_date == today
        else:
            return self.filter_date == today 
    
    def _get_filter_date_as_date(self):
        """Converte o filter_date de string para objeto date"""
        if self.filter_date:
            return timezone.datetime.strptime(self.filter_date, '%Y-%m-%d').date()
        return timezone.now().date()

    def _get_start_date_as_date(self):
        """Converte o start_date de string para objeto date"""
        if self.start_date:
            return timezone.datetime.strptime(self.start_date, '%Y-%m-%d').date()
        return None

    def _get_end_date_as_date(self):
        """Converte o end_date de string para objeto date"""
        if self.end_date:
            return timezone.datetime.strptime(self.end_date, '%Y-%m-%d').date()
        return None

    def _get_date_filter_for_queries(self):
        """Retorna o filtro de data apropriado para as queries (compatível com timezone MySQL)"""
        if self.date_range_mode:
            # Para intervalos, usar range com datetime completo
            from django.utils import timezone
            start_datetime = timezone.datetime.combine(self.start_date_obj, timezone.datetime.min.time())
            end_datetime = timezone.datetime.combine(self.end_date_obj, timezone.datetime.max.time())
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
            return {
                'dispatch_time__range': [start_datetime, end_datetime]
            }
        else:
            # Para data única, usar range do dia completo
            from django.utils import timezone
            start_datetime = timezone.datetime.combine(self.filter_date_obj, timezone.datetime.min.time())
            end_datetime = timezone.datetime.combine(self.filter_date_obj, timezone.datetime.max.time())
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
            return {
                'dispatch_time__range': [start_datetime, end_datetime]
            }

    def _get_orders_by_dispatch_date(self):
        """Retorna a contagem de orders por data de dispatch com estatísticas de status (compatível com MySQL)"""
        from django.db.models import DateField
        from django.db.models.functions import Cast
        if self.date_range_mode:
            date_filter = self._get_date_filter_for_queries()
            dispatch_counts = (
                apiDispatch.objects
                .filter(**date_filter)
                .annotate(dispatch_date=Cast('dispatch_time', output_field=DateField()))
                .values('dispatch_date')
                .annotate(
                    total=Count('id'),
                    delivered=Count(
                        Case(
                            When(order__status='delivered', then=1),
                            output_field=IntegerField()
                        )
                    ),
                    failed=Count(
                        Case(
                            When(order__simplified_order_status__in=['failed', 'undelivered'], then=1),
                            output_field=IntegerField()
                        )
                    ),
                    pending=Count(
                        Case(
                            When(order__simplified_order_status='to_attempt', then=1),
                            output_field=IntegerField()
                        )
                    )
                )
                .annotate(
                    success_rate=Case(
                        When(total__gt=0, then=(100.0 * F('delivered') / F('total'))),
                        default=0,
                        output_field=FloatField()
                    )
                )
                .order_by('-dispatch_date')
            )
        else:
            end_date = self.filter_date_obj
            start_date = end_date - timedelta(days=14)
            # Converter para datetime range para compatibilidade com timezone
            from django.utils import timezone
            start_datetime = timezone.datetime.combine(start_date, timezone.datetime.min.time())
            end_datetime = timezone.datetime.combine(end_date, timezone.datetime.max.time())
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
            dispatch_counts = (
                apiDispatch.objects
                .filter(dispatch_time__range=[start_datetime, end_datetime])
                .annotate(dispatch_date=Cast('dispatch_time', output_field=DateField()))
                .values('dispatch_date')
                .annotate(
                    total=Count('id'),
                    delivered=Count(
                        Case(
                            When(order__status='delivered', then=1),
                            output_field=IntegerField()
                        )
                    ),
                    failed=Count(
                        Case(
                            When(order__simplified_order_status__in=['failed', 'undelivered'], then=1),
                            output_field=IntegerField()
                        )
                    ),
                    pending=Count(
                        Case(
                            When(order__simplified_order_status='to_attempt', then=1),
                            output_field=IntegerField()
                        )
                    )
                )
                .annotate(
                    success_rate=Case(
                        When(total__gt=0, then=(100.0 * F('delivered') / F('total'))),
                        default=0,
                        output_field=FloatField()
                    )
                )
                .order_by('-dispatch_date')
            )
        return dispatch_counts

    def get_dispatches_by_date(self):
        """Retorna detalhes de dispatches para a data(s) filtrada(s)"""
        date_filter = self._get_date_filter_for_queries()
        return apiDispatch.objects.filter(
            **date_filter
        ).select_related('driver', 'order')
    
    def get_dispatch_metrics(self):
        """Retorna métricas de dispatch para a data(s) filtrada(s)"""
        date_filter = self._get_date_filter_for_queries()
        
        # Métricas por status de order
        metrics = apiDispatch.objects.filter(
            **date_filter
        ).aggregate(
            total=Count('id'),
            delivered=Count(
                Case(
                    When(order__status='delivered', then=1),
                    output_field=IntegerField()
                )
            ),
            failed=Count(
                Case(
                    When(order__simplified_order_status__in=['failed', 'undelivered'], then=1),
                    output_field=IntegerField()
                )
            ),
            pending=Count(
                Case(
                    When(order__simplified_order_status='to_attempt', then=1),
                    output_field=IntegerField()
                )
            ),
            recovered=Count(
                Case(
                    When(recovered=True, then=1),
                    output_field=IntegerField()
                )
            )
        )
        
        # Calcular taxa de sucesso
        if metrics['total'] > 0:
            metrics['success_rate'] = round((metrics['delivered'] / metrics['total']) * 100, 2)
        else:
            metrics['success_rate'] = 0
            
        return metrics
    
    def get_best_driver(self):
        """Retorna o melhor motorista do período com base na taxa de sucesso"""
        date_filter = self._get_date_filter_for_queries()
        
        best_driver_data = (
            apiDispatch.objects
            .filter(**date_filter)
            .select_related('driver')
            .values('driver')
            .annotate(
                total_dispatches=Count('id'),
                total_delivered=Count(
                    Case(When(order__status='delivered', then=1), output_field=IntegerField())
                )
            )
            .annotate(
                driver_success_rate=Case(
                    When(total_dispatches__gt=0, then=(100.0 * F('total_delivered') / F('total_dispatches'))),
                    default=0,
                    output_field=FloatField()
                )
            )
            .filter(total_dispatches__gte=5)  # Mínimo de 5 entregas para ser considerado
            .order_by('-driver_success_rate', '-total_delivered')
            .first()
        )
        
        if not best_driver_data:
            return None
        
        # Buscar o objeto driver completo
        best_driver = apiDispatch.objects.filter(
            driver=best_driver_data['driver'],
            **date_filter
        ).select_related('driver').first()
        
        if not best_driver:
            return None
        
        # Classe para emular a estrutura do objeto original
        class DriverClass:
            def __init__(self, name, id):
                self.name = name
                self.id = id
                
        class DriverWrapper:
            def __init__(self, driver_obj):
                clean_name = self._extract_driver_name(driver_obj.driver.name)
                self.driver = DriverClass(clean_name, driver_obj.driver.id)
                self.success_rate = best_driver_data['driver_success_rate']
                self.total_dispatches = best_driver_data['total_dispatches']
                self.total_delivered = best_driver_data['total_delivered']
                
            def _extract_driver_name(self, full_name):
                # Métodos simplificados para extrair apenas o nome
                if not full_name:
                    return "N/A"
                
                # Remove códigos e prefixos comuns
                parts = full_name.split()
                if len(parts) <= 2:
                    return full_name
                
                # Padrão para identificar nomes próprios
                # Filtra os componentes que parecem ser nomes próprios
                name_parts = [p for p in parts 
                              if len(p) > 2 and p[0].isupper() 
                              and not p.isupper() 
                              and p not in ['OPO', 'LF', 'SC', 'LMO']]
                
                # Se não houver nomes próprios identificados, use as 2 últimas palavras
                if not name_parts:
                    return ' '.join(parts[-2:])
                
                return ' '.join(name_parts)
                
        return DriverWrapper(best_driver)
    

    
    def get_weekly_efficiency(self):
        """Calcula a eficiência semanal baseada no período selecionado (compatível com MySQL)"""
        from django.db.models import DateField
        from django.db.models.functions import Cast
        from django.utils import timezone
        
        if self.date_range_mode:
            start_date = self.start_date_obj
            end_date = self.end_date_obj
        else:
            start_date = self.filter_date_obj - timedelta(days=6)
            end_date = self.filter_date_obj
            
        # Converter para datetime range para compatibilidade com timezone
        start_datetime = timezone.datetime.combine(start_date, timezone.datetime.min.time())
        end_datetime = timezone.datetime.combine(end_date, timezone.datetime.max.time())
        start_datetime = timezone.make_aware(start_datetime)
        end_datetime = timezone.make_aware(end_datetime)
        
        daily_stats = (
            apiDispatch.objects
            .filter(dispatch_time__range=[start_datetime, end_datetime])
            .annotate(date=Cast('dispatch_time', output_field=DateField()))
            .values('date')
            .annotate(
                total=Count('id'),
                delivered=Count(
                    Case(When(order__status='delivered', then=1), output_field=IntegerField())
                )
            )
            .annotate(
                success_rate=Case(
                    When(total__gt=0, then=(100.0 * F('delivered') / F('total'))),
                    default=0,
                    output_field=FloatField()
                )
            )
        )
        if not daily_stats:
            return 0
        total_success_rate = sum(day['success_rate'] for day in daily_stats)
        return round(total_success_rate / len(daily_stats), 2)
    
    def get_total_orders_description(self):
        """Retorna uma descrição para o card de total de pedidos"""
        if self.date_range_mode:
            if self.start_date_obj == self.end_date_obj:
                return f"Pedidos em {self.start_date_obj.strftime('%d/%m/%Y')}"
            else:
                return f"Pedidos do período ({self.start_date_obj.strftime('%d/%m')} a {self.end_date_obj.strftime('%d/%m')})"
        elif self.is_today:
            return "Pedidos de hoje"
        else:
            return f"Pedidos em {self.filter_date_obj.strftime('%d/%m/%Y')}"
    
    def get_hourly_dispatch_distribution(self):
        """Retorna a distribuição de dispatches por hora do período (compatível com MySQL)"""
        from django.db.models.functions import ExtractHour
        date_filter = self._get_date_filter_for_queries()
        hourly_distribution = (
            apiDispatch.objects
            .filter(**date_filter)
            .annotate(hour=ExtractHour('dispatch_time'))
            .values('hour')
            .annotate(
                total=Count('id'),
                delivered=Count(
                    Case(
                        When(order__status='delivered', then=1),
                        output_field=IntegerField()
                    )
                )
            )
            .order_by('hour')
        )
        formatted_distribution = []
        for hour_data in hourly_distribution:
            hour = hour_data['hour']
            # Verificar se hour não é None antes de formatar
            if hour is None:
                continue
            hour_label = f"{hour:02d}:00 - {hour+1:02d}:00"
            formatted_distribution.append({
                'hour': hour,
                'hour_label': hour_label,
                'total': hour_data['total'],
                'delivered': hour_data['delivered'],
                'success_rate': round((hour_data['delivered'] / hour_data['total'] * 100), 2) if hour_data['total'] > 0 else 0
            })
        return formatted_distribution
    
    def _extract_driver_name(self, full_name):
        """
        Extrai o nome do motorista a partir do nome completo com códigos
        Exemplos: 
        - 'SC OPO LF M Michel Oliveira LMO' -> 'Michel Oliveira'
        - 'OPO LF M Michel Oliveira' -> 'Michel Oliveira'
        """
        if not full_name:
            return "N/A"
            
        # Lista de códigos e prefixos comuns que devem ser removidos
        prefixos = ['SC', 'OPO', 'LF', 'M', 'D', 'LX', 'Porto', 'Lisboa', 'FCO', 'PRT']
        sufixos = ['LMO', 'XYZ', 'ABC', 'IJK']
        
        # Abordagem mais rigorosa para extrair apenas o nome real
        nome_limpo = full_name
        
        # 1. Separar as palavras
        parts = full_name.split()
        
        # 2. Identificar partes que podem ser um nome real (letra maiúscula seguida de minúsculas)
        # A maioria dos nomes próprios tem esse padrão
        nome_candidato = []
        iniciou_nome = False
        
        # Primeiro, vamos tentar identificar padrões de nomes próprios
        for i, part in enumerate(parts):
            # Verifica se é um prefixo conhecido para ignorar
            if part in prefixos:
                continue
                
            # Verifica se parece um nome próprio (primeira letra maiúscula, resto minúsculo)
            is_proper_name = len(part) > 2 and part[0].isupper() and not part.isupper()
            
            # Se já iniciamos o nome ou encontramos um candidato a nome próprio
            if iniciou_nome or is_proper_name:
                iniciou_nome = True
                nome_candidato.append(part)
        
        # Se identificamos candidatos a nomes
        if nome_candidato:
            # Remover possíveis sufixos (códigos no final que são todas letras maiúsculas)
            if nome_candidato and nome_candidato[-1].isupper() and len(nome_candidato[-1]) <= 3:
                nome_candidato.pop()
                
            # Remover sufixos conhecidos
            if nome_candidato and nome_candidato[-1] in sufixos:
                nome_candidato.pop()
                
            nome_limpo = ' '.join(nome_candidato)
        
        # Se a abordagem acima não funcionou, vamos usar uma regra mais simples
        if not nome_candidato or len(nome_limpo) < 5:
            # Remover prefixos conhecidos
            cleaned_parts = [p for p in parts if p not in prefixos and len(p) > 1]
            
            # Se ainda temos muitas partes, assumir que as últimas 2-3 são o nome real
            if len(cleaned_parts) > 3:
                nome_limpo = ' '.join(cleaned_parts[-3:])
            else:
                nome_limpo = ' '.join(cleaned_parts)
        
        # Última verificação: se começamos com letras maiúsculas isoladas seguidas de espaço,
        # remova-as pois provavelmente são iniciais ou códigos
        nome_limpo = re.sub(r'^([A-Z]\s)+', '', nome_limpo).strip()
        
        # Se ainda não conseguimos extrair um nome decente, use as duas últimas partes
        if len(nome_limpo.split()) < 2 and len(parts) >= 2:
            nome_limpo = ' '.join(parts[-2:])
            
        return nome_limpo

    def _driver_sucess_chart(self):
        """Retorna dados para o gráfico de sucesso dos motoristas"""
        date_filter = self._get_date_filter_for_queries()
        
        driver_success_data = (
            apiDispatch.objects
            .filter(**date_filter)
            .values('driver', 'driver__name')
            .annotate(
                total_attempts=Count('id'),
                deliveries=Count(
                    Case(When(order__status='delivered', then=1), output_field=IntegerField())
                ),
                fails=Count(
                    Case(When(order__simplified_order_status__in=['failed', 'undelivered'], then=1),
                        output_field=IntegerField())
                )
            )
            .annotate(
                success_rate=Case(
                    When(total_attempts__gt=0, then=(100.0 * F('deliveries') / F('total_attempts'))),
                    default=0,
                    output_field=FloatField()
                )
            )
            .filter(total_attempts__gte=1)
            .order_by('-success_rate')
        )

        formatted_data = []
        for data in driver_success_data:
            driver_name = self._extract_driver_name(data['driver__name'])

            # Buscar pendentes
            pending_count = apiDispatch.objects.filter(
                driver=data['driver'],
                **date_filter,
                order__simplified_order_status='to_attempt'
            ).count()

            # Total real
            real_total_attempts = data['deliveries'] + data['fails'] + pending_count

            if real_total_attempts > 0:
                success_pct = 100.0 * data['deliveries'] / real_total_attempts
                fails_pct = 100.0 * data['fails'] / real_total_attempts
                pending_pct = 100.0 * pending_count / real_total_attempts
            else:
                success_pct = fails_pct = pending_pct = 0

            # Buscar imagem de perfil
            profile_img_url = self.get_driver_profile_image(data['driver'])
            
            formatted_data.append({
                'name': driver_name,
                'deliveries': data['deliveries'],
                'fails': data['fails'],
                'pending': pending_count,
                'real_total_attempts': real_total_attempts,
                'success_pct': round(success_pct, 2),
                'fails_pct': round(fails_pct, 2),
                'pending_pct': round(pending_pct, 2),
                'driver_id': data['driver'],
                'profile_picture': profile_img_url
            })

        return formatted_data

    def get_driver_profile_image(self, driver_id):
        """
        Retorna a URL da imagem de perfil para um motorista a partir do ID.
        Usado para preencher as imagens no dashboard de motoristas.
        
        Args:
            driver_id: ID do motorista no sistema
            
        Returns:
            str: URL da imagem de perfil ou None se não encontrada
        """
        try:
            # Primeiro tenta buscar um registro na tabela de acesso de motoristas
            driver_access = DriverAccess.objects.filter(driver_id=driver_id).first()
            
            # Se encontrar e tiver foto de perfil
            if driver_access and driver_access.profile_picture:
                return driver_access.profile_picture.url
            
            # Se não encontrar, retorna None
            return None
        except Exception as e:
            # Loggar o erro, mas não quebrar a aplicação
            print(f"Erro ao buscar imagem de perfil para motorista {driver_id}: {str(e)}")
            return None

       
@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):

    template_name = 'paack_dashboard/dashboard.html'

    def check_last_sync(self):
        """Verifica quando foi feito o último sync e calcula quando será possível fazer o próximo"""
        try:
            last_sync = apiDispatch.objects.order_by('-dispatch_time').first()
            if last_sync:
                last_sync_time = last_sync.dispatch_time
                now = timezone.now()
                time_diff = now - last_sync_time
                
                # Se passaram menos de 10 minutos
                if time_diff.total_seconds() < 600:  # 10 minutos em segundos
                    next_sync = last_sync_time + timedelta(minutes=10)
                    return {
                        'can_sync': False,
                        'next_sync': next_sync.strftime('%H:%M:%S')
                    }
            return {'can_sync': True}
        except Exception as e:
            print(f"Erro ao verificar último sync: {str(e)}")
            return {'can_sync': True}  # Em caso de erro, permitir o sync
    
    def update_api_data(self):
        # Verifica se pode fazer o sync
        sync_check = self.check_last_sync()
        if not sync_check['can_sync']:
            return {
                'success': False,
                'message': f'O sync das informações só pode ser feito em {sync_check["next_sync"]}'
            }
            
        sync_service = SyncService()
        result = sync_service.sync_data(force_refresh=True)
        print(f'Sync feito com resultado: {result}')
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Verifica se foi solicitada uma atualização através do parâmetro na URL
        if self.request.GET.get('sync') == 'true':
            # Atualiza os dados da API
            sync_result = self.update_api_data()
            
            # Feedback ao usuário sobre a atualização dos dados
            if sync_result.get('success', False):
                messages.success(self.request, f"Dados atualizados com sucesso! Última atualização: {timezone.now().strftime('%H:%M:%S')}")
                context['data_status'] = 'updated'
            else:
                error_msg = sync_result.get('message', 'Não foi possível atualizar os dados neste momento.')
                messages.warning(self.request, f"Você pode estar vendo dados desatualizados. {error_msg}")
                context['data_status'] = 'outdated'
                context['data_error'] = error_msg
        
        data_service = DashboardDataService(self.request)
        
        context['filter_date'] = data_service.filter_date
        context['start_date'] = data_service.start_date
        context['end_date'] = data_service.end_date
        context['date_range_mode'] = data_service.date_range_mode
        
        # Mostrar current_date com base no filter_date ou intervalo
        if data_service.date_range_mode:
            context['start_date_formatted'] = data_service.start_date_obj.strftime('%d/%m/%Y')
            context['end_date_formatted'] = data_service.end_date_obj.strftime('%d/%m/%Y')
            if data_service.start_date_obj == data_service.end_date_obj:
                context['current_date'] = data_service.start_date_obj.strftime('%d/%m/%Y')
            else:
                context['current_date'] = f"{data_service.start_date_obj.strftime('%d/%m')} a {data_service.end_date_obj.strftime('%d/%m/%Y')}"
        else:
            context['current_date'] = data_service.filter_date_obj.strftime('%d/%m/%Y')
            
        context['is_today'] = data_service.is_today

        # Dados de dispatches
        context['orders_by_dispatch_date'] = data_service._get_orders_by_dispatch_date()
        context['dispatch_data'] = data_service.get_dispatches_by_date()
        context['dispatch_metrics'] = data_service.get_dispatch_metrics()
        
        # Dados adicionais para os cards
        context['best_driver'] = data_service.get_best_driver()
        context['week_efficiency'] = data_service.get_weekly_efficiency()
        context['total_orders_description'] = data_service.get_total_orders_description()
        
        # Distribuição horária
        context['hourly_distribution'] = data_service.get_hourly_dispatch_distribution()

        # Dados para o gráfico de sucesso dos motoristas
        context['driver_success_chart'] = data_service._driver_sucess_chart()
        
        # Garantir que os dados para o template alternativo também estejam disponíveis
        context['top_drivers_today'] = context['driver_success_chart'][:10] if context['driver_success_chart'] else []
        
        # Adicionar dados em formato JSON para uso direto por scripts JavaScript
        import json
        
        # Limpamos os dados para serialização - usando dict mais simples para evitar problemas de serialização
        serializable_data = []
        if context['driver_success_chart']:
            for item in context['driver_success_chart']:
                serializable_item = {
                    'name': item['name'],
                    'deliveries': item['deliveries'],
                    'fails': item['fails'],
                    'total_attempts': item['real_total_attempts'],
                    'success_rate': float(item['success_pct']),
                    'success_rate_display': f"{item['success_pct']:.1f}%"
                }
                serializable_data.append(serializable_item)
                
        # Usar json.dumps com opções para garantir JSON válido
        context['driver_success_chart_json'] = json.dumps(
            serializable_data, 
            ensure_ascii=False,    # Garantir que caracteres UTF-8 são mantidos
            separators=(',', ':')  # Remover espaços extras para compactar o JSON
        )

        return context

@method_decorator(login_required, name='dispatch')
class DriversManagementView(TemplateView):
    template_name = 'paack_dashboard/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_service = DashboardDataService(self.request)
        context['filter_date'] = data_service.filter_date
        context['start_date'] = data_service.start_date
        context['end_date'] = data_service.end_date
        context['date_range_mode'] = data_service.date_range_mode
        context['is_today'] = data_service.is_today
        
        # Adicionar métricas de dispatch ao contexto
        context['dispatch_metrics'] = data_service.get_dispatch_metrics()
        
        return context

@method_decorator(login_required, name='dispatch')
class DebugWeeklyEfficiencyView(TemplateView):

    template_name = 'paack_dashboard/debug_week_efficiency.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Inicializar data de destino (hoje ou data do parâmetro)
        date_filter = self.request.GET.get('date')
        if date_filter:
            target_date = timezone.datetime.strptime(date_filter, '%Y-%m-%d').date()
        else:
            target_date = timezone.now().date()
            
        # Calcular início da semana (domingo a sábado)
        # 6 = domingo, 0 = segunda, 1 = terça, etc.
        days_to_subtract = target_date.weekday() + 1
        if days_to_subtract == 7:  # Se hoje for domingo (6), não subtrair nada
            days_to_subtract = 0
        week_start = target_date - timedelta(days=days_to_subtract)
        
        # Calcular fim da semana (sábado)
        # Se a data alvo for sábado, então o fim da semana é a própria data
        week_end = target_date if target_date.weekday() == 5 else week_start + timedelta(days=6)
        
        # Preparar dados para debug
        valid_rates = []
        week_data = []
        
        current_day = week_start
        while current_day <= week_end:
            # Cálculos do dia com apiDispatch para manter consistência com o resto do dashboard
            day_deliveries = apiDispatch.objects.filter(
                dispatch_time__date=current_day,
                order__status='delivered'
            ).count()
            
            day_fails = apiDispatch.objects.filter(
                dispatch_time__date=current_day,
                order__simplified_order_status__in=['failed', 'undelivered']
            ).count()
            
            day_pending = apiDispatch.objects.filter(
                dispatch_time__date=current_day,
                order__simplified_order_status='to_attempt'
            ).count()
            
            day_total = day_deliveries + day_fails + day_pending
            
            # Calcular taxa de sucesso para o dia
            if day_total > 0:
                day_success_rate = (day_deliveries / day_total) * 100
                if day_deliveries + day_fails > 0:  # Somente se houver entregas concluídas
                    valid_rates.append(day_success_rate)
            else:
                day_success_rate = 0
                
            # Adicionar dados do dia à lista
            week_data.append({
                'date': current_day.strftime('%Y-%m-%d'),
                'weekday': current_day.strftime('%A'),  # Nome do dia da semana
                'deliveries': day_deliveries,
                'fails': day_fails,
                'pending': day_pending,
                'total': day_total,
                'success_rate': day_success_rate,
                'is_today': current_day == target_date
            })
            
            current_day += timedelta(days=1)
        
        # Calcular eficiência da semana
        sum_rates = sum(valid_rates) if valid_rates else 0
        count_days = len(valid_rates)
        week_efficiency = sum_rates / count_days if count_days > 0 else 0
        
        # Adicionar dados ao contexto
        context['target_date'] = target_date
        context['week_start'] = week_start
        context['week_end'] = week_end
        context['week_data'] = week_data
        context['valid_rates'] = valid_rates
        context['sum_rates'] = sum_rates
        context['count_days'] = count_days
        context['week_efficiency'] = week_efficiency
        
        return context
        
        
@method_decorator(login_required, name='dispatch')
class AdditionalDashboardView(TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_service = DashboardDataService(self.request)
        context['filter_date'] = data_service.filter_date
        context['start_date'] = data_service.start_date
        context['end_date'] = data_service.end_date
        context['date_range_mode'] = data_service.date_range_mode
        context['is_today'] = data_service.is_today
        
        # Calcular a eficiência semanal
        context['weekly_efficiency'] = data_service.get_weekly_efficiency()
        
        return context


@login_required
def driver_profile_image(request, driver_id):
    """
    View para servir a imagem de perfil do motorista.
    
    Args:
        request: Objeto HttpRequest
        driver_id: ID do motorista
        
    Returns:
        FileResponse: Imagem do motorista ou uma imagem padrão
    """
    try:
        # Primeiro tenta buscar um registro na tabela de acesso de motoristas
        driver_access = DriverAccess.objects.filter(driver_id=driver_id).first()
        
        # Se encontrar e tiver foto de perfil
        if driver_access and driver_access.profile_picture:
            return FileResponse(driver_access.profile_picture.open(), content_type='image/jpeg')
        
        # Se não encontrar, tentar servir uma imagem padrão
        default_img_path = os.path.join('static', 'img', 'default-profile.png')
        if os.path.exists(default_img_path):
            return FileResponse(open(default_img_path, 'rb'), content_type='image/png')
            
        # Caso tudo falhe, retornar um erro 404
        raise Http404("Imagem não encontrada")
        
    except Exception as e:
        # Loggar o erro, mas retornar um 404 gracioso
        print(f"Erro ao servir imagem de perfil para motorista {driver_id}: {str(e)}")
        raise Http404("Erro ao processar a imagem")