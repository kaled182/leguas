# Guia de Testes - Sistema Financeiro (Fase 6)

## Visão Geral
Sistema completo de gestão financeira para faturas de partners, acertos de motoristas e descontos/claims.

---

## 1. Modelos Criados

### ✅ PartnerInvoice (Faturas a Receber)
**Campos principais**:
- `partner`: Partner a faturar
- `invoice_number`: Número auto-gerado (PARTNER-YYYYMMDD-###)
- `period_start/end`: Período de faturação
- `gross_amount`, `tax_amount`, `net_amount`: Valores
- `status`: DRAFT → GENERATED → SENT → PAID → OVERDUE → CANCELLED

**Métodos**:
- `calculate_totals()`: Calcula totais baseado em pedidos do período
- `mark_as_paid()`: Marca como paga
- `check_overdue()`: Verifica se está atrasada

---

### ✅ DriverSettlement (Acertos de Motoristas)
**Campos principais**:
- `driver`: Motorista
- `partner`: Partner (opcional para multi-partner)
- `period_type`: WEEKLY ou MONTHLY
- `week_number/year`: Para acertos semanais
- `gross_amount`, `bonus_amount`, `net_amount`: Valores
- `total_deliveries`, `success_rate`: Performance
- `status`: DRAFT → CALCULATED → APPROVED → PAID → CANCELLED

**Cálculo Automático**:
- Valor bruto baseado em tarifas por zona postal
- Bônus por performance:
  - 2% para taxa sucesso ≥ 85%
  - 5% para taxa sucesso ≥ 90%
  - 10% para taxa sucesso ≥ 95%
- Descontos: combustível + claims + outros

**Métodos**:
- `calculate_settlement()`: Calcula valores automaticamente
- `approve()`: Aprova acerto
- `mark_as_paid()`: Marca como pago

---

### ✅ DriverClaim (Descontos/Multas)
**Tipos de claims** (9 categorias):
1. `ORDER_LOSS`: Perda de mercadoria
2. `VEHICLE_FINE`: Multa de trânsito
3. `VEHICLE_DAMAGE`: Dano ao veículo
4. `UNIFORM_DAMAGE`: Dano ao uniforme
5. `LATE_DELIVERY`: Atraso na entrega
6. `CUSTOMER_COMPLAINT`: Reclamação de cliente
7. `FUEL_EXCESS`: Excesso de combustível
8. `EQUIPMENT_LOSS`: Perda de equipamento
9. `OTHER`: Outros

**Status workflow**:
- PENDING → APPROVED → DEDUCTED
- PENDING → REJECTED → APPEALED → APPROVED/REJECTED

**Métodos**:
- `approve()`: Aprova claim
- `reject()`: Rejeita claim
- `appeal()`: Cria apelação

---

## 2. Calculators (Engines de Cálculo)

### ✅ SettlementCalculator
**Localização**: `settlements/calculators/settlement_calculator.py`

**Principais funções**:
```python
from settlements.calculators import SettlementCalculator

# Calcular acerto semanal de um motorista
settlement = SettlementCalculator.calculate_weekly_settlement(
    driver_id=1,
    week_number=9,
    year=2026
)

# Calcular acerto mensal
settlement = SettlementCalculator.calculate_monthly_settlement(
    driver_id=1,
    month=2,
    year=2026
)

# Calcular para todos os motoristas
settlements = SettlementCalculator.calculate_all_weekly_settlements(
    week_number=9,
    year=2026
)
```

---

### ✅ ClaimProcessor
**Localização**: `settlements/calculators/claim_processor.py`

**Principais funções**:
```python
from settlements.calculators import ClaimProcessor

# Auto-criar claim de pedido falhado
claim = ClaimProcessor.create_claim_from_order(
    order_id=123,
    claim_type='ORDER_LOSS',
    amount=50.00
)

# Auto-criar claim de multa de veículo
claim = ClaimProcessor.create_claim_from_vehicle_incident(
    incident_id=45,
    driver_id=1
)

# Aprovar claim
ClaimProcessor.approve_claim(claim_id=10, approved_by_user_id=1)

# Aplicar claims a um settlement
ClaimProcessor.apply_claims_to_settlement(settlement_id=5)

# Auto-criar claims dos últimos 7 dias
claims = ClaimProcessor.auto_create_claims_from_failed_orders(
    days_back=7
)
```

---

### ✅ InvoiceCalculator
**Localização**: `settlements/calculators/invoice_calculator.py`

**Principais funções**:
```python
from settlements.calculators import InvoiceCalculator

# Gerar invoice de partner
invoice = InvoiceCalculator.calculate_partner_invoice(
    partner_id=1,
    start_date='2026-02-01',
    end_date='2026-02-28'
)

# Gerar invoices para todos os partners
invoices = InvoiceCalculator.calculate_monthly_invoices_all_partners(
    month=2,
    year=2026
)

# Reconciliar invoice (marcar pago)
InvoiceCalculator.reconcile_invoice(
    invoice_id=10,
    paid_amount=1500.50,
    payment_date='2026-03-05'
)

# Verificar invoices atrasadas
overdue = InvoiceCalculator.check_overdue_invoices()
```

---

## 3. Management Commands

### ✅ calculate_weekly_settlements
**Descrição**: Calcula acertos semanais para motoristas

**Uso**:
```bash
# Calcular semana atual para todos os motoristas
python manage.py calculate_weekly_settlements

# Calcular semana específica
python manage.py calculate_weekly_settlements --week 9 --year 2026

# Calcular apenas um motorista
python manage.py calculate_weekly_settlements --driver-id 1 --week 9 --year 2026

# Modo teste (não salva no banco)
python manage.py calculate_weekly_settlements --week 9 --year 2026 --dry-run
```

**Output esperado**:
```
=== Cálculo de Settlements Semanais ===
Semana: 9/2026 (2026-02-23 a 2026-03-01)

✅ Settlement calculado para João Silva (ID: 1)
   - Entregas: 45
   - Taxa sucesso: 95.6%
   - Valor bruto: €1,250.00
   - Bônus: €125.00 (10%)
   - Líquido: €1,320.50

Resumo:
- Settlements criados: 12
- Valor total líquido: €15,340.80
```

---

### ✅ calculate_monthly_invoices
**Descrição**: Calcula invoices mensais para partners

**Uso**:
```bash
# Calcular mês anterior para todos os partners
python manage.py calculate_monthly_invoices

# Calcular mês específico
python manage.py calculate_monthly_invoices --month 2 --year 2026

# Calcular apenas um partner
python manage.py calculate_monthly_invoices --partner-id 3 --month 2 --year 2026

# Modo teste
python manage.py calculate_monthly_invoices --month 2 --year 2026 --dry-run
```

**Output esperado**:
```
=== Cálculo de Invoices Mensais ===
Período: 2026-02-01 a 2026-02-28

✅ Invoice gerada para DPD Portugal
   - Número: DPD-20260301-001
   - Pedidos: 234
   - Bruto: €3,450.00
   - IVA (23%): €793.50
   - Total: €4,243.50

⚠️  Invoices atrasadas verificadas:
   - FEDEX-20260201-001: €2,100.00 (15 dias)

Resumo:
- Invoices geradas: 4
- Valor total: €18,567.90
- Atrasadas: 2 (€4,890.00)
```

---

### ✅ process_pending_claims
**Descrição**: Processa claims pendentes e auto-cria de pedidos falhados

**Uso**:
```bash
# Auto-criar claims dos últimos 7 dias
python manage.py process_pending_claims --auto-create

# Definir período específico
python manage.py process_pending_claims --auto-create \
    --start-date 2026-02-01 --end-date 2026-02-28

# Processar apenas um motorista
python manage.py process_pending_claims --driver-id 1

# Modo teste
python manage.py process_pending_claims --auto-create --dry-run
```

**Output esperado**:
```
=== Processamento de Claims ===

Auto-criando claims de pedidos falhados (2026-02-20 a 2026-02-27)...

✅ 12 claims criados automaticamente
   - Perdas de mercadoria: 5
   - Atrasos: 4
   - Reclamações: 3

Claims pendentes por motorista:
- João Silva: 3 claims (€150.00 total)
- Maria Santos: 1 claim (€35.00 total)

Resumo:
- Claims pendentes: 8 (€340.00)
- Claims aprovados: 15 (€780.00)
- Claims aplicados a settlements: 12
```

---

## 4. Admin Interfaces

### Acesso
URL: `http://localhost:8000/admin/settlements/`

### ✅ PartnerInvoice Admin
**Funcionalidades**:
- ✅ Filtros: status, partner, período, atrasadas
- ✅ Busca: número invoice, referência externa
- ✅ Hierarquia de datas
- ✅ Color badges para status:
  - 🩶 DRAFT
  - 🟠 GENERATED
  - 🟡 SENT
  - 🟢 PAID
  - 🔴 OVERDUE
  - ⚫ CANCELLED

**Ações em massa**:
1. Marcar como paga
2. Verificar atrasadas
3. Recalcular totais

---

### ✅ DriverSettlement Admin
**Funcionalidades**:
- ✅ Inline de claims relacionados
- ✅ Exibição de estatísticas de performance
- ✅ Filtros: período, motorista, partner, status
- ✅ Color badges para status

**Ações em massa**:
1. Recalcular settlement
2. Aprovar settlement
3. Marcar como pago

**Campos customizados**:
- `display_performance`: Taxa de sucesso + badge colorido
- `display_bonus`: Percentual de bônus
- `display_claims`: Total de descontos

---

### ✅ DriverClaim Admin
**Funcionalidades**:
- ✅ Filtros: tipo, status, motorista, período
- ✅ Links para pedidos e incidentes relacionados
- ✅ Upload de evidências
- ✅ Color badges para status:
  - 🟡 PENDING
  - 🟢 APPROVED
  - 🔴 REJECTED
  - 🔵 APPEALED
  - ✅ DEDUCTED

**Ações em massa**:
1. Aprovar claims
2. Rejeitar claims

**Campos customizados**:
- `display_order`: Link para pedido (se existe)
- `display_incident`: Link para incidente (se existe)
- `display_settlement`: Link para settlement aplicado

---

## 5. PDF Generation

### ✅ PDFGenerator
**Localização**: `settlements/reports/pdf_generator.py`

**Requisito**: `reportlab` (já instalado)

**Uso Programático**:
```python
from settlements.reports.pdf_generator import PDFGenerator

# Gerar PDF de settlement
pdf = PDFGenerator()
pdf_file = pdf.generate_settlement_pdf(settlement_id=10)
# Retorna: ContentFile pronto para salvar em FileField

# Gerar PDF de invoice
pdf_file = pdf.generate_invoice_pdf(invoice_id=5)

# Salvar diretamente no campo do model
from settlements.models import DriverSettlement
settlement = DriverSettlement.objects.get(id=10)
PDFGenerator.save_to_field(settlement, 'pdf_file', settlement.id)
```

**Conteúdo do PDF de Settlement**:
- Header com logo (se disponível)
- Informações do motorista
- Período do acerto
- Estatísticas de performance
- Detalhamento financeiro:
  - Valor bruto por zona
  - Bônus por performance
  - Descontos (combustível, claims, outros)
  - Valor líquido final
- Tabela detalhada de claims deduzidos
- Footer com data de geração

**Conteúdo do PDF de Invoice**:
- Header com logo
- Número da invoice e referências
- Informações do partner
- Período de faturação
- Tabela de valores:
  - Valor bruto
  - IVA (23%)
  - Total a pagar
- Estatísticas de entregas
- Informações de pagamento
- Footer

---

## 6. Testes Recomendados

### 6.1 Teste de Cálculo de Settlement
```bash
# 1. Modo dry-run primeiro
docker exec leguas_web python manage.py calculate_weekly_settlements \
    --week 9 --year 2026 --dry-run

# 2. Se tudo OK, executar de verdade
docker exec leguas_web python manage.py calculate_weekly_settlements \
    --week 9 --year 2026

# 3. Verificar no admin
# Acessar: http://localhost:8000/admin/settlements/driversettlement/
```

---

### 6.2 Teste de Auto-criação de Claims
```bash
# 1. Verificar pedidos falhados recentes
docker exec leguas_web python manage.py shell
>>> from orders_manager.models import Order
>>> Order.objects.filter(status__in=['CANCELLED', 'FAILED']).count()

# 2. Auto-criar claims em dry-run
docker exec leguas_web python manage.py process_pending_claims \
    --auto-create --dry-run

# 3. Se OK, executar
docker exec leguas_web python manage.py process_pending_claims \
    --auto-create
```

---

### 6.3 Teste de Invoice Generation
```bash
# 1. Verificar pedidos do mês anterior
docker exec leguas_web python manage.py shell
>>> from orders_manager.models import Order
>>> Order.objects.filter(
...     created_at__month=2,
...     created_at__year=2026,
...     status='DELIVERED'
... ).count()

# 2. Gerar invoices em dry-run
docker exec leguas_web python manage.py calculate_monthly_invoices \
    --month 2 --year 2026 --dry-run

# 3. Se OK, executar
docker exec leguas_web python manage.py calculate_monthly_invoices \
    --month 2 --year 2026
```

---

### 6.4 Teste de PDF Generation
```bash
docker exec leguas_web python manage.py shell
```
```python
from settlements.models import DriverSettlement
from settlements.reports.pdf_generator import PDFGenerator

# Pegar um settlement existente
settlement = DriverSettlement.objects.first()

if settlement:
    # Gerar PDF
    pdf = PDFGenerator()
    pdf_file = pdf.generate_settlement_pdf(settlement.id)
    
    # Salvar no campo
    settlement.pdf_file.save(
        f'settlement_{settlement.id}.pdf',
        pdf_file,
        save=True
    )
    
    print(f"✅ PDF gerado: {settlement.pdf_file.url}")
else:
    print("⚠️  Nenhum settlement encontrado. Execute calculate_weekly_settlements primeiro.")
```

---

### 6.5 Teste de Admin Workflow
1. **Acesse o admin**: `http://localhost:8000/admin/settlements/`

2. **DriverClaim workflow**:
   - Criar claim manual
   - Upload de evidência
   - Aprovar claim
   - Verificar se aparece no settlement

3. **DriverSettlement workflow**:
   - Visualizar settlement calculado
   - Ver claims inline
   - Recalcular (ação em massa)
   - Aprovar
   - Marcar como pago
   - Download do PDF

4. **PartnerInvoice workflow**:
   - Visualizar invoice gerada
   - Verificar totais
   - Marcar como enviada
   - Reconciliar pagamento
   - Verificar se marca OVERDUE automaticamente

---

## 7. Integração com Dados Reais

### Verificar Tarifas
Para que os cálculos funcionem corretamente, é necessário ter tarifas cadastradas:

```python
from pricing.models import PartnerTariff
from core.models import Partner

# Verificar tarifas existentes
tarifas = PartnerTariff.objects.all()
print(f"Tarifas cadastradas: {tarifas.count()}")

# Exemplo de criação de tarifa (se necessário)
partner = Partner.objects.first()
if partner and not PartnerTariff.objects.filter(partner=partner).exists():
    PartnerTariff.objects.create(
        partner=partner,
        postal_code_range='1000-1999',
        base_price=15.00,
        success_bonus=2.00,
        failure_penalty=5.00,
        is_active=True
    )
```

---

## 8. Próximos Passos (Fase 7)

- [ ] **WhatsApp Integration**: Envio automático de PDFs de settlement
- [ ] **Celery Tasks**: Automação semanal/mensal
- [ ] **Email Notifications**: Alertas de invoices atrasadas
- [ ] **Dashboard Views**: Gráficos financeiros
- [ ] **Export Excel/CSV**: Relatórios exportáveis
- [ ] **API REST**: Endpoints para mobile app

---

## 9. Troubleshooting

### Erro: "No PartnerTariff found"
**Causa**: Não existem tarifas cadastradas para o partner/zona postal  
**Solução**: Cadastrar tarifas no admin em `/admin/pricing/partnertariff/`

### Erro: "reportlab not found"
**Causa**: Biblioteca não instalada  
**Solução**: `docker exec leguas_web pip install reportlab`

### Settlement com valor 0
**Causa**: Nenhum pedido DELIVERED no período  
**Solução**: Verificar pedidos com `Order.objects.filter(status='DELIVERED')`

### Claims não aparecem no settlement
**Causa**: Claims não estão APPROVED ou não têm `settlement` associado  
**Solução**: Usar `ClaimProcessor.apply_claims_to_settlement(settlement_id)`

---

## 10. Commits Relacionados

1. **e18b808**: feat: Implement Fase 6 - Financial System (Settlements & Claims)
   - 12 arquivos alterados
   - 3,020 inserções
   - Modelos, calculators, commands, admin, PDF

2. **677d0c7**: docs: Update ROADMAP - Mark Fase 6 as completed
   - ROADMAP atualizado com status ✅

---

## Suporte

Para dúvidas ou issues:
1. Verificar logs no container: `docker logs leguas_web`
2. Debug mode nos calculators com `get_debug_log()`
3. Django shell para testes manuais
4. Admin interface para visualização

**Sistema pronto para uso em produção! 🎉**
