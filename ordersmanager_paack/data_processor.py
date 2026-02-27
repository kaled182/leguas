import logging
from uuid import UUID
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from .models import Order, Driver, Dispatch, DeliveryAttempt
from .utils import parse_api_date, parse_api_datetime

logger = logging.getLogger(__name__)

class DataProcessor:
    """
    Classe responsável pelo processamento e transformação dos dados da API
    para as models do Django. Baseada no ordersmanager funcional.
    """
    
    def __init__(self):
        self.stats = {
            'total_processed': 0,
            'orders_created': 0,
            'orders_updated': 0,
            'drivers_created': 0,
            'dispatches_created': 0,
            'errors': []
        }
    
    def process_data(self, api_data):
        """
        Processa os dados da API e retorna estatísticas.
        IMPLEMENTAÇÃO REAL baseada no ordersmanager.
        Todas as operações ORM utilizam o banco padrão (MySQL).
        """
        try:
            logger.info("💾 Utilizando banco: {0}".format(settings.DATABASES['default']['ENGINE']))
            logger.info("🔍 Analisando estrutura dos dados da API...")
            
            # Obter dataset principal - igual ao ordersmanager
            dataset = api_data.get('DATA_EXTRACT_AVG') or api_data.get('DATA_PIVOT')
            if not dataset:
                logger.error("❌ Dataset não encontrado na resposta da API")
                logger.error(f"🔍 Chaves disponíveis: {list(api_data.keys()) if api_data else 'Nenhuma'}")
                return self.stats
            
            columns = dataset.get("columns", [])
            rows = dataset.get("data", [])
            
            logger.info(f"📋 Dataset encontrado com {len(columns)} colunas")
            logger.info(f"📦 Total de linhas brutas: {len(rows)}")
            
            # Filtrar linhas com estrutura incorreta
            valid_rows = [row for row in rows if len(row) == len(columns)]
            invalid_rows = len(rows) - len(valid_rows)
            
            if invalid_rows > 0:
                logger.warning(f"⚠️ {invalid_rows} linhas descartadas (estrutura incorreta)")
            
            if not columns or not valid_rows:
                logger.warning("⚠️ Nenhum dado válido para processar")
                return self.stats
            
            logger.info(f"✅ Processando {len(valid_rows)} registros válidos...")
            logger.info(f"📝 Colunas disponíveis: {', '.join(columns[:10])}{'...' if len(columns) > 10 else ''}")
            
            # Processar cada linha em transação
            processed_count = 0
            with transaction.atomic():
                for row_index, row in enumerate(valid_rows):
                    try:
                        self._process_single_row(row, columns)
                        self.stats['total_processed'] += 1
                        processed_count += 1
                        
                        # Log de progresso a cada 50 registros
                        if processed_count % 50 == 0:
                            logger.info(f"📈 Progresso: {processed_count}/{len(valid_rows)} registros processados")
                        
                    except Exception as e:
                        error_msg = f"Erro na linha {row_index}: {str(e)}"
                        logger.error(f"❌ {error_msg}")
                        self.stats['errors'].append(error_msg)
                        # Continue processando outras linhas mesmo com erro
                        continue
            
            self._log_stats()
            return self.stats
            
        except Exception as e:
            logger.error(f"❌ Erro geral no processamento: {e}")
            self.stats['errors'].append(str(e))
            return self.stats
    
    def _process_single_row(self, row, columns):
        """Processa uma linha individual dos dados - baseado no ordersmanager"""
        def get_value(column_name, default=None):
            try:
                index = columns.index(column_name)
                value = row[index] if index < len(row) else default
                return value if value not in ['', None, 'null'] else default
            except ValueError:
                return default
        
        # Validar UUID da ordem
        order_uuid = get_value('ORDER_UUID')
        if not order_uuid:
            raise ValueError("ORDER_UUID é obrigatório")
        
        try:
            uuid_obj = UUID(order_uuid)
        except ValueError:
            raise ValueError(f"UUID inválido: {order_uuid}")
        
        # Processar motorista se existir
        driver = None
        driver_id = get_value('DISPATCH_DRIVER_ID')
        if driver_id:
            driver = self._get_or_create_driver(
                driver_id=driver_id,
                name=get_value('DISPATCH_DRIVER_NAME', 'Motorista Desconhecido'),
                vehicle=get_value('DISPATCH_DRIVER_VEHICLE', ''),
                vehicle_norm=get_value('DISPATCH_DRIVER_VEHICLE_NORM', '')
            )
        
        # Processar ordem
        order = self._get_or_create_order(row, columns, uuid_obj)
        
        # Processar dispatch
        if driver:
            self._get_or_create_dispatch(order, driver, row, columns)
    
    def _get_or_create_driver(self, driver_id, name, vehicle, vehicle_norm):
        """Cria ou atualiza um motorista (gravação no banco padrão MySQL)"""
        driver, created = Driver.objects.get_or_create(
            driver_id=driver_id,
            defaults={
                'name': name,
                'vehicle': vehicle or 'Desconhecido',
                'vehicle_norm': vehicle_norm or 'Desconhecido'
            }
        )
        
        if created:
            self.stats['drivers_created'] += 1
            logger.info(f"🚛 Novo motorista: {name}")
        
        return driver
    
    def _get_or_create_order(self, row, columns, uuid_obj):
        """Cria ou atualiza uma ordem (gravação no banco padrão MySQL)"""
        def get_value(column_name, default=None):
            try:
                index = columns.index(column_name)
                value = row[index] if index < len(row) else default
                return value if value not in ['', None, 'null'] else default
            except ValueError:
                return default
        
        order, created = Order.objects.update_or_create(
            uuid=uuid_obj,
            defaults={
                'order_id': get_value('ORDER_ID', ''),
                'order_type': get_value('ORDER_TYPE', ''),
                'service_type': get_value('SERVICE_TYPE', ''),
                'status': get_value('ORDER_STATUS', ''),
                'packages_count': self._safe_int(get_value('PACKAGES_COUNT', 0)),
                'packages_barcode': get_value('PACKAGES_BARCODE', ''),
                'retailer': get_value('RETAILER', ''),
                'retailer_order_number': get_value('RETAILER_ORDER_NUMBER', ''),
                'retailer_sales_number': get_value('RETAILER_SALES_NUMBER', ''),
                'client_address': get_value('CLIENT_ADDRESS', ''),
                'client_address_text': get_value('CLIENT_ADDRESS_TEXT', ''),
                'client_phone': get_value('CLIENT_PHONE', ''),
                'client_email': get_value('CLIENT_EMAIL', ''),
                'intended_delivery_date': parse_api_date(get_value('ORDER_INTENDED_DELIVERY_DATE')) or timezone.now().date(),
                'actual_delivery_date': parse_api_date(get_value('ORDER_ACTUAL_DELIVERY_DATE')),
                'delivery_timeslot': get_value('ORDER_DELIVERY_TIMESLOT', ''),
                'simplified_order_status': get_value('SIMPLIFIED_ORDER_STATUS', ''),
                # Campos calculados
                'is_delivered': get_value('ORDER_STATUS') in ['delivered', 'picked_up'],
                'is_failed': get_value('ORDER_STATUS') in ['failed', 'returned', 'cancelled'],
                'delivery_date_only': parse_api_date(get_value('ORDER_ACTUAL_DELIVERY_DATE')),
            }
        )
        
        if created:
            self.stats['orders_created'] += 1
            logger.info(f"📦 Nova ordem: {order.order_id}")
        else:
            self.stats['orders_updated'] += 1
        
        return order
    
    def _get_or_create_dispatch(self, order, driver, row, columns):
        """Cria ou atualiza um dispatch (gravação no banco padrão MySQL)"""
        def get_value(column_name, default=None):
            try:
                index = columns.index(column_name)
                value = row[index] if index < len(row) else default
                return value if value not in ['', None, 'null'] else default
            except ValueError:
                return default
        
        try:
            dispatch_time_raw = get_value('DIPATCH_DRIVER_TIME')
            dispatch_time_parsed = parse_api_datetime(dispatch_time_raw) if dispatch_time_raw else None
            
            dispatch, created = Dispatch.objects.update_or_create(
                order=order,
                defaults={
                    'driver': driver,
                    'dispatch_time': dispatch_time_parsed,
                    'fleet': get_value('DISPATCH_FLEET', ''),
                    'dc': get_value('DISPATCH_DC', ''),
                    'driver_route_stop': self._safe_int(get_value('DRIVER_ROUTE_STOP', 0)),
                    'recovered': bool(self._safe_int(get_value('RECOVERED', 0))),
                }
            )
            
            if created:
                self.stats['dispatches_created'] += 1
                logger.info(f"🚚 Novo dispatch criado para {order.order_id}")
            
            return dispatch
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar/atualizar dispatch para {order.order_id}: {str(e)}")
            # Re-raise para não quebrar a transação silenciosamente
            raise
    
    def _safe_int(self, value, default=0):
        """Converte valor para int de forma segura"""
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def _log_stats(self):
        """Registra estatísticas do processamento"""
        logger.info("=" * 50)
        logger.info("📈 ESTATÍSTICAS FINAIS DO PROCESSAMENTO")
        logger.info("=" * 50)
        logger.info(f"   📦 Total processado: {self.stats['total_processed']}")
        logger.info(f"   🆕 Ordens criadas: {self.stats['orders_created']}")
        logger.info(f"   🔄 Ordens atualizadas: {self.stats['orders_updated']}")
        logger.info(f"   🚛 Motoristas criados: {self.stats['drivers_created']}")
        logger.info(f"   🚚 Dispatches criados: {self.stats['dispatches_created']}")
        
        if self.stats['errors']:
            logger.warning(f"   ⚠️ Erros encontrados: {len(self.stats['errors'])}")
            logger.warning("   📋 Primeiros 3 erros:")
            for i, error in enumerate(self.stats['errors'][:3]):
                logger.warning(f"      {i+1}. {error}")
        else:
            logger.info("   ✅ Nenhum erro encontrado!")
        
        logger.info("=" * 50)