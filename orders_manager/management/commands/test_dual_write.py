"""
Management command para testar o dual write de pedidos.

Uso:
    python manage.py test_dual_write
    python manage.py test_dual_write --count 5  # Criar 5 pedidos de teste
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from orders_manager.adapters import get_order_adapter
from datetime import datetime, timedelta
import random


class Command(BaseCommand):
    help = 'Testa dual write criando pedidos de exemplo'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=1,
            help='Número de pedidos de teste a criar',
        )
    
    def handle(self, *args, **options):
        count = options['count']
        
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS(' TESTE DE DUAL WRITE'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
        
        adapter = get_order_adapter()
        
        # Mostrar configuração atual
        self.stdout.write(self.style.HTTP_INFO('📋 Configuração Atual:\n'))
        self.stdout.write(f'  • Dual Write: {"🟢 ATIVADO" if adapter.dual_write else "❌ DESATIVADO"}')
        self.stdout.write(f'  • Write Generic: {"🟢 SIM" if adapter.write_generic else "❌ NÃO"}')
        self.stdout.write(f'  • Read Generic: {"🟢 SIM" if adapter.read_generic else "❌ NÃO"}')
        self.stdout.write(f'  • Validação: {"🟢 ATIVADA" if adapter.validate else "❌ DESATIVADA"}')
        self.stdout.write(f'  • Logging: {"🟢 ATIVADO" if adapter.log_operations else "❌ DESATIVADO"}\n')
        
        if not adapter.dual_write:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️ DUAL_WRITE_ORDERS não está ativado!\n'
                    '   Os pedidos serão criados apenas no sistema antigo.\n'
                )
            )
        
        # Criar pedidos de teste
        self.stdout.write(self.style.HTTP_INFO(f'🚀 Criando {count} pedido(s) de teste...\n'))
        
        created_generic = []
        created_paack = []
        errors = []
        
        for i in range(count):
            try:
                order_data = self._generate_test_order(i)
                
                self.stdout.write(f'  [{i+1}/{count}] Criando pedido {order_data["external_reference"]}...')
                
                order_generic, order_paack = adapter.create_order(order_data)
                
                if order_generic:
                    created_generic.append(order_generic)
                    self.stdout.write(
                        self.style.SUCCESS(f'    ✓ Generic criado (ID: {order_generic.id})')
                    )
                
                if order_paack:
                    created_paack.append(order_paack)
                    self.stdout.write(
                        self.style.SUCCESS(f'    ✓ Paack criado (UUID: {order_paack.uuid})')
                    )
                
            except Exception as e:
                error_msg = f'Erro no pedido {i+1}: {str(e)}'
                errors.append(error_msg)
                self.stdout.write(self.style.ERROR(f'    ❌ {error_msg}'))
        
        # Resumo
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS(' RESUMO DO TESTE'))
        self.stdout.write('='*70)
        self.stdout.write(f'✅ Pedidos Generic criados: {len(created_generic)}')
        self.stdout.write(f'✅ Pedidos Paack criados: {len(created_paack)}')
        self.stdout.write(f'❌ Erros: {len(errors)}')
        
        if errors:
            self.stdout.write('\n⚠️ ERROS ENCONTRADOS:')
            for error in errors:
                self.stdout.write(f'   • {error}')
        
        # Validar consistência se dual write
        if adapter.dual_write and len(created_generic) > 0 and len(created_paack) > 0:
            self.stdout.write('\n' + self.style.HTTP_INFO('🔍 Validando consistência...\n'))
            
            for i, (gen, paack) in enumerate(zip(created_generic, created_paack)):
                self.stdout.write(f'  Pedido {i+1}:')
                self.stdout.write(f'    - UUID Paack: {paack.uuid}')
                self.stdout.write(f'    - Ref Generic: {gen.external_reference}')
                self.stdout.write(f'    - Status Paack: {paack.status}')
                self.stdout.write(f'    - Status Generic: {gen.current_status}')
                
                if str(paack.uuid) == gen.external_reference:
                    self.stdout.write(self.style.SUCCESS('    ✓ Referências match'))
                else:
                    self.stdout.write(self.style.ERROR('    ❌ Referências NÃO match!'))
        
        self.stdout.write('='*70)
        
        if adapter.dual_write:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n✅ Teste concluído! Verifique os logs da aplicação para detalhes.\n'
                    '   Consulte: docker compose logs web --tail 50 | grep "DUAL WRITE"\n'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️ Para ativar dual write, edite system_config/feature_flags.py:\n'
                    '   DUAL_WRITE_ORDERS = True\n'
                )
            )
    
    def _generate_test_order(self, index):
        """Gera dados de pedido de teste"""
        
        addresses = [
            ('Rua da Prata, 123, 1100-420 Lisboa', '1100-420'),
            ('Av. dos Aliados, 45, 4000-099 Porto', '4000-099'),
            ('Rua do Comércio, 78, 3000-123 Coimbra', '3000-123'),
            ('Largo da Sé, 10, 4700-435 Braga', '4700-435'),
            ('Rua 25 de Abril, 56, 8000-100 Faro', '8000-100'),
        ]
        
        address, postal_code = random.choice(addresses)
        
        # Data de entrega: amanhã a 7 dias no futuro
        delivery_date = datetime.now().date() + timedelta(days=random.randint(1, 7))
        
        return {
            'external_reference': f'TEST-{datetime.now().strftime("%Y%m%d")}-{index+1:04d}',
            'recipient_name': f'Cliente Teste {index+1}',
            'recipient_address': address,
            'postal_code': postal_code,
            'recipient_phone': f'+351 9{random.randint(10000000, 99999999)}',
            'recipient_email': f'cliente{index+1}@example.com',
            'declared_value': random.choice([10.50, 25.00, 50.00, 75.00, 100.00]),
            'weight_kg': random.choice([0.5, 1.0, 2.0, 5.0]),
            'scheduled_delivery': delivery_date,
            'status': random.choice(['pending', 'assigned', 'in_transit']),
            'notes': f'Pedido de teste criado em {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            'order_type': 'standard',
            'service_type': 'standard',
            'packages_count': 1,
            'packages_barcode': f'BAR{index+1:04d}',
            'retailer': 'Paack',
            'delivery_timeslot': '09:00-18:00',
        }
