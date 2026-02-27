import uuid
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Union, Any
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from ordersmanager_paack.models import Order, Dispatch, Driver

logger = logging.getLogger(__name__)

from .constants import STATUS_LABELS

class ManualCorrectionService:
    """
    Serviço para gerenciamento de correções manuais de pedidos
    """
    
    # Status válidos para orders
    VALID_STATUSES = [
        'delivered', 'on_course', 'picked_up', 
        'reached_picked_up', 'return_in_progress', 'undelivered'
    ]
    
    # Mapeamento de status para labels em português
    STATUS_LABELS = STATUS_LABELS
    
    # Tipos de correção
    CORRECTION_TYPES = {
        'ADD': 'Adição',
        'SUB': 'Subtração'
    }

    @staticmethod
    def check_manual_orders(target_date: Union[str, date], driver_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Busca as correções manuais para uma data específica
        
        Args:
            target_date: Data para buscar (formato YYYY-MM-DD ou objeto date)
            driver_id: ID do motorista (opcional)
            
        Returns:
            Dict com contagem e lista de orders
        """
        try:
            from .models import ManualCorrection
            
            # Converter string para date se necessário
            if isinstance(target_date, str):
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            
            queryset = ManualCorrection.objects.filter(created_at__date=target_date)
            
            if driver_id:
                queryset = queryset.filter(driver__driver_id=driver_id)
                
            queryset = queryset.select_related('driver', 'order', 'created_by').order_by('-created_at')
            
            orders = []
            for correction in queryset:
                order_data = {
                    'correction_id': correction.id,
                    'order_id': correction.order.order_id,
                    'order_status': correction.order.status,
                    'correction_type': correction.correction_type,
                    'created_at': correction.created_at.strftime('%H:%M:%S'),
                    'driver_name': correction.driver.name,
                    'driver_id': correction.driver.driver_id,
                    'reason': correction.reason,
                    'created_by': correction.created_by.username if correction.created_by else 'Sistema'
                }
                orders.append(order_data)
                
            return {
                'success': True,
                'count': len(orders),
                'orders': orders
            }
            
        except Exception as e:
            logger.error(f"Erro ao buscar orders manuais: {str(e)}")
            return {
                'success': False,
                'error': f'Erro ao buscar registros: {str(e)}',
                'count': 0,
                'orders': []
            }
        
    @staticmethod
    def generate_manual_order_id() -> str:
        """
        Gera um ID único para orders manuais
        
        Returns:
            String com ID único no formato MANUAL_YYYYMMDDHHMMSSSSSSSS
        """
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S%f')
        return f"MANUAL_{timestamp}"

    @classmethod
    def create_manual_records_batch(
        cls, 
        driver_id: str, 
        reason: str, 
        user, 
        quantity: int = 1, 
        is_addition: bool = True, 
        status: str = 'delivered'
    ) -> Dict[str, Any]:
        """
        Cria registros manuais em lote (Order + Dispatch + ManualCorrection)
        
        Args:
            driver_id: ID do motorista
            reason: Motivo do registro manual
            user: Usuário que está criando o registro
            quantity: Quantidade de registros a criar (default: 1)
            is_addition: True para adição, False para subtração
            status: Status da order (default: delivered)
                   
        Returns:
            Dict com resultado da operação
        """
        logger.info(f"Iniciando criação de {quantity} registros para driver_id={driver_id}")
        
        # Validações iniciais
        validation_result = cls._validate_batch_params(driver_id, reason, user, quantity, status)
        if not validation_result['success']:
            return validation_result
            
        try:
            with transaction.atomic():
                # Buscar o driver
                try:
                    driver = Driver.objects.get(driver_id=driver_id)
                except Driver.DoesNotExist:
                    return {
                        'success': False,
                        'error': f'Motorista com ID {driver_id} não encontrado.'
                    }
                
                created_records = []
                correction_type = 'ADD' if is_addition else 'SUB'
                
                for i in range(quantity):
                    logger.debug(f"Criando registro {i+1} de {quantity}")
                    
                    # Criar Order
                    order = cls._create_manual_order(status, reason)
                    logger.debug(f"Order criada com ID: {order.id}")
                    
                    # Criar Dispatch
                    dispatch = cls._create_manual_dispatch(order, driver)
                    logger.debug(f"Dispatch criado com ID: {dispatch.id}")
                    
                    # Criar ManualCorrection
                    manual_correction = cls._create_manual_correction(
                        correction_type, reason, driver, order, dispatch, user
                    )
                    logger.debug(f"ManualCorrection criada com ID: {manual_correction.id}")
                    
                    created_records.append({
                        'order_id': order.order_id,
                        'order_uuid': str(order.uuid),
                        'dispatch_id': dispatch.id,
                        'correction_id': manual_correction.id,
                        'status': status
                    })
                
                action_text = "adição" if is_addition else "subtração"
                plural_suffix = "s" if quantity > 1 else ""
                
                return {
                    'success': True,
                    'message': f'{quantity} {action_text}{plural_suffix} manual registrada{plural_suffix} com sucesso!',
                    'records': created_records,
                    'driver_name': driver.name,
                    'correction_type': correction_type
                }
                
        except Exception as e:
            logger.error(f"Erro ao criar registros manuais: {str(e)}")
            return {
                'success': False,
                'error': f'Erro ao criar registro manual: {str(e)}'
            }

    @staticmethod
    def _validate_batch_params(driver_id, reason, user, quantity, status) -> Dict[str, Any]:
        """Valida os parâmetros de entrada para criação em lote"""
        if not driver_id:
            return {'success': False, 'error': 'Driver ID é obrigatório'}
        
        if not reason or not reason.strip():
            return {'success': False, 'error': 'Motivo é obrigatório'}
        
        if not user:
            return {'success': False, 'error': 'Usuário é obrigatório'}
        
        if quantity < 1 or quantity > 100:  # Limite de segurança
            return {'success': False, 'error': 'Quantidade deve estar entre 1 e 100'}
        
        if status not in ManualCorrectionService.VALID_STATUSES:
            return {
                'success': False, 
                'error': f'Status inválido. Use um dos seguintes: {", ".join(ManualCorrectionService.VALID_STATUSES)}'
            }
        
        return {'success': True}

    @staticmethod
    def _create_manual_order(status: str, reason: str) -> Order:
        """Cria uma Order manual"""
        now = timezone.now()
        return Order.objects.create(
            uuid=uuid.uuid4(),
            order_id=ManualCorrectionService.generate_manual_order_id(),
            order_type='MANUAL',
            service_type='MANUAL',
            status=status,
            packages_count=1,
            packages_barcode='MANUAL',
            retailer='MANUAL_CORRECTION',
            retailer_order_number='MANUAL',
            retailer_sales_number='MANUAL',
            client_address='MANUAL CORRECTION',
            client_address_text=reason[:500],  # Limitar tamanho
            client_phone='0000000000',
            client_email='manual@correction.local',
            intended_delivery_date=now.date(),
            actual_delivery_date=now.date() if status == 'delivered' else None,
            delivery_timeslot='00:00-23:59',
            simplified_order_status=status,
            is_delivered=status == 'delivered',
            is_failed=status == 'undelivered',
            delivery_date_only=now.date() if status == 'delivered' else None,
            created_at=now,
            updated_at=now
        )

    @staticmethod
    def _create_manual_dispatch(order: Order, driver: Driver) -> Dispatch:
        """Cria um Dispatch manual"""
        return Dispatch.objects.create(
            order=order,
            driver=driver,
            fleet='MANUAL',
            dc='MANUAL',
            driver_route_stop=0,
            dispatch_time=timezone.now(),
            recovered=False
        )

    @staticmethod
    def _create_manual_correction(correction_type: str, reason: str, driver: Driver, 
                                order: Order, dispatch: Dispatch, user) -> Any:
        """Cria um registro de ManualCorrection"""
        from .models import ManualCorrection
        return ManualCorrection.objects.create(
            correction_type=correction_type,
            reason=reason,
            driver=driver,
            order=order,
            dispatch=dispatch,
            created_by=user,
            created_at=timezone.now()
        )

    @staticmethod
    def get_manual_corrections(
        start_date: Optional[Union[str, date]] = None, 
        end_date: Optional[Union[str, date]] = None, 
        driver_id: Optional[str] = None
    ) -> Any:
        """
        Busca as correções manuais com filtros
        
        Args:
            start_date: Data inicial (formato YYYY-MM-DD ou objeto date)
            end_date: Data final (formato YYYY-MM-DD ou objeto date)  
            driver_id: ID do motorista (opcional)
            
        Returns:
            QuerySet de ManualCorrection
        """
        try:
            from .models import ManualCorrection
            
            queryset = ManualCorrection.objects.all()
            
            if start_date:
                if isinstance(start_date, str):
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=start_date)
                
            if end_date:
                if isinstance(end_date, str):
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=end_date)
                
            if driver_id:
                queryset = queryset.filter(driver__driver_id=driver_id)
                
            return queryset.select_related('driver', 'order', 'created_by').order_by('-created_at')
            
        except Exception as e:
            logger.error(f"Erro ao buscar correções manuais: {str(e)}")
            return ManualCorrection.objects.none()
        
    @staticmethod
    def remove_manual_records(
        target_date: Union[str, date], 
        driver_id: Optional[str] = None, 
        reason: Optional[str] = None, 
        user = None
    ) -> Dict[str, Any]:
        """
        Remove registros manuais de uma data específica
        
        Args:
            target_date: Data dos registros a serem removidos
            driver_id: ID do motorista (opcional)
            reason: Motivo da remoção
            user: Usuário que está removendo
            
        Returns:
            Dict com resultado da operação
        """
        try:
            from .models import ManualCorrection
            
            # Converter string para date se necessário
            if isinstance(target_date, str):
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            
            with transaction.atomic():
                # Buscar as correções
                queryset = ManualCorrection.objects.filter(created_at__date=target_date)
                if driver_id:
                    queryset = queryset.filter(driver__driver_id=driver_id)
                
                # Se não encontrar nada, retorna erro
                count = queryset.count()
                if count == 0:
                    return {
                        'success': False,
                        'error': 'Nenhum registro encontrado para remover'
                    }
                
                # Coletar informações antes de deletar
                corrections_info = list(queryset.values(
                    'id', 'order_id', 'dispatch_id', 'driver__name', 'correction_type'
                ))
                
                # Coletar IDs dos orders e dispatches relacionados
                order_ids = list(queryset.values_list('order_id', flat=True))
                dispatch_ids = list(queryset.values_list('dispatch_id', flat=True))
                
                # Deletar todos os registros relacionados
                queryset.delete()
                deleted_orders = Order.objects.filter(id__in=order_ids).delete()[0]
                deleted_dispatches = Dispatch.objects.filter(id__in=dispatch_ids).delete()[0]
                
                logger.info(f"Removidos {count} registros manuais para data {target_date}")
                
                return {
                    'success': True,
                    'message': f'{count} registro{"s" if count > 1 else ""} removido{"s" if count > 1 else ""} com sucesso',
                    'removed_count': count,
                    'deleted_orders': deleted_orders,
                    'deleted_dispatches': deleted_dispatches,
                    'corrections_info': corrections_info
                }
                
        except Exception as e:
            logger.error(f"Erro ao remover registros manuais: {str(e)}")
            return {
                'success': False,
                'error': f'Erro ao remover registros: {str(e)}'
            }

    @classmethod
    def get_driver_manual_summary(
        cls, 
        driver_id: str, 
        start_date: Optional[Union[str, date]] = None,
        end_date: Optional[Union[str, date]] = None
    ) -> Dict[str, Any]:
        """
        Obtém um resumo das correções manuais de um motorista
        
        Args:
            driver_id: ID do motorista
            start_date: Data inicial (opcional)
            end_date: Data final (opcional)
            
        Returns:
            Dict com resumo das correções
        """
        try:
            corrections = cls.get_manual_corrections(start_date, end_date, driver_id)
            
            total_corrections = corrections.count()
            additions = corrections.filter(correction_type='ADD').count()
            subtractions = corrections.filter(correction_type='SUB').count()
            
            # Agrupar por status
            status_summary = {}
            for correction in corrections:
                status = correction.order.status
                if status not in status_summary:
                    status_summary[status] = {'ADD': 0, 'SUB': 0}
                status_summary[status][correction.correction_type] += 1
            
            return {
                'success': True,
                'driver_id': driver_id,
                'period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'summary': {
                    'total_corrections': total_corrections,
                    'additions': additions,
                    'subtractions': subtractions,
                    'net_change': additions - subtractions
                },
                'status_breakdown': status_summary
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar resumo do motorista {driver_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Erro ao gerar resumo: {str(e)}'
            }
    
    @staticmethod
    @transaction.atomic
    def create_manual_correction(
        driver_id: str,
        target_date: Union[str, date],
        status: str,
        reason: str,
        quantity: int,
        created_by_user,
        correction_type: str = 'ADD'
    ) -> Dict[str, Any]:
        """
        Cria uma correção manual seguindo o mesmo padrão da API.
        Cria Order e Dispatch da mesma forma que o DataProcessor.
        
        Args:
            driver_id: ID do motorista
            target_date: Data da correção
            status: Status do pedido
            reason: Motivo da correção
            quantity: Quantidade de pedidos (para futuras extensões)
            created_by_user: Usuário que criou a correção
            correction_type: Tipo de correção ('ADD' ou 'SUB')
            
        Returns:
            Dict com resultado da operação
        """
        try:
            from .models import ManualCorrection
            import uuid
            
            # Converter string para date se necessário
            if isinstance(target_date, str):
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            
            # Validar status
            if status not in ManualCorrectionService.VALID_STATUSES:
                return {
                    'success': False,
                    'error': f'Status inválido: {status}. Statuses válidos: {", ".join(ManualCorrectionService.VALID_STATUSES)}'
                }
            
            # Buscar o motorista
            try:
                driver = Driver.objects.get(driver_id=driver_id)
            except Driver.DoesNotExist:
                return {
                    'success': False,
                    'error': f'Motorista com ID {driver_id} não encontrado'
                }
            
            # Gerar UUID único para o pedido
            order_uuid = uuid.uuid4()
            order_id = f"MANUAL_{order_uuid.hex[:8].upper()}"
            
            # Criar Order seguindo o padrão da API
            order = Order.objects.create(
                uuid=order_uuid,
                order_id=order_id,
                order_type='manual',
                service_type='manual_correction',
                status=status,
                packages_count=1,
                packages_barcode=f"MAN_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
                retailer='Manual Correction',
                retailer_order_number=order_id,
                retailer_sales_number=order_id,
                client_address='Manual Entry',
                client_address_text='Manual Entry',
                client_phone='',
                client_email='',
                intended_delivery_date=target_date,
                actual_delivery_date=target_date if status == 'delivered' else None,
                delivery_timeslot='',
                simplified_order_status=status,
                # Campos calculados baseados no status
                is_delivered=status in ['delivered', 'picked_up'],
                is_failed=status in ['failed', 'returned', 'cancelled', 'undelivered'],
                delivery_date_only=target_date if status == 'delivered' else None,
            )
            
            # Criar Dispatch seguindo o padrão da API
            dispatch_time = timezone.now().replace(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=9,  # Hora padrão para entregas manuais
                minute=0,
                second=0,
                microsecond=0
            )
            
            dispatch = Dispatch.objects.create(
                order=order,
                driver=driver,
                dispatch_time=dispatch_time,
                fleet='MANUAL',
                dc='MANUAL',
                driver_route_stop=1,
                recovered=False,
            )
            
            # Criar registro de correção manual
            correction = ManualCorrection.objects.create(
                correction_type=correction_type,
                driver=driver,
                correction_date=target_date,
                status=status,
                reason=reason,
                order=order,
                dispatch=dispatch,
                created_by=created_by_user,
                quantity=quantity
            )
            
            logger.info(f"✅ Correção manual criada: {order_id} para {driver.name} em {target_date}")
            
            return {
                'success': True,
                'message': f'Correção manual criada com sucesso: {order_id}',
                'correction_id': correction.id,
                'order_id': order.id,
                'dispatch_id': dispatch.id
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar correção manual: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }