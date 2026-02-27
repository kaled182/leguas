# 🏗️ Arquitetura do Sistema - Léguas Franzinas

## Visão Geral da Arquitetura

Sistema modular Django para gestão logística multi-partner com foco em escalabilidade, rastreabilidade e automação financeira.

---

## 📐 Diagrama de Entidade-Relacionamento (ER)

### Arquitetura Completa (Futura)

```mermaid
erDiagram
    Partner ||--o{ Order : "possui"
    Partner ||--o{ PartnerTariff : "configurado com"
    Partner ||--o{ PartnerInvoice : "recebe"
    Partner ||--o{ PartnerIntegration : "integra via"
    
    PostalZone ||--o{ PartnerTariff : "aplicada em"
    PostalZone ||--o{ DriverShift : "atribuida a"
    
    Order ||--|| OrderStatus : "tem histórico"
    Order ||--o| OrderIncident : "pode ter"
    Order ||--|| DriverSettlement : "contabilizado em"
    
    DriverProfile ||--o{ DriverShift : "trabalha em"
    DriverProfile ||--o{ VehicleAssignment : "usa veículo em"
    DriverProfile ||--o{ DriverSettlement : "recebe"
    DriverProfile ||--o{ DriverClaim : "tem descontos"
    
    Vehicle ||--o{ VehicleAssignment : "atribuido em"
    Vehicle ||--o{ VehicleMaintenance : "tem manutenções"
    Vehicle ||--o{ VehicleIncident : "tem incidentes"
    
    DriverShift }|--|| Vehicle : "usa"
    DriverShift }|--|| Partner : "para"
    
    Partner {
        int id PK
        string name
        string nif UK
        string contact_email
        string contact_phone
        json api_credentials
        boolean is_active
        datetime created_at
    }
    
    PartnerIntegration {
        int id PK
        int partner_id FK
        string integration_type "API, FTP, EMAIL"
        string endpoint_url
        json auth_config
        int sync_frequency_minutes
        datetime last_sync
    }
    
    PostalZone {
        int id PK
        string name
        string code_pattern "4000-*, 1000-1999"
        string region
        decimal latitude
        decimal longitude
    }
    
    PartnerTariff {
        int id PK
        int partner_id FK
        int postal_zone_id FK
        decimal base_price
        decimal success_bonus
        decimal failure_penalty
        datetime valid_from
        datetime valid_until
    }
    
    Order {
        int id PK
        int partner_id FK
        string external_reference UK
        string recipient_name
        string recipient_address
        string postal_code
        string tracking_code
        decimal declared_value
        datetime scheduled_delivery
        string current_status
        int assigned_driver_id FK
        datetime created_at
    }
    
    OrderStatus {
        int id PK
        int order_id FK
        string status "PENDING, IN_TRANSIT, DELIVERED, INCIDENT"
        string notes
        datetime changed_at
        int changed_by_id FK
    }
    
    OrderIncident {
        int id PK
        int order_id FK
        string reason "ABSENT, WRONG_ADDRESS, DAMAGED, REFUSED"
        string description
        boolean driver_responsible
        decimal claim_amount
        datetime occurred_at
    }
    
    Vehicle {
        int id PK
        string license_plate UK
        string brand
        string model
        int year
        string vehicle_type "CAR, VAN, MOTORCYCLE, ELECTRIC"
        date inspection_expiry
        date insurance_expiry
        string status "ACTIVE, MAINTENANCE, INACTIVE"
        decimal monthly_cost
    }
    
    VehicleAssignment {
        int id PK
        int vehicle_id FK
        int driver_id FK
        date assignment_date UK
        time start_time
        time end_time
        int odometer_start
        int odometer_end
    }
    
    VehicleMaintenance {
        int id PK
        int vehicle_id FK
        string maintenance_type "INSPECTION, REPAIR, CLEANING"
        decimal cost
        date scheduled_date
        date completed_date
        string notes
    }
    
    VehicleIncident {
        int id PK
        int vehicle_id FK
        int driver_id FK
        string incident_type "FINE, ACCIDENT, DAMAGE"
        decimal amount
        string description
        boolean driver_responsible
        datetime occurred_at
    }
    
    DriverShift {
        int id PK
        int driver_id FK
        int vehicle_id FK
        int partner_id FK
        date shift_date UK
        json assigned_postal_zones
        time start_time
        time end_time
        int total_deliveries
        int successful_deliveries
        decimal total_earned
    }
    
    DriverSettlement {
        int id PK
        int driver_id FK
        int week_number
        int year
        date period_start
        date period_end
        decimal gross_amount
        decimal claims_deducted
        decimal net_amount
        string status "DRAFT, APPROVED, PAID"
        datetime paid_at
    }
    
    DriverClaim {
        int id PK
        int driver_id FK
        int settlement_id FK
        string claim_type "ORDER_LOSS, FINE, DAMAGE"
        int order_id FK
        int vehicle_incident_id FK
        decimal amount
        string justification
        string status "PENDING, APPROVED, REJECTED"
    }
```

---

## 🗂️ Estrutura de Apps Django

```
leguas/
├── core/                      # App central (Partners, Configs)
│   ├── models.py
│   │   ├── Partner
│   │   └── PartnerIntegration
│   ├── admin.py
│   ├── views.py
│   └── serializers.py
│
├── orders_manager/            # Gestão genérica de pedidos
│   ├── models.py
│   │   ├── Order
│   │   ├── OrderStatus
│   │   └── OrderIncident
│   ├── services/
│   │   ├── order_importer.py  # Factory pattern por Partner
│   │   ├── paack_importer.py
│   │   ├── amazon_importer.py
│   │   └── generic_importer.py
│   └── management/
│       └── commands/
│           └── import_orders.py
│
├── fleet_management/          # Gestão de veículos
│   ├── models.py
│   │   ├── Vehicle
│   │   ├── VehicleAssignment
│   │   ├── VehicleMaintenance
│   │   └── VehicleIncident
│   ├── views.py
│   └── dashboards/
│       └── fleet_status.html
│
├── pricing/                   # Zonas e tarifas
│   ├── models.py
│   │   ├── PostalZone
│   │   ├── PartnerTariff
│   │   └── TariffModifier
│   ├── calculators/
│   │   └── price_calculator.py
│   └── management/
│       └── commands/
│           └── import_postal_zones.py
│
├── route_allocation/          # Turnos e rotas
│   ├── models.py
│   │   ├── DriverShift
│   │   └── ShiftPerformance
│   ├── algorithms/
│   │   └── route_optimizer.py
│   └── views.py
│
├── settlements/               # Financeiro (já existe, evoluir)
│   ├── models.py
│   │   ├── PartnerInvoice     # NOVO
│   │   ├── DriverSettlement   # EVOLUIR
│   │   └── DriverClaim        # NOVO
│   ├── calculators/
│   │   ├── settlement_calculator.py
│   │   └── claim_processor.py
│   └── reports/
│       └── pdf_generator.py
│
├── drivers_app/               # Motoristas (já existe)
│   └── models.py
│       └── DriverProfile
│
└── analytics/                 # Dashboards e forecasting (NOVO)
    ├── views.py
    ├── forecasting/
    │   └── volume_predictor.py
    └── templates/
        └── analytics/
```

---

## 🔄 Fluxo de Dados Principal

### 1. Importação de Pedidos

```mermaid
sequenceDiagram
    participant P as Partner (API/FTP)
    participant I as OrderImporter
    participant O as Order Model
    participant D as Dashboard
    
    P->>I: Envia dados de pedidos
    I->>I: Valida e normaliza
    I->>O: Cria Order + OrderStatus
    O->>D: Atualiza métricas em tempo real
    D->>D: Dispara alertas se volume anormal
```

### 2. Atribuição de Turno

```mermaid
sequenceDiagram
    participant A as Admin
    participant R as RouteAllocator
    participant DS as DriverShift
    participant WA as WhatsApp
    
    A->>R: Define turno (Motorista, Data, Zonas)
    R->>R: Valida disponibilidade
    R->>DS: Cria DriverShift
    DS->>WA: Envia notificação ao motorista
    WA->>Driver: "Amanhã: Veículo ABC-1234, Zonas: 4000-*"
```

### 3. Processamento de Entrega

```mermaid
sequenceDiagram
    participant D as Motorista
    participant O as Order
    participant OS as OrderStatus
    participant S as Settlement
    
    D->>O: Confirma entrega via app
    O->>OS: Adiciona status DELIVERED
    OS->>S: Calcula valor baseado em Tarifa
    S->>S: Acumula no settlement da semana
```

### 4. Cálculo de Settlement Semanal

```mermaid
sequenceDiagram
    participant Cron as Celery Beat (Domingo 23:59)
    participant SC as SettlementCalculator
    participant O as Orders (Week)
    participant PT as PartnerTariff
    participant DC as DriverClaims
    participant DS as DriverSettlement
    participant WA as WhatsApp
    
    Cron->>SC: Trigger cálculo semanal
    SC->>O: Busca orders DELIVERED da semana
    SC->>PT: Busca tarifas aplicáveis
    SC->>SC: Calcula gross_amount
    SC->>DC: Busca claims pendentes
    SC->>SC: Calcula net_amount
    SC->>DS: Cria DriverSettlement
    DS->>WA: Envia PDF extrato
```

---

## 🎨 Camadas de Abstração

### Layer 1: Models (Data)
- **Responsabilidade**: Estrutura de dados, validações básicas
- **Exemplo**: `Order.clean()` valida se postal_code existe em PostalZone

### Layer 2: Services (Business Logic)
- **Responsabilidade**: Regras de negócio complexas
- **Exemplo**: `OrderImporter` - lida com diferentes formatos de Partners

### Layer 3: Calculators (Computação)
- **Responsabilidade**: Cálculos financeiros e matemáticos
- **Exemplo**: `PriceCalculator` - aplica tarifas + modificadores

### Layer 4: Views (Presentation)
- **Responsabilidade**: Interface com usuário/API
- **Exemplo**: `OrderListView` - exibe pedidos com filtros

### Layer 5: Tasks (Async)
- **Responsabilidade**: Operações pesadas em background
- **Exemplo**: `calculate_weekly_settlements.delay()`

---

## 🔐 Segurança e Permissões

### Níveis de Acesso

| Role | Permissões |
|------|-----------|
| **Super Admin** | Tudo |
| **Admin Financeiro** | Ver/Editar Settlements, Tarifas, Invoices |
| **Admin Operacional** | Ver/Editar Orders, Shifts, Fleet |
| **Motorista** | Ver próprios Shifts, Settlements, Orders |
| **Partner (API)** | Criar Orders, Ver status de seus Orders |

### Auditoria
- Todas as operações críticas (`OrderStatus`, `DriverClaim`, `Settlement`) têm:
  - `created_by` (quem fez)
  - `created_at` (quando)
  - `modified_by` / `modified_at`

---

## 📊 Performance e Escalabilidade

### Database Indexing
```python
# Indexes críticos
Order.Meta.indexes = [
    Index(fields=['partner', 'created_at']),
    Index(fields=['assigned_driver', 'current_status']),
    Index(fields=['postal_code']),
]

DriverShift.Meta.indexes = [
    Index(fields=['driver', 'shift_date']),
    Index(fields=['partner', 'shift_date']),
]
```

### Caching Strategy
- **Redis**: Cache de tarifas (expiração: 1 hora)
- **DB Query Cache**: Dashboard metrics (5 minutos)
- **Static Files**: CDN (CloudFlare)

### Background Tasks (Celery)
```python
# celery.py
app.conf.beat_schedule = {
    'calculate-weekly-settlements': {
        'task': 'settlements.tasks.calculate_weekly_settlements',
        'schedule': crontab(day_of_week=0, hour=23, minute=59),
    },
    'sync-partner-orders': {
        'task': 'orders.tasks.sync_all_partners',
        'schedule': crontab(minute='*/15'),  # A cada 15 min
    },
    'check-vehicle-expiries': {
        'task': 'fleet.tasks.alert_expiring_documents',
        'schedule': crontab(hour=8, minute=0),  # Diário 8h
    },
}
```

---

## 🧪 Testing Strategy

### Pirâmide de Testes

```
        /\
       /  \  E2E (5%)
      /____\
     /      \  Integration (15%)
    /________\
   /          \ Unit (80%)
  /______________\
```

### Exemplos

**Unit Test**:
```python
def test_price_calculator_applies_tariff():
    order = Order(postal_code='4000-001', partner=paack)
    tariff = PartnerTariff(partner=paack, base_price=5.0)
    calc = PriceCalculator()
    assert calc.calculate(order, tariff) == 5.0
```

**Integration Test**:
```python
def test_order_to_settlement_flow():
    order = create_order(driver=driver1, status='DELIVERED')
    settlement = SettlementCalculator().calculate_for_week(driver1, week=10)
    assert settlement.gross_amount == expected_value
```

**E2E Test**:
```python
def test_admin_creates_shift_driver_receives_whatsapp():
    # Selenium test simulando criação de turno
    admin.create_shift(driver=driver1, date='2026-03-01')
    # Mock do WhatsApp
    assert whatsapp_mock.sent_messages[0].contains('Veículo')
```

---

## 📈 Monitoring e Logs

### Métricas (Prometheus + Grafana)
- Latência de APIs
- Taxa de sucesso de importação
- Número de orders por status
- Taxa de erro em settlements

### Logs Estruturados (JSON)
```json
{
  "timestamp": "2026-02-27T15:30:00Z",
  "level": "INFO",
  "service": "orders_manager",
  "action": "order_created",
  "partner_id": 1,
  "order_id": 12345,
  "user": "admin@leguas.pt"
}
```

### Alertas (Sentry)
- Erro em cálculo de settlement
- Falha em sincronização de Partner
- Timeout em API de importação

---

## 🔄 Migração de Dados

### Estratégia de Migração (`ordersmanager_paack` → `orders_manager`)

```python
# management/commands/migrate_paack_orders.py

from django.core.management.base import BaseCommand
from ordersmanager_paack.models import PaackOrder
from orders_manager.models import Order
from core.models import Partner

class Command(BaseCommand):
    def handle(self, *args, **options):
        # 1. Criar Partner "Paack"
        paack, _ = Partner.objects.get_or_create(
            name="Paack",
            nif="123456789",
            defaults={'api_credentials': {...}}
        )
        
        # 2. Migrar orders
        for old_order in PaackOrder.objects.all():
            Order.objects.get_or_create(
                external_reference=old_order.tracking_code,
                defaults={
                    'partner': paack,
                    'recipient_name': old_order.recipient,
                    'postal_code': old_order.postal_code,
                    # ... mapeamento de campos
                }
            )
        
        self.stdout.write(self.style.SUCCESS('Migração concluída!'))
```

---

## 📚 Documentação Adicional

- [MODELS_REFERENCE.md](./MODELS_REFERENCE.md) - Referência completa de todos os models
- [API_ENDPOINTS.md](./API_ENDPOINTS.md) - Documentação de APIs REST
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Guia de deploy e configuração de servidores

---

**Última atualização**: 27/02/2026  
**Versão da Arquitetura**: 2.0 (Multi-Partner)
