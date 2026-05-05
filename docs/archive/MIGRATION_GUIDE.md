# 📋 Guia de Migração - Sistema Legacy → Multi-Partner

## Objetivo

Migrar o sistema atual (focado em Paack) para uma arquitetura multi-partner sem interrupção do serviço.

---

## ⚠️ Princípios da Migração

1. **Zero Downtime**: Sistema antigo e novo rodam em paralelo
2. **Idempotência**: Scripts podem ser executados múltiplas vezes
3. **Rollback**: Sempre possível voltar ao estado anterior
4. **Validação**: Cada etapa é verificada antes de prosseguir

---

## 🗓️ Fases da Migração

### Fase 0: Preparação (Antes de começar)

#### Checklist Pré-Migração
- [ ] Backup completo do banco de dados
- [ ] Documentar queries SQL mais usadas
- [ ] Listar todas as integrações externas ativas
- [ ] Congelar mudanças no código legacy por 48h
- [ ] Notificar equipe sobre janela de migração

#### Comandos de Backup

```bash
# Backup MySQL
docker exec leguas_db mysqldump -u root -p leguas_db > backup_pre_migration_$(date +%Y%m%d_%H%M%S).sql

# Backup de arquivos (media)
tar -czf media_backup_$(date +%Y%m%d_%H%M%S).tar.gz media/

# Verificar integridade
md5sum backup_*.sql > backup_checksums.txt
```

---

### Fase 1: Criação da Infraestrutura (Dia 1)

#### 1.1 - Criar Apps Django

```bash
# Dentro do container Django
docker exec -it leguas_web bash

python manage.py startapp core
python manage.py startapp orders_manager
python manage.py startapp fleet_management
python manage.py startapp pricing
python manage.py startapp route_allocation
python manage.py startapp analytics
```

#### 1.2 - Registrar Apps em `settings.py`

```python
# my_project/settings.py

INSTALLED_APPS = [
    # ... apps existentes ...
    'drivers_app',
    'ordersmanager_paack',  # MANTER por enquanto
    
    # Novos apps
    'core',
    'orders_manager',
    'fleet_management',
    'pricing',
    'route_allocation',
    'analytics',
]
```

#### 1.3 - Criar Models Iniciais

**Ordem de criação** (por dependências):
1. `core.Partner`
2. `pricing.PostalZone`
3. `pricing.PartnerTariff`
4. `orders_manager.Order`
5. `fleet_management.Vehicle`

**Executar migrations**:
```bash
python manage.py makemigrations core
python manage.py migrate core

python manage.py makemigrations pricing
python manage.py migrate pricing

# Repetir para cada app
```

---

### Fase 2: Migração de Dados (Dia 2-3)

#### 2.1 - Criar Partner "Paack"

```python
# management/commands/create_initial_partners.py

from django.core.management.base import BaseCommand
from core.models import Partner, PartnerIntegration

class Command(BaseCommand):
    help = 'Cria Partners iniciais'
    
    def handle(self, *args, **options):
        # Partner Paack
        paack, created = Partner.objects.get_or_create(
            nif='PT123456789',  # NIF real da Paack
            defaults={
                'name': 'Paack',
                'contact_email': 'operations@paack.co',
                'contact_phone': '+351912345678',
                'api_credentials': {
                    'api_key': 'YOUR_PAACK_API_KEY',
                    'api_secret': 'YOUR_PAACK_SECRET',
                },
                'is_active': True,
            }
        )
        
        if created:
            # Criar integração API
            PartnerIntegration.objects.create(
                partner=paack,
                integration_type='API',
                endpoint_url='https://api.paack.co/v1',
                auth_config={'type': 'bearer'},
                sync_frequency_minutes=15,
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Partner {paack.name} criado com sucesso!')
            )
```

**Executar**:
```bash
python manage.py create_initial_partners
```

#### 2.2 - Migrar Pedidos Paack

```python
# management/commands/migrate_paack_orders.py

from django.core.management.base import BaseCommand
from django.db import transaction
from ordersmanager_paack.models import PaackOrder, PaackOrderStatus
from orders_manager.models import Order, OrderStatus
from core.models import Partner
from datetime import datetime

class Command(BaseCommand):
    help = 'Migra pedidos da Paack para modelo genérico'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem salvar no banco (teste)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Número de pedidos por lote',
        )
    
    def handle(self, *args, **options):
        paack = Partner.objects.get(name='Paack')
        
        # Contar total
        total = PaackOrder.objects.count()
        self.stdout.write(f'Total de pedidos a migrar: {total}')
        
        migrated = 0
        errors = []
        
        # Processar em lotes
        for offset in range(0, total, options['batch_size']):
            batch = PaackOrder.objects.all()[offset:offset + options['batch_size']]
            
            with transaction.atomic():
                for paack_order in batch:
                    try:
                        # Verificar se já foi migrado
                        if Order.objects.filter(
                            external_reference=paack_order.tracking_code
                        ).exists():
                            continue
                        
                        # Criar Order genérico
                        new_order = Order(
                            partner=paack,
                            external_reference=paack_order.tracking_code,
                            recipient_name=paack_order.recipient_name,
                            recipient_address=paack_order.address,
                            postal_code=paack_order.postal_code,
                            recipient_phone=paack_order.phone,
                            declared_value=paack_order.value or 0,
                            scheduled_delivery=paack_order.delivery_date,
                            current_status=self._map_status(paack_order.status),
                            assigned_driver_id=paack_order.driver_id,
                            created_at=paack_order.created_at,
                        )
                        
                        if not options['dry_run']:
                            new_order.save()
                            
                            # Migrar histórico de status
                            for old_status in PaackOrderStatus.objects.filter(
                                order=paack_order
                            ):
                                OrderStatus.objects.create(
                                    order=new_order,
                                    status=self._map_status(old_status.status),
                                    notes=old_status.notes,
                                    changed_at=old_status.created_at,
                                    changed_by_id=old_status.user_id,
                                )
                        
                        migrated += 1
                        
                    except Exception as e:
                        errors.append({
                            'paack_order_id': paack_order.id,
                            'tracking_code': paack_order.tracking_code,
                            'error': str(e),
                        })
                
                # Commit do lote
                if options['dry_run']:
                    raise Exception("Dry-run: rollback")
            
            # Progress
            self.stdout.write(
                f'Progresso: {min(offset + options["batch_size"], total)}/{total}'
            )
        
        # Resumo
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Migração concluída!\n'
            f'Migrados: {migrated}\n'
            f'Erros: {len(errors)}'
        ))
        
        if errors:
            self.stdout.write(self.style.ERROR(
                '\n❌ Pedidos com erro:'
            ))
            for err in errors[:10]:  # Mostrar apenas os 10 primeiros
                self.stdout.write(f"  - {err['tracking_code']}: {err['error']}")
    
    def _map_status(self, paack_status):
        """Mapeia status da Paack para status genérico"""
        mapping = {
            'pending': 'PENDING',
            'assigned': 'ASSIGNED',
            'in_transit': 'IN_TRANSIT',
            'delivered': 'DELIVERED',
            'returned': 'RETURNED',
            'incident': 'INCIDENT',
        }
        return mapping.get(paack_status, 'PENDING')
```

**Executar**:
```bash
# Teste primeiro (sem salvar)
python manage.py migrate_paack_orders --dry-run

# Se OK, migrar de verdade
python manage.py migrate_paack_orders

# Verificar quantidade
python manage.py shell
>>> from orders_manager.models import Order
>>> Order.objects.count()
>>> from ordersmanager_paack.models import PaackOrder
>>> PaackOrder.objects.count()
# Devem ser iguais
```

#### 2.3 - Validação da Migração

```python
# management/commands/validate_migration.py

from django.core.management.base import BaseCommand
from ordersmanager_paack.models import PaackOrder
from orders_manager.models import Order

class Command(BaseCommand):
    help = 'Valida se migração está correta'
    
    def handle(self, *args, **options):
        checks = []
        
        # Check 1: Contagem total
        paack_count = PaackOrder.objects.count()
        generic_count = Order.objects.filter(partner__name='Paack').count()
        
        if paack_count == generic_count:
            checks.append(('Contagem total', True, f'{generic_count} pedidos'))
        else:
            checks.append(('Contagem total', False, 
                          f'Paack: {paack_count} vs Generic: {generic_count}'))
        
        # Check 2: Valores financeiros
        paack_total = PaackOrder.objects.aggregate(
            total=models.Sum('value')
        )['total'] or 0
        
        generic_total = Order.objects.filter(partner__name='Paack').aggregate(
            total=models.Sum('declared_value')
        )['total'] or 0
        
        if abs(paack_total - generic_total) < 0.01:
            checks.append(('Valores declarados', True, 
                          f'€{generic_total:.2f}'))
        else:
            checks.append(('Valores declarados', False,
                          f'Paack: €{paack_total:.2f} vs Generic: €{generic_total:.2f}'))
        
        # Check 3: Pedidos sem duplicação
        duplicates = Order.objects.values('external_reference').annotate(
            count=models.Count('id')
        ).filter(count__gt=1)
        
        if duplicates.count() == 0:
            checks.append(('Duplicação', True, 'Sem duplicatas'))
        else:
            checks.append(('Duplicação', False, 
                          f'{duplicates.count()} referências duplicadas'))
        
        # Mostrar resultados
        self.stdout.write('\n' + '='*60)
        self.stdout.write(' RESULTADO DA VALIDAÇÃO')
        self.stdout.write('='*60 + '\n')
        
        all_passed = True
        for check_name, passed, info in checks:
            status = '✅' if passed else '❌'
            self.stdout.write(f'{status} {check_name}: {info}')
            if not passed:
                all_passed = False
        
        self.stdout.write('\n' + '='*60)
        if all_passed:
            self.stdout.write(self.style.SUCCESS(
                '✅ VALIDAÇÃO PASSOU! Migração está correta.'
            ))
        else:
            self.stdout.write(self.style.ERROR(
                '❌ VALIDAÇÃO FALHOU! Revisar migração.'
            ))
```

**Executar**:
```bash
python manage.py validate_migration
```

---

### Fase 3: Implementação Dual (Dia 4-7)

Durante esta fase, **ambos os sistemas rodam em paralelo**:
- Novas orders podem ser criadas em ambos
- Dashboards leem dos dois
- Equipe usa o novo sistema gradualmente

#### 3.1 - Configurar Feature Flags

```python
# my_project/settings.py

# Feature Flags
FEATURE_FLAGS = {
    'USE_GENERIC_ORDERS': True,  # Gravar em orders_manager também
    'READ_FROM_GENERIC_ORDERS': False,  # Ainda lê do Paack
    'SETTLEMENTS_FROM_GENERIC': False,  # Settlements ainda usa Paack
}
```

#### 3.2 - Adapter Pattern para Transição

```python
# orders_manager/adapters.py

from django.conf import settings
from ordersmanager_paack.models import PaackOrder
from orders_manager.models import Order
from core.models import Partner

class OrderAdapter:
    """
    Abstração que permite ler/escrever em ambos os sistemas
    durante a migração
    """
    
    @staticmethod
    def create_order(partner_name, order_data):
        # Sempre cria no sistema antigo (backwards compatibility)
        paack_order = PaackOrder.objects.create(**order_data)
        
        # Se feature flag ativa, cria também no novo
        if settings.FEATURE_FLAGS['USE_GENERIC_ORDERS']:
            partner = Partner.objects.get(name=partner_name)
            Order.objects.create(
                partner=partner,
                external_reference=paack_order.tracking_code,
                **order_data
            )
        
        return paack_order
    
    @staticmethod
    def get_orders(filters=None):
        if settings.FEATURE_FLAGS['READ_FROM_GENERIC_ORDERS']:
            return Order.objects.filter(**(filters or {}))
        else:
            return PaackOrder.objects.filter(**(filters or {}))
```

**Uso nas views**:
```python
# orders_manager/views.py

from .adapters import OrderAdapter

def list_orders(request):
    orders = OrderAdapter.get_orders(filters={'status': 'PENDING'})
    # Resto do código fica igual
```

---

### Fase 4: Transição Gradual (Dia 8-14)

#### 4.1 - Ativar Leitura do Sistema Novo

```python
# settings.py
FEATURE_FLAGS = {
    'USE_GENERIC_ORDERS': True,
    'READ_FROM_GENERIC_ORDERS': True,  # 🔄 MUDANÇA AQUI
    'SETTLEMENTS_FROM_GENERIC': False,
}
```

**Testar extensivamente**:
- Dashboards carregam corretamente?
- Filtros funcionam?
- Performance OK?

#### 4.2 - Migrar Settlements

```python
# settlements/models.py (evoluir modelo existente)

class DriverSettlement(models.Model):
    # Campos existentes
    driver = models.ForeignKey('drivers_app.DriverProfile', ...)
    week_number = models.IntegerField()
    # ...
    
    # NOVOS CAMPOS (adicionar via migration)
    is_from_generic_orders = models.BooleanField(default=False)  # Flag de controle
    partner = models.ForeignKey('core.Partner', null=True, blank=True)  # Novo
    
    def calculate_amount(self):
        if self.is_from_generic_orders:
            # Usa orders_manager.Order
            orders = Order.objects.filter(
                assigned_driver=self.driver,
                current_status='DELIVERED',
                # filtro de data da semana...
            )
            # Calcula baseado em PartnerTariff
        else:
            # Lógica antiga (Paack hardcoded)
            pass
```

**Migration para adicionar campos**:
```bash
python manage.py makemigrations settlements --name add_generic_order_support
python manage.py migrate settlements
```

#### 4.3 - Testar Cálculo de Settlement

```bash
# Criar settlement de teste
python manage.py shell
>>> from settlements.models import DriverSettlement
>>> from drivers_app.models import DriverProfile
>>> driver = DriverProfile.objects.first()
>>> settlement = DriverSettlement.objects.create(
...     driver=driver,
...     week_number=10,
...     year=2026,
...     is_from_generic_orders=True  # Usar novo sistema
... )
>>> settlement.calculate_amount()
# Verificar se valores batem com manual
```

---

### Fase 5: Deprecação do Sistema Antigo (Dia 15-21)

#### 5.1 - Parar de Escrever no Sistema Antigo

```python
# settings.py
FEATURE_FLAGS = {
    'USE_GENERIC_ORDERS': True,
    'READ_FROM_GENERIC_ORDERS': True,
    'SETTLEMENTS_FROM_GENERIC': True,  # 🔄 MUDANÇA AQUI
    'DISABLE_PAACK_WRITES': True,  # 🔄 NOVO
}
```

#### 5.2 - Remover Código Legacy (Gradualmente)

```python
# ordersmanager_paack/models.py

class PaackOrder(models.Model):
    # ... campos existentes ...
    
    class Meta:
        managed = False  # Django não gerencia mais este modelo
        db_table = 'paack_orders_legacy'  # Renomear tabela
```

**Renomear tabela no MySQL**:
```sql
RENAME TABLE ordersmanager_paack_paackorder TO paack_orders_legacy;
```

#### 5.3 - Arquivar Dados Antigos

```bash
# Exportar dados antigos para arquivo
python manage.py dumpdata ordersmanager_paack > legacy_paack_data.json

# Ou backup SQL
mysqldump leguas_db paack_orders_legacy > paack_legacy_backup.sql
```

---

### Fase 6: Limpeza Final (Dia 22-30)

#### 6.1 - Remover Apps Legacy

```python
# settings.py
INSTALLED_APPS = [
    # ... apps existentes ...
    # 'ordersmanager_paack',  # COMENTAR/REMOVER
    
    # Novos apps
    'core',
    'orders_manager',
    # ...
]
```

#### 6.2 - Remover Tabelas do Banco (CUIDADO!)

```sql
-- Apenas após confirmação de que tudo funciona há 30 dias
DROP TABLE IF EXISTS paack_orders_legacy;
DROP TABLE IF EXISTS paack_order_status_legacy;
-- etc
```

#### 6.3 - Atualizar Documentação

- [ ] Atualizar README.md
- [ ] Atualizar diagramas ER
- [ ] Documentar novos endpoints de API
- [ ] Criar tutorial de uso para equipe

---

## 🔍 Checklist de Validação por Fase

### Fase 1: Infraestrutura
- [ ] Todos os apps criados e registrados
- [ ] Migrations rodadas sem erro
- [ ] Admin interface acessível para novos models

### Fase 2: Migração de Dados
- [ ] Partner Paack criado
- [ ] Todos os pedidos migrados (contagem OK)
- [ ] Valores financeiros batem
- [ ] Sem pedidos duplicados
- [ ] Histórico de status migrado

### Fase 3: Sistema Dual
- [ ] Novas orders gravadas em ambos
- [ ] Dashboards funcionam com ambos
- [ ] Performance aceitável

### Fase 4: Transição
- [ ] Leitura migrada para sistema novo
- [ ] Settlements calculados corretamente
- [ ] Sem erros em produção há 7 dias

### Fase 5: Deprecação
- [ ] Sistema antigo em read-only
- [ ] Dados arquivados
- [ ] Tabelas renomeadas

### Fase 6: Limpeza
- [ ] Código legacy removido
- [ ] Tabelas antigas dropadas (após 30 dias)
- [ ] Documentação atualizada

---

## 🚨 Plano de Rollback

### Se algo der errado na Fase 2-3:

```python
# settings.py - Voltar flags
FEATURE_FLAGS = {
    'USE_GENERIC_ORDERS': False,  # Desativar escrita
    'READ_FROM_GENERIC_ORDERS': False,  # Voltar para Paack
    'SETTLEMENTS_FROM_GENERIC': False,
}
```

### Se algo der errado na Fase 4-5:

```bash
# Restaurar backup do banco
mysql -u root -p leguas_db < backup_pre_migration_YYYYMMDD_HHMMSS.sql

# Reverter migrations
python manage.py migrate orders_manager zero
python manage.py migrate core zero
```

---

## 📊 Métricas de Sucesso da Migração

| Métrica | Target | Como medir |
|---------|--------|-----------|
| Zero data loss | 100% | Contagem de orders, somas de valores |
| Uptime durante migração | >99.9% | Logs de erro, monitoramento |
| Performance mantida | <10% degradação | Tempo de resposta de APIs |
| Bugs introduzidos | 0 críticos, <5 menores | Issues reportadas |
| Tempo de rollback | <30 min | Simulação de rollback |

---

## 📞 Suporte Durante Migração

- **Equipe técnica**: disponível 24/7 durante Fases 2-4
- **Hotline**: criar canal Slack #migration-support
- **Documentação**: manter changelog detalhado de cada mudança

---

**Última atualização**: 27/02/2026  
**Responsável pela migração**: Equipe de Desenvolvimento Léguas Franzinas
