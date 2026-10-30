# Inventário de páginas e rotas — baseline

**Estado:** Fase 0. Gerado com commit `469a7d8`, em 2026-10-30.
**Dados:** seed sintético em SQLite, sem dados de produção. Valores de KPI e tempos não representam produção.
**Dados brutos:** `docs/rebrand/dados/baseline.json`.

## 1. Stack

| Camada | Tecnologia | Evidência |
|---|---|---|
| Backend | Django 5.2.18, DRF 3.16, Celery 5.4, MySQL 8 | `requirements.txt`, `production/docker-compose.yml` |
| Templates | Django Templates, 202 ficheiros `.html` | `my_project/settings.py` |
| CSS | Tailwind por CDN em 14 templates, mais `@tailwindcss/browser@4` em 1 | `templates/layouts/admin_base.html:35` |
| Tailwind compilado | App `theme` com `tailwindcss ^3.3.2`, sem build no deploy e config vazia | `theme/tailwind.config.js` |
| CSS próprio | `static/css/base.css`, `modern-dashboard.css`, blocos `<style>` nos templates | `static/css/` |
| JS | Alpine.js, Chart.js, `static/js/sidebar.js`, `base.js` | `admin_base.html:108-114` |
| Versões por CDN | `lucide@latest`, `alpinejs@3.x.x` e `chart.js` sem versão fixa | `admin_base.html:108-114` |
| Ícones | Lucide | `unpkg.com/lucide@latest` |
| Fontes | Inter (Google Fonts). Poppins só em 2 templates | `admin_base.html:32` |
| Tema escuro | Classe `dark` no `<html>`. 3 chaves de `localStorage`: `management-theme`, `financial-theme`, `darkMode` | `admin_base.html:19`, `settlements/base.html:15`, `static/js/base.js:18` |
| Debug toolbar | Não existe. Queries medidas com `CaptureQueriesContext` | `my_project/settings.py` |

**AVISO:** `lucide@latest`, `alpinejs@3.x.x` e `chart.js` mudam sem aviso. Uma versão nova pode partir o sistema em produção sem deploy.

## 2. Totais

| Métrica | Valor |
|---|---|
| Rotas no projeto | 901 |
| Rotas do Django admin (fora do rebrand visual) | 335 |
| Rotas de aplicação testadas | 566 |
| Páginas HTML | 164 |
| Rotas sem página (JSON, CSV, PDF, POST, parâmetros obrigatórios) | 402 |
| Capturas de ecrã | 640 |
| Páginas com erro real de consola | 7 |
| Páginas com pedido falhado | 3 |
| Queries por página: mediana / máximo | 0 / 390 |
| Carregamento desktop: mediana / máximo | 1.3 s / 6.1 s |
| Páginas com scroll horizontal em telemóvel | 84 |

**Páginas por grupo:** Finanças 53, Portal do motorista 17, Operação 11, Operação/Finanças 10, Rede 10, Autenticação 9, Clientes 9, Portal da frota 8, Sistema 8, Frota 6, Tarifas 6, Motoristas 5, Relatórios 5, Contratos 3, Outros 2, Ferramentas 1, Hoje 1.

**Estado das rotas sem página, com o perfil superuser:** 200: 89, 302: 9, 400: 15, 401: 10, 404: 4, 405: 250, 500: 18, 502: 1, não testada: 6.

## 3. Limitações

- O seed cria 2 registos por modelo. Listas longas e páginas com filtros não mostram o volume real.
- 19 rotas respondem 400 ou 404 sem parâmetros válidos. Não têm captura. Estão na secção 7.
- Modais não têm captura própria. A coluna "Componentes" indica as páginas com modal.
- O tempo de carregamento vem do servidor local de desenvolvimento e não do Gunicorn.
- O erro COOP da consola existe só em HTTP local e foi excluído.

## 4. Páginas

| URL | View | Template | Grupo | Componentes | Perfis |
|---|---|---|---|---|---|
| `/auth/` | `customauth.authenticate_view` | `customauth/login.html` | Autenticação | Formulário | Público, Superuser, Staff, Autenticado, Motorista, Frota |
| `/auth/authenticate/` | `customauth.authenticate_view` | `customauth/login.html` | Autenticação | Formulário | Público, Superuser, Staff, Autenticado, Motorista, Frota |
| `/auth/driver/` | `customauth.driver_auth_views.driver_login` | `customauth/driver_login.html` | Autenticação | Formulário, Hero/gradiente, Separadores | Público, Superuser, Staff, Autenticado, Motorista, Frota |
| `/auth/driver/credentials/<int:driver_id>/` | `customauth.driver_auth_views.admin_driver_credentials` | `customauth/admin_driver_credentials.html` | Autenticação | Formulário, Hero/gradiente | Superuser, Staff |
| `/auth/driver/login/` | `customauth.driver_auth_views.driver_login` | `customauth/driver_login.html` | Autenticação | Formulário, Hero/gradiente, Separadores | Público, Superuser, Staff, Autenticado, Motorista, Frota |
| `/auth/empresa/` | `customauth.empresa_auth_views.empresa_login` | `customauth/empresa_login.html` | Autenticação | Formulário, Hero/gradiente | Público, Superuser, Staff, Autenticado, Motorista, Frota |
| `/auth/empresa/credentials/<int:empresa_id>/` | `customauth.empresa_auth_views.admin_empresa_credentials` | `customauth/admin_empresa_credentials.html` | Autenticação | Formulário, Hero/gradiente | Superuser, Staff |
| `/auth/empresa/login/` | `customauth.empresa_auth_views.empresa_login` | `customauth/empresa_login.html` | Autenticação | Formulário, Hero/gradiente | Público, Superuser, Staff, Autenticado, Motorista, Frota |
| `/auth/login/` | `customauth.authenticate_view` | `customauth/login.html` | Autenticação | Formulário | Público, Superuser, Staff, Autenticado, Motorista, Frota |
| `/core/drivers/<int:driver_id>/account/` | `core.driver_account_statement` | `core/driver_account.html` | Clientes (sem menu) | KPI, Tabela | Superuser, Staff, Autenticado |
| `/core/financial-alerts/` | `core.financial_alerts_list` | `core/financial_alerts.html` | Clientes (sem menu) | - | Superuser, Staff, Autenticado |
| `/core/integrations/<int:pk>/edit/` | `core.integration_edit` | `core/integration_form.html` | Clientes (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/core/partners/<int:partner_pk>/integrations/create/` | `core.integration_create` | `core/integration_form.html` | Clientes (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/core/partners/<int:pk>/` | `core.partner_detail` | `core/partner_detail.html` | Clientes (sem menu) | Filtros, Formulário, Hero/gradiente, KPI, Modal, Separadores, Tabela | Superuser, Staff, Autenticado |
| `/core/partners/<int:pk>/bonus-rules/` | `core.partner_bonus_rules` | `core/partner_bonus_rules.html` | Clientes (sem menu) | Modal, Tabela | Superuser, Staff, Autenticado |
| `/core/partners/<int:pk>/edit/` | `core.partner_edit` | `core/partner_form.html` | Clientes (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/core/partners/<int:pk>/financial/` | `core.partner_financial_dashboard` | `core/partner_financial.html` | Clientes (sem menu) | Filtros, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Autenticado |
| `/core/partners/create/` | `core.partner_create` | `core/partner_form.html` | Clientes (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/contracts/admin/gerado/<int:pk>/` | `contracts_generator.generated_contract_view` | `contracts/generated_view.html` | Contratos (sem menu) | - | Superuser, Staff |
| `/contracts/admin/gerar/<int:driver_id>/` | `contracts_generator.contract_generator` | `contracts/generator.html` | Contratos (sem menu) | Filtros, Formulário | Superuser, Staff |
| `/contracts/admin/templates/<int:pk>/edit/` | `contracts.admin_template_edit` | `contracts/admin_template_form.html` | Contratos (sem menu) | Filtros, Formulário, Hero/gradiente | Superuser, Staff |
| `/converter/` | `converter.converter_view` | `converter.html` | Ferramentas (sem menu) | Formulário, Hero/gradiente | Superuser, Staff, Autenticado |
| `/accounting/` | `accounting.dashboard` | `accounting/dashboard.html` | Finanças (sem menu) | Tabela | Superuser, Staff, Autenticado |
| `/accounting/a-pagar/calendario/` | `accounting_payables.payables_calendar` | `accounting/payables_calendar.html` | Finanças (sem menu) | - | Superuser, Staff, Autenticado |
| `/accounting/a-pagar/forecast/` | `accounting_payables.payables_forecast` | `accounting/payables_forecast.html` | Finanças (sem menu) | KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/a-pagar/sem-ff/` | `accounting_payables.payables_fleets_without_invoice` | `accounting/payables_no_ff.html` | Finanças (sem menu) | Filtros, KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/a-pagar/sem-pf/` | `accounting_payables.payables_drivers_without_pf` | `accounting/payables_no_pf.html` | Finanças (sem menu) | Filtros, KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/categorias/<int:pk>/editar/` | `accounting_categories.category_edit` | `accounting/category_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/accounting/categorias/nova/` | `accounting_categories.category_create` | `accounting/category_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/accounting/centros-custo/<int:pk>/editar/` | `accounting_cost_centers.cost_center_edit` | `accounting/cost_center_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/accounting/centros-custo/novo/` | `accounting_cost_centers.cost_center_create` | `accounting/cost_center_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/accounting/contas-a-pagar/<int:pk>/` | `accounting.bill_detail` | `accounting/bill_detail.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/accounting/contas-a-pagar/<int:pk>/editar/` | `accounting.bill_edit` | `accounting/bill_form.html` | Finanças (sem menu) | Formulário, Hero/gradiente, Modal | Superuser, Staff, Autenticado |
| `/accounting/contas-a-pagar/lixeira/` | `accounting.bill_trash` | `accounting/bill_trash.html` | Finanças (sem menu) | Tabela | Superuser, Staff, Autenticado |
| `/accounting/contas-a-pagar/nova/` | `accounting.bill_create` | `accounting/bill_form.html` | Finanças (sem menu) | Formulário, Hero/gradiente, Modal | Superuser, Staff, Autenticado |
| `/accounting/despesas/<int:pk>/editar/` | `accounting.expense_edit` | `accounting/expense_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/accounting/despesas/nova/` | `accounting.expense_create` | `accounting/expense_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/accounting/extractos/<int:pk>/` | `accounting.bank_statement_detail` | `accounting/bank_statement_detail.html` | Finanças (sem menu) | Tabela | Superuser, Staff, Autenticado |
| `/accounting/extractos/upload/` | `accounting.bank_statement_upload` | `accounting/bank_statement_upload.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/accounting/fornecedores/<int:pk>/editar/` | `accounting_suppliers.fornecedor_edit` | `accounting/fornecedor_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/accounting/fornecedores/novo/` | `accounting_suppliers.fornecedor_create` | `accounting/fornecedor_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/accounting/fornecedores/tags/` | `accounting_suppliers.fornecedor_tag_list` | `accounting/fornecedor_tag_list.html` | Finanças (sem menu) | Formulário, Tabela | Superuser, Staff, Autenticado |
| `/accounting/impostos/<int:pk>/editar/` | `accounting_taxes.imposto_edit` | `accounting/imposto_form.html` | Finanças (sem menu) | Formulário, Modal | Superuser, Staff, Autenticado |
| `/accounting/impostos/novo/` | `accounting_taxes.imposto_create` | `accounting/imposto_form.html` | Finanças (sem menu) | Formulário, Modal | Superuser, Staff, Autenticado |
| `/accounting/receitas/<int:pk>/editar/` | `accounting.revenue_edit` | `accounting/revenue_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/accounting/receitas/nova/` | `accounting.revenue_create` | `accounting/revenue_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff, Autenticado |
| `/payroll/folhas/<int:pk>/` | `payroll.payroll_detail` | `payroll/payroll_detail.html` | Finanças (sem menu) | Filtros, Formulário, Tabela | Superuser, Staff |
| `/payroll/folhas/gerar/` | `payroll.payroll_generate` | `payroll/payroll_generate.html` | Finanças (sem menu) | Formulário | Superuser, Staff |
| `/payroll/funcionarios/` | `payroll.employee_list` | `payroll/employee_list.html` | Finanças (sem menu) | KPI, Tabela | Superuser, Staff |
| `/payroll/funcionarios/<int:pk>/` | `payroll.employee_edit` | `payroll/employee_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff |
| `/payroll/funcionarios/novo/` | `payroll.employee_create` | `payroll/employee_form.html` | Finanças (sem menu) | Formulário | Superuser, Staff |
| `/accounting/contas-a-pagar/` | `accounting.bill_list` | `accounting/bill_list.html` | Finanças › A pagar › Contas a pagar | Filtros, KPI, Tabela | Superuser, Staff, Autenticado |
| `/payroll/folhas/` | `payroll.payroll_list` | `payroll/payroll_list.html` | Finanças › A pagar › Folha de pagamento | Filtros, KPI, Tabela | Superuser, Staff |
| `/accounting/fornecedores/` | `accounting_suppliers.fornecedor_list` | `accounting/fornecedor_list.html` | Finanças › A pagar › Fornecedores | Filtros, Formulário, KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/a-pagar/` | `accounting_payables.payables_inbox` | `accounting/payables_inbox.html` | Finanças › A pagar › Inbox | Filtros, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Autenticado |
| `/accounting/pendentes-regularizacao/` | `accounting_payables.pending_reconciliation` | `accounting/pending_reconciliation.html` | Finanças › A pagar › Pendentes de regularização | KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/extractos/` | `accounting.bank_statement_list` | `accounting/bank_statement_list.html, accounting/_analysis_tabs.html` | Finanças › A receber › Extratos OFX | Tabela | Superuser, Staff, Autenticado |
| `/settlements/invoices/` | `settlements.invoice_list` | `settlements/invoice_list_v2.html` | Finanças › A receber › Faturas de clientes | Filtros, Formulário, Hero/gradiente, KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/reconciliacao-bancaria/` | `accounting_reconciliation.bank_reconciliation` | `accounting/bank_reconciliation.html` | Finanças › A receber › Reconciliação bancária | Filtros, Formulário, KPI | Superuser, Staff, Autenticado |
| `/accounting/break-even/` | `accounting.break_even_monitor` | `accounting/break_even.html, accounting/_analysis_tabs.html` | Finanças › Análise › Break-even | Filtros, Gráfico, KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/categorias/` | `accounting_categories.category_list` | `accounting/category_list.html` | Finanças › Análise › Categorias | Filtros, Tabela | Superuser, Staff, Autenticado |
| `/accounting/centros-custo/` | `accounting_cost_centers.cost_center_list` | `accounting/cost_center_list.html` | Finanças › Análise › Centros de custo | Filtros, Formulário, KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/dre/` | `accounting.dre` | `accounting/dre.html, accounting/_analysis_tabs.html` | Finanças › Análise › DRE | Filtros, KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/fluxo-caixa/` | `accounting.cash_flow_projection` | `accounting/cash_flow.html, accounting/_analysis_tabs.html` | Finanças › Análise › Fluxo de caixa | Filtros, KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/auditoria/` | `accounting_audit.audit_timeline` | `accounting/audit_timeline.html` | Finanças › Controlo › Auditoria | Filtros | Superuser, Staff, Autenticado |
| `/settlements/calendar/` | `settlements.holiday_views.holiday_list` | `settlements/holiday_calendar.html` | Finanças › Controlo › Calendário | Filtros, Modal, Tabela | Superuser, Staff, Autenticado |
| `/accounting/periodos/` | `accounting_period_lock.period_lock_list` | `accounting/period_lock_list.html` | Finanças › Controlo › Fechos de período | Formulário, Tabela | Superuser, Staff, Autenticado |
| `/settlements/socios/` | `settlements_shareholder.shareholder_dashboard` | `settlements/shareholder_dashboard.html` | Finanças › Controlo › Sócios e reembolsos | Filtros, KPI, Modal, Tabela | Superuser, Staff, Autenticado |
| `/accounting/impostos/` | `accounting_taxes.imposto_list` | `accounting/imposto_list.html` | Finanças › Impostos › Impostos | Filtros, Formulário, KPI, Modal, Tabela | Superuser, Staff, Autenticado |
| `/accounting/impostos/planos/` | `accounting_taxes.plano_list` | `accounting/plano_list.html` | Finanças › Impostos › Planos prestacionais | Filtros, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Autenticado |
| `/settlements/adiantamentos/` | `settlements_cash_entries.cash_entries_dashboard` | `settlements/cash_entries_dashboard.html` | Finanças › Pagamentos a motoristas › Conta-corrente | Filtros, KPI, Modal, Tabela | Superuser, Staff, Autenticado |
| `/driversapp/admin/pagamentos/` | `drivers_app.payments_views.payments_dashboard` | `drivers_app/admin/payments.html` | Finanças › Pagamentos a motoristas › Pagamentos | Formulário, Gráfico, Hero/gradiente, KPI, Tabela | Superuser, Staff |
| `/accounting/exec/` | `accounting_exec.executive_dashboard` | `accounting/executive_dashboard.html` | Finanças › Visão geral › Resumo executivo | Filtros, Gráfico, KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/tesouraria/` | `accounting_treasury.treasury_dashboard` | `accounting/treasury_dashboard.html` | Finanças › Visão geral › Tesouraria | Gráfico, KPI, Tabela | Superuser, Staff, Autenticado |
| `/accounting/hub/` | `accounting_hub.hub_financeiro` | `accounting/hub.html` | Finanças › Visão geral › Visão financeira | Tabela | Superuser, Staff, Autenticado |
| `/fleet/maintenance/<int:pk>/` | `fleet_management.maintenance_detail` | `fleet_management/maintenance_detail.html` | Frota (sem menu) | Hero/gradiente | Superuser, Staff, Autenticado |
| `/fleet/maintenance/<int:pk>/edit/` | `fleet_management.maintenance_edit` | `fleet_management/maintenance_form.html` | Frota (sem menu) | Formulário, Hero/gradiente | Superuser, Staff, Autenticado |
| `/fleet/maintenance/calendar/` | `fleet_management.maintenance_calendar` | `fleet_management/maintenance_calendar.html` | Frota (sem menu) | Hero/gradiente, Modal | Superuser, Staff, Autenticado |
| `/fleet/maintenance/create/` | `fleet_management.maintenance_create` | `fleet_management/maintenance_form.html` | Frota (sem menu) | Formulário, Hero/gradiente | Superuser, Staff, Autenticado |
| `/fleet/vehicles/<int:pk>/edit/` | `fleet_management.vehicle_edit` | `fleet_management/vehicle_form.html` | Frota (sem menu) | Formulário, Hero/gradiente | Superuser, Staff, Autenticado |
| `/fleet/vehicles/create/` | `fleet_management.vehicle_create` | `fleet_management/vehicle_form.html` | Frota (sem menu) | Formulário, Hero/gradiente | Superuser, Staff, Autenticado |
| `/` | `dashboard_leguas_home.DashboardView` | `dashboard_leguas/home.html` | Hoje › Painel do dia | Filtros, Gráfico, Hero/gradiente, KPI, Tabela | Superuser, Staff, Autenticado |
| `/driversapp/admin/central/` | `drivers_app.central_views.drivers_central` | `drivers_app/admin/drivers_central.html` | Motoristas (sem menu) | Filtros, Formulário, Gráfico, Hero/gradiente, KPI, Tabela | Superuser, Staff |
| `/driversapp/admin/reclamacoes/` | `drivers_app.admin_complaints_dashboard` | `drivers_app/admin_complaints.html` | Motoristas (sem menu) | Filtros, Hero/gradiente, KPI, Modal | Superuser, Staff, Autenticado |
| `/driversapp/admin/tickets-cainiao/` | `drivers_app_ticket_import.admin_tickets_cainiao` | `drivers_app/admin_tickets_cainiao.html` | Motoristas (sem menu) | Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Autenticado |
| `/driversapp/cadastro-completo/` | `drivers_app.public_driver_register_full` | `drivers_app/driver_public_register_full.html` | Motoristas (sem menu) | Filtros, Formulário, Hero/gradiente | Público, Superuser, Staff, Autenticado, Motorista, Frota |
| `/driversapp/cadastro/` | `drivers_app.public_driver_register` | `drivers_app/driver_public_register.html` | Motoristas (sem menu) | Formulário, Hero/gradiente | Público, Superuser, Staff, Autenticado, Motorista, Frota |
| `/fleet/maintenance/` | `fleet_management.maintenance_list` | `fleet_management/maintenance_list.html` | Operação › Frota › Manutenções | Filtros, Hero/gradiente, Tabela | Superuser, Staff, Autenticado |
| `/fleet/dashboard/` | `fleet_management.fleet_dashboard` | `fleet_management/fleet_dashboard.html` | Operação › Frota › Painel | Hero/gradiente | Superuser, Staff, Autenticado |
| `/fleet/vehicles/` | `fleet_management.vehicle_list` | `fleet_management/vehicle_list.html` | Operação › Frota › Veículos | Filtros, Hero/gradiente | Superuser, Staff, Autenticado |
| `/driversapp/admin/aprovar/` | `drivers_app.admin_approve_drivers` | `drivers_app/admin_approve_drivers.html` | Operação › Motoristas › Aprovar cadastros | Filtros, Formulário, Hero/gradiente, Modal | Superuser, Staff, Autenticado |
| `/driversapp/admin/` | `drivers_app.central_views.drivers_central` | `drivers_app/admin/drivers_central.html` | Operação › Motoristas › Central | Filtros, Formulário, Gráfico, Hero/gradiente, KPI, Tabela | Superuser, Staff |
| `/driversapp/admin/criar/` | `drivers_app.admin_create_driver` | `drivers_app/admin_create_driver.html` | Operação › Motoristas › Novo motorista | Formulário, Hero/gradiente | Superuser, Staff, Autenticado |
| `/driversapp/admin/pedidos-alteracao/` | `drivers_app.admin_change_requests.change_requests_list` | `drivers_app/admin/change_requests_list.html` | Operação › Motoristas › Pedidos de alteração | Formulário, Hero/gradiente, Modal | Superuser, Staff |
| `/settlements/packages/` | `settlements.cainiao_views.cainiao_packages_page` | `settlements/cainiao_packages.html` | Operação › Pacotes › Pesquisa | Filtros, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Autenticado |
| `/settlements/claims/` | `settlements.claim_list` | `settlements/claim_list_v2.html` | Operação › Pacotes › Reclamações | Filtros, Formulário, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Autenticado |
| `/settlements/recursos/` | `settlements.appeals_inbox` | `settlements/appeals_inbox.html` | Operação › Pacotes › Recursos | Formulário, Hero/gradiente, KPI, Tabela | Superuser, Staff, Autenticado |
| `/settlements/pudo/fake-delivery-suspects/` | `settlements_pudo.fake_delivery_suspects` | `settlements/pudo_fake_delivery_suspects.html` | Operação › Pacotes › Suspeitas de entrega falsa (PUDO) | Filtros, Formulário, Tabela | Superuser, Staff, Autenticado |
| `/settlements/cainiao/map/` | `settlements.cainiao_views.cainiao_map_view` | `settlements/cainiao_map.html, system_config/_leaflet_tiles.html` | Operação/Finanças (sem menu) | Filtros, Hero/gradiente, Mapa, Modal, Tabela | Superuser, Staff, Autenticado |
| `/settlements/cainiao/map/compare/` | `settlements.cainiao_views.cainiao_map_compare` | `settlements/cainiao_map_compare.html, system_config/_leaflet_tiles.html` | Operação/Finanças (sem menu) | Filtros, Mapa | Superuser, Staff, Autenticado |
| `/settlements/cainiao/waybill/<str:waybill>/` | `settlements.cainiao_views.cainiao_waybill_detail` | `settlements/cainiao_waybill_detail.html, system_config/_leaflet_tiles.html` | Operação/Finanças (sem menu) | Hero/gradiente, Mapa | Superuser, Staff, Autenticado |
| `/settlements/claims/<int:claim_id>/` | `settlements.claim_detail` | `settlements/claim_detail.html` | Operação/Finanças (sem menu) | Formulário, Hero/gradiente, Modal | Superuser, Staff, Autenticado |
| `/settlements/claims/appeals/` | `settlements.claim_list` | `settlements/claim_list_v2.html` | Operação/Finanças (sem menu) | Filtros, Formulário, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Autenticado |
| `/settlements/financial/` | `settlements.financial_dashboard` | `settlements/financial_dashboard_v2.html, accounting/_analysis_tabs.html` | Operação/Finanças (sem menu) | Hero/gradiente | Superuser, Staff, Autenticado |
| `/settlements/invoices/<int:invoice_id>/` | `settlements.invoice_detail` | `settlements/invoice_detail.html` | Operação/Finanças (sem menu) | Hero/gradiente | Superuser, Staff, Autenticado |
| `/settlements/invoices/cainiao/<int:import_id>/` | `settlements_cainiao_billing.cainiao_billing_detail` | `settlements/cainiao_billing_detail.html` | Operação/Finanças (sem menu) | Formulário, KPI, Tabela | Superuser, Staff, Autenticado |
| `/settlements/pacote/<str:waybill>/` | `settlements.package_360` | `settlements/package_360.html` | Operação/Finanças (sem menu) | Filtros, Hero/gradiente | Superuser, Staff, Autenticado |
| `/settlements/settlements/` | `settlements.settlement_list` | `settlements/settlement_list_v2.html` | Operação/Finanças (sem menu) | Filtros, Hero/gradiente, KPI, Tabela | Superuser, Staff, Autenticado |
| `/dashboard_v2/` | `dashboard_leguas.DashboardV2` | `dashboard_leguas/index.html` | Outros | - | Público, Superuser, Staff, Autenticado, Motorista, Frota |
| `/sla/prazos/` | `dashboard_leguas_sla.sla_rules` | `dashboard_leguas/sla_rules.html` | Outros | Formulário, Hero/gradiente, Tabela | Superuser, Staff |
| `/settlements/empresas/<int:empresa_id>/portal/` | `settlements_fleet_portal.empresa_portal_dashboard` | `settlements/portal_empresa/dashboard.html` | Portal da frota | KPI, Tabela | Superuser, Staff, Frota |
| `/settlements/empresas/<int:empresa_id>/portal/claims/` | `settlements_fleet_portal.empresa_portal_claims` | `settlements/portal_empresa/claims.html` | Portal da frota | Tabela | Superuser, Staff, Frota |
| `/settlements/empresas/<int:empresa_id>/portal/contratos/` | `settlements_fleet_portal.empresa_portal_contracts` | `settlements/portal_empresa/contracts.html` | Portal da frota | Filtros, Modal, Tabela | Superuser, Staff, Frota |
| `/settlements/empresas/<int:empresa_id>/portal/documentos/` | `settlements_fleet_portal.empresa_portal_documents` | `settlements/portal_empresa/documents.html` | Portal da frota | Filtros, Modal | Superuser, Staff, Frota |
| `/settlements/empresas/<int:empresa_id>/portal/faturas/` | `settlements_fleet_portal.empresa_portal_invoices` | `settlements/portal_empresa/invoices.html` | Portal da frota | Filtros, Hero/gradiente, Modal, Tabela | Superuser, Staff, Frota |
| `/settlements/empresas/<int:empresa_id>/portal/motoristas/` | `settlements_fleet_portal.empresa_portal_drivers` | `settlements/portal_empresa/drivers.html` | Portal da frota | Tabela | Superuser, Staff, Frota |
| `/settlements/empresas/<int:empresa_id>/portal/perfil/` | `settlements_fleet_portal.empresa_portal_profile` | `settlements/portal_empresa/profile.html` | Portal da frota | Formulário | Superuser, Staff, Frota |
| `/settlements/empresas/<int:empresa_id>/portal/relatorios/` | `settlements_fleet_portal.empresa_portal_reports` | `settlements/portal_empresa/reports.html` | Portal da frota | Tabela | Superuser, Staff, Frota |
| `/contracts/portal/<int:driver_id>/` | `contracts.driver_contracts` | `contracts/driver_contracts.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Hero/gradiente, Modal | Superuser, Staff, Motorista |
| `/contracts/portal/<int:driver_id>/sign/<int:template_id>/` | `contracts.driver_contract_sign` | `contracts/driver_contract_sign.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Formulário, Hero/gradiente, Modal | Superuser, Staff, Motorista |
| `/contracts/portal/<int:driver_id>/view/<int:contract_id>/` | `contracts.driver_contract_view` | `contracts/driver_contract_view.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Hero/gradiente, Modal | Superuser, Staff, Motorista |
| `/driversapp/portal/<int:driver_id>/` | `drivers_app.portal_views.driver_portal` | `drivers_app/portal/dashboard.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Filtros, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Motorista |
| `/driversapp/portal/<int:driver_id>/descontos/` | `drivers_app.portal_admin_views.driver_claims` | `drivers_app/portal/admin_claims.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Formulário, Modal | Superuser, Staff |
| `/driversapp/portal/<int:driver_id>/documentos/` | `drivers_app.portal_admin_views.driver_documents` | `drivers_app/portal/admin_documents.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Filtros, Formulário, Hero/gradiente, KPI, Modal | Superuser, Staff |
| `/driversapp/portal/<int:driver_id>/editar/` | `drivers_app.ficha_views.driver_ficha` | `drivers_app/portal/admin_ficha.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Formulário, Modal, Tabela | Superuser, Staff |
| `/driversapp/portal/<int:driver_id>/faturas/` | `drivers_app.portal_views.driver_portal_invoices` | `drivers_app/portal/invoices.html, drivers_app/portal/_app_ui.html, drivers_app/portal/_breakdown.html` | Portal do motorista | Filtros, Formulário, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Motorista |
| `/driversapp/portal/<int:driver_id>/helpers/` | `drivers_app.portal_admin_views.driver_helpers` | `drivers_app/portal/admin_helpers.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Formulário, Hero/gradiente, Modal | Superuser, Staff |
| `/driversapp/portal/<int:driver_id>/indicacoes/` | `drivers_app.portal_views.driver_portal_referrals` | `drivers_app/portal/referrals.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Filtros, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Motorista |
| `/driversapp/portal/<int:driver_id>/logins/` | `drivers_app.portal_admin_views.driver_logins` | `drivers_app/portal/admin_logins.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Formulário, Hero/gradiente, Modal, Tabela | Superuser, Staff |
| `/driversapp/portal/<int:driver_id>/perfil/` | `drivers_app.portal_views.driver_portal_profile` | `drivers_app/portal/profile.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Formulário, Hero/gradiente, Modal | Superuser, Staff, Motorista |
| `/driversapp/portal/<int:driver_id>/pf/<int:pre_invoice_id>/` | `drivers_app.portal_admin_views.driver_pre_invoice_detail` | `drivers_app/portal/admin_pf_detail.html, drivers_app/portal/_app_ui.html, drivers_app/portal/_breakdown.html` | Portal do motorista | Filtros, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff |
| `/driversapp/portal/<int:driver_id>/pudos/` | `drivers_app.portal_views.driver_portal_pudos` | `drivers_app/portal/pudos.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Filtros, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Motorista |
| `/driversapp/portal/<int:driver_id>/reclamacoes/` | `drivers_app.portal_admin_views.driver_complaints` | `drivers_app/portal/admin_complaints.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Filtros, Formulário, KPI, Modal | Superuser, Staff |
| `/driversapp/portal/<int:driver_id>/relatorios/` | `drivers_app.portal_views.driver_portal_reports` | `drivers_app/portal/reports.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Filtros, Hero/gradiente, KPI, Modal, Tabela | Superuser, Staff, Motorista |
| `/driversapp/portal/<int:driver_id>/veiculos/` | `drivers_app.portal_admin_views.driver_vehicles` | `drivers_app/portal/admin_vehicles.html, drivers_app/portal/_app_ui.html` | Portal do motorista | Formulário, Modal | Superuser, Staff |
| `/pricing/calculator/` | `pricing.price_calculator` | `pricing/price_calculator.html` | Rede › Clientes e plataformas › Calculadora | Formulário, Hero/gradiente | Superuser, Staff, Autenticado |
| `/core/integrations/dashboard/` | `core.integrations_dashboard` | `core/integrations_dashboard.html` | Rede › Clientes e plataformas › Integrações | Hero/gradiente, Tabela | Superuser, Staff, Autenticado |
| `/core/partners/` | `core.partner_list` | `core/partner_list.html` | Rede › Clientes e plataformas › Lista | Filtros, Formulário, Hero/gradiente, Modal | Superuser, Staff, Autenticado |
| `/pricing/tariffs/` | `pricing.tariff_list` | `pricing/tariff_list.html` | Rede › Clientes e plataformas › Tarifas | Filtros, Hero/gradiente | Superuser, Staff, Autenticado |
| `/pricing/zones/` | `pricing.zone_list` | `pricing/zone_list.html` | Rede › Clientes e plataformas › Zonas postais | Filtros, Hero/gradiente | Superuser, Staff, Autenticado |
| `/contracts/admin/signed/` | `contracts.admin_signed_contracts` | `contracts/admin_signed_list.html` | Rede › Contratos › Assinados | Filtros, Formulário, Hero/gradiente, Modal, Tabela | Superuser, Staff |
| `/contracts/admin/templates/` | `contracts.admin_templates_list` | `contracts/admin_templates_list.html` | Rede › Contratos › Modelos | Hero/gradiente, Tabela | Superuser, Staff |
| `/contracts/admin/templates/create/` | `contracts.admin_template_create` | `contracts/admin_template_form.html` | Rede › Contratos › Modelos › Botão "Novo modelo" | Filtros, Formulário, Hero/gradiente | Superuser, Staff |
| `/contracts/admin/missing/` | `contracts.admin_missing_contracts` | `contracts/admin_missing_list.html` | Rede › Contratos › Por assinar | Hero/gradiente, Tabela | Superuser, Staff |
| `/driversapp/empresas-parceiras/` | `drivers_app.empresas_parceiras_list` | `drivers_app/empresas_parceiras.html` | Rede › Frotas subcontratadas | Filtros, Hero/gradiente, Modal, Separadores, Tabela | Superuser, Staff, Autenticado |
| `/analytics/reports/fleet-costs/` | `analytics.fleet_cost_report` | `analytics/fleet_cost_report.html` | Relatórios › Custos de frota | Filtros, Hero/gradiente, Tabela | Superuser, Staff, Autenticado |
| `/analytics/integrations/status/` | `analytics.api_status_dashboard` | `analytics/api_status_dashboard.html` | Relatórios › Estado das APIs | Hero/gradiente, Tabela | Superuser, Staff, Autenticado |
| `/analytics/incidents/` | `analytics.incidents_report` | `analytics/incidents_report.html` | Relatórios › Incidências | Filtros, Hero/gradiente | Superuser, Staff, Autenticado |
| `/analytics/vehicles/` | `analytics.vehicles_performance_report` | `analytics/vehicles_performance_report.html` | Relatórios › Performance de veículos | Filtros, Hero/gradiente, Tabela | Superuser, Staff, Autenticado |
| `/analytics/integrations/logs/` | `analytics.sync_logs_list` | `analytics/sync_logs_list.html` | Relatórios › Registos de sincronização | Filtros, Formulário, Hero/gradiente, Tabela | Superuser, Staff, Autenticado |
| `/system/atualizacao/` | `system_config_updates.updates_index` | `system_config/updates.html` | Sistema (sem menu) | Formulário, Hero/gradiente, Modal | Superuser, Staff, Autenticado |
| `/system/recovery-keys/` | `system_config_recovery.recovery_keys_index` | `system_config/recovery_keys.html` | Sistema (sem menu) | Hero/gradiente, Tabela | Superuser |
| `/system/users/<int:pk>/edit/` | `system_config.user_views.user_edit` | `system_config/users/form.html` | Sistema (sem menu) | Formulário, Hero/gradiente | Superuser |
| `/system/users/create/` | `system_config.user_views.user_create` | `system_config/users/form.html` | Sistema (sem menu) | Formulário, Hero/gradiente | Superuser |
| `/system/whatsapp/` | `system_config.whatsapp_dashboard` | `system_config/whatsapp_dashboard.html` | Sistema (sem menu) | Filtros, Hero/gradiente | Superuser, Staff, Autenticado |
| `/system/` | `system_config.system_config_view` | `system_config/config.html` | Sistema › Configurações | Formulário, Hero/gradiente, Modal, Tabela | Superuser, Staff, Autenticado |
| `/management/tools/qr-generator/` | `management.tools_views.qr_generator_view` | `management/tools/qr_generator.html` | Sistema › Ferramentas | Hero/gradiente | Superuser, Staff, Autenticado |
| `/system/users/` | `system_config.user_views.user_list` | `system_config/users/list.html` | Sistema › Utilizadores | Filtros, Formulário, Hero/gradiente, KPI, Modal, Tabela | Superuser |
| `/pricing/tariffs/<int:pk>/edit/` | `pricing.tariff_edit` | `pricing/tariff_form.html` | Tarifas (sem menu) | Formulário, Hero/gradiente | Superuser, Staff, Autenticado |
| `/pricing/tariffs/create/` | `pricing.tariff_create` | `pricing/tariff_form.html` | Tarifas (sem menu) | Formulário, Hero/gradiente | Superuser, Staff, Autenticado |
| `/pricing/tariffs/import/` | `pricing.tariff_import_csv` | `pricing/tariff_import.html` | Tarifas (sem menu) | Formulário, Tabela | Superuser, Staff, Autenticado |
| `/pricing/zones/<int:pk>/edit/` | `pricing.zone_edit` | `pricing/zone_form.html` | Tarifas (sem menu) | Formulário, Hero/gradiente | Superuser, Staff, Autenticado |
| `/pricing/zones/create/` | `pricing.zone_create` | `pricing/zone_form.html` | Tarifas (sem menu) | Formulário, Hero/gradiente | Superuser, Staff, Autenticado |
| `/pricing/zones/import/` | `pricing.zone_import_csv` | `pricing/zone_import.html` | Tarifas (sem menu) | Formulário, Tabela | Superuser, Staff, Autenticado |

## 5. Métricas por página

A coluna "Consola" conta erros reais, sem o aviso do Tailwind CDN, que surge em quase todas as páginas.

| URL | Queries | Load (s) | Erros HTML | Consola | Pedidos falhados | Scroll móvel | Capturas |
|---|---|---|---|---|---|---|---|
| `/auth/` | 9 | 0.7 | 0 | 0 | 0 | não | 4 |
| `/auth/authenticate/` | 9 | 0.9 | 0 | 0 | 0 | não | 4 |
| `/auth/driver/` | 9 | 1.3 | 1 | 0 | 0 | não | 2 |
| `/auth/driver/credentials/<int:driver_id>/` | 11 | 1.5 | 1 | 0 | 0 | sim | 4 |
| `/auth/driver/login/` | 9 | 0.8 | 1 | 0 | 0 | não | 2 |
| `/auth/empresa/` | 9 | 1.1 | 1 | 0 | 0 | não | 2 |
| `/auth/empresa/credentials/<int:empresa_id>/` | 11 | 1.8 | 1 | 0 | 0 | não | 4 |
| `/auth/empresa/login/` | 9 | 0.7 | 1 | 0 | 0 | não | 2 |
| `/auth/login/` | 9 | 0.7 | 0 | 0 | 0 | não | 4 |
| `/core/drivers/<int:driver_id>/account/` | 0 | 1.7 | 1 | 0 | 0 | não | 4 |
| `/core/financial-alerts/` | 0 | 1.3 | 1 | 0 | 0 | não | 4 |
| `/core/integrations/<int:pk>/edit/` | 0 | 1.3 | 1 | 0 | 0 | não | 4 |
| `/core/partners/<int:partner_pk>/integrations/create/` | 0 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/core/partners/<int:pk>/` | 0 | 3.8 | 34 | 0 | 0 | não | 4 |
| `/core/partners/<int:pk>/bonus-rules/` | 0 | 1.4 | 1 | 0 | 0 | sim | 4 |
| `/core/partners/<int:pk>/edit/` | 0 | 2.4 | 1 | 0 | 0 | não | 4 |
| `/core/partners/<int:pk>/financial/` | 0 | 2.1 | 1 | 0 | 0 | sim | 4 |
| `/core/partners/create/` | 0 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/contracts/admin/gerado/<int:pk>/` | 10 | 0.2 | 1 | 0 | 0 | não | 2 |
| `/contracts/admin/gerar/<int:driver_id>/` | 21 | 0.4 | 1 | 0 | 0 | não | 2 |
| `/contracts/admin/templates/<int:pk>/edit/` | 0 | 1.5 | 1 | 0 | 0 | não | 4 |
| `/converter/` | 19 | 0.9 | 0 | 0 | 0 | não | 2 |
| `/accounting/` | 0 | 0.8 | 1 | 0 | 0 | não | 2 |
| `/accounting/a-pagar/calendario/` | 0 | 1.2 | 3 | 0 | 0 | não | 4 |
| `/accounting/a-pagar/forecast/` | 0 | 1.5 | 1 | 0 | 0 | sim | 4 |
| `/accounting/a-pagar/sem-ff/` | 0 | 1.1 | 2 | 0 | 0 | sim | 4 |
| `/accounting/a-pagar/sem-pf/` | 0 | 1.2 | 2 | 0 | 0 | sim | 4 |
| `/accounting/categorias/<int:pk>/editar/` | 0 | 1.0 | 1 | 0 | 0 | não | 4 |
| `/accounting/categorias/nova/` | 0 | 1.0 | 1 | 0 | 0 | não | 4 |
| `/accounting/centros-custo/<int:pk>/editar/` | 0 | 0.9 | 1 | 0 | 0 | não | 4 |
| `/accounting/centros-custo/novo/` | 0 | 0.9 | 1 | 0 | 0 | não | 4 |
| `/accounting/contas-a-pagar/<int:pk>/` | 0 | 1.2 | 1 | 0 | 0 | não | 4 |
| `/accounting/contas-a-pagar/<int:pk>/editar/` | 0 | 1.9 | 1 | 0 | 0 | não | 4 |
| `/accounting/contas-a-pagar/lixeira/` | 0 | 1.1 | 1 | 0 | 0 | sim | 4 |
| `/accounting/contas-a-pagar/nova/` | 0 | 1.4 | 1 | 0 | 0 | não | 4 |
| `/accounting/despesas/<int:pk>/editar/` | 0 | 1.0 | 1 | 0 | 0 | sim | 2 |
| `/accounting/despesas/nova/` | 0 | 0.9 | 1 | 0 | 0 | sim | 2 |
| `/accounting/extractos/<int:pk>/` | 0 | 1.1 | 1 | 0 | 0 | sim | 4 |
| `/accounting/extractos/upload/` | 0 | 1.3 | 1 | 0 | 0 | não | 4 |
| `/accounting/fornecedores/<int:pk>/editar/` | 0 | 1.0 | 1 | 0 | 0 | não | 4 |
| `/accounting/fornecedores/novo/` | 0 | 0.9 | 1 | 0 | 0 | não | 4 |
| `/accounting/fornecedores/tags/` | 0 | 1.5 | 1 | 0 | 0 | sim | 4 |
| `/accounting/impostos/<int:pk>/editar/` | 0 | 2.2 | 1 | 0 | 0 | não | 4 |
| `/accounting/impostos/novo/` | 0 | 1.1 | 1 | 0 | 0 | sim | 4 |
| `/accounting/receitas/<int:pk>/editar/` | 0 | 0.7 | 1 | 0 | 0 | sim | 2 |
| `/accounting/receitas/nova/` | 0 | 0.8 | 1 | 0 | 0 | sim | 2 |
| `/payroll/folhas/<int:pk>/` | 0 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/payroll/folhas/gerar/` | 10 | 1.3 | 1 | 0 | 0 | não | 4 |
| `/payroll/funcionarios/` | 0 | 1.3 | 1 | 0 | 0 | sim | 4 |
| `/payroll/funcionarios/<int:pk>/` | 0 | 1.2 | 1 | 0 | 0 | não | 4 |
| `/payroll/funcionarios/novo/` | 0 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/accounting/contas-a-pagar/` | 0 | 1.3 | 1 | 0 | 0 | sim | 4 |
| `/payroll/folhas/` | 0 | 1.2 | 1 | 0 | 0 | sim | 4 |
| `/accounting/fornecedores/` | 0 | 1.5 | 1 | 0 | 0 | sim | 4 |
| `/accounting/a-pagar/` | 0 | 1.4 | 9 | 4 | 0 | sim | 4 |
| `/accounting/pendentes-regularizacao/` | 0 | 1.3 | 1 | 0 | 0 | sim | 4 |
| `/accounting/extractos/` | 0 | 1.5 | 1 | 0 | 0 | sim | 4 |
| `/settlements/invoices/` | 16 | 1.8 | 1 | 0 | 0 | sim | 4 |
| `/accounting/reconciliacao-bancaria/` | 0 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/accounting/break-even/` | 0 | 1.8 | 1 | 1 | 0 | não | 4 |
| `/accounting/categorias/` | 0 | 1.4 | 1 | 0 | 0 | sim | 4 |
| `/accounting/centros-custo/` | 0 | 1.7 | 1 | 0 | 0 | sim | 4 |
| `/accounting/dre/` | 0 | 1.9 | 5 | 0 | 0 | sim | 4 |
| `/accounting/fluxo-caixa/` | 0 | 1.6 | 1 | 0 | 0 | sim | 4 |
| `/accounting/auditoria/` | 0 | 1.4 | 1 | 0 | 0 | não | 4 |
| `/settlements/calendar/` | 13 | 2.2 | 1 | 1 | 0 | sim | 4 |
| `/accounting/periodos/` | 0 | 1.8 | 1 | 0 | 0 | sim | 4 |
| `/settlements/socios/` | 9 | 1.6 | 13 | 0 | 0 | sim | 4 |
| `/accounting/impostos/` | 0 | 1.6 | 1 | 0 | 0 | sim | 4 |
| `/accounting/impostos/planos/` | 0 | 1.1 | 1 | 0 | 0 | sim | 4 |
| `/settlements/adiantamentos/` | 9 | 1.2 | 15 | 0 | 0 | sim | 4 |
| `/driversapp/admin/pagamentos/` | 37 | 1.9 | 4 | 0 | 0 | sim | 4 |
| `/accounting/exec/` | 0 | 1.8 | 1 | 0 | 0 | sim | 4 |
| `/accounting/tesouraria/` | 0 | 6.1 | 1 | 0 | 0 | sim | 4 |
| `/accounting/hub/` | 0 | 1.5 | 3 | 0 | 0 | sim | 4 |
| `/fleet/maintenance/<int:pk>/` | 0 | 1.5 | 1 | 0 | 0 | sim | 4 |
| `/fleet/maintenance/<int:pk>/edit/` | 0 | 1.4 | 1 | 0 | 0 | não | 4 |
| `/fleet/maintenance/calendar/` | 0 | 1.4 | 1 | 0 | 1 | sim | 4 |
| `/fleet/maintenance/create/` | 0 | 1.0 | 1 | 0 | 0 | não | 4 |
| `/fleet/vehicles/<int:pk>/edit/` | 0 | 1.3 | 1 | 0 | 0 | não | 4 |
| `/fleet/vehicles/create/` | 0 | 1.2 | 1 | 0 | 0 | não | 4 |
| `/` | 34 | 3.2 | 15 | 0 | 0 | sim | 4 |
| `/driversapp/admin/central/` | 39 | 1.3 | 12 | 0 | 0 | sim | 4 |
| `/driversapp/admin/reclamacoes/` | 11 | 1.9 | 1 | 0 | 0 | sim | 4 |
| `/driversapp/admin/tickets-cainiao/` | 11 | 1.0 | 8 | 1 | 1 | sim | 4 |
| `/driversapp/cadastro-completo/` | 9 | 1.0 | 0 | 0 | 0 | não | 2 |
| `/driversapp/cadastro/` | 9 | 0.7 | 0 | 0 | 0 | não | 2 |
| `/fleet/maintenance/` | 0 | 1.8 | 1 | 0 | 0 | sim | 4 |
| `/fleet/dashboard/` | 0 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/fleet/vehicles/` | 0 | 1.9 | 1 | 0 | 0 | sim | 4 |
| `/driversapp/admin/aprovar/` | 17 | 2.1 | 1 | 0 | 0 | sim | 4 |
| `/driversapp/admin/` | 39 | 3.8 | 12 | 0 | 0 | sim | 4 |
| `/driversapp/admin/criar/` | 9 | 1.0 | 1 | 0 | 0 | sim | 4 |
| `/driversapp/admin/pedidos-alteracao/` | 14 | 1.5 | 1 | 0 | 0 | não | 4 |
| `/settlements/packages/` | 10 | 3.0 | 4 | 0 | 0 | sim | 4 |
| `/settlements/claims/` | 21 | 1.1 | 1 | 0 | 0 | sim | 4 |
| `/settlements/recursos/` | 14 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/settlements/pudo/fake-delivery-suspects/` | 0 | 1.7 | 1 | 0 | 0 | sim | 4 |
| `/settlements/cainiao/map/` | 13 | 2.4 | 1 | 0 | 0 | sim | 4 |
| `/settlements/cainiao/map/compare/` | 10 | 1.8 | 1 | 0 | 0 | sim | 4 |
| `/settlements/cainiao/waybill/<str:waybill>/` | 21 | 1.7 | 1 | 1 | 0 | não | 4 |
| `/settlements/claims/<int:claim_id>/` | 10 | 1.3 | 1 | 1 | 0 | não | 4 |
| `/settlements/claims/appeals/` | 20 | 2.0 | 1 | 0 | 0 | sim | 4 |
| `/settlements/financial/` | 26 | 1.9 | 1 | 0 | 0 | não | 4 |
| `/settlements/invoices/<int:invoice_id>/` | 10 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/settlements/invoices/cainiao/<int:import_id>/` | 18 | 1.0 | 1 | 0 | 0 | sim | 4 |
| `/settlements/pacote/<str:waybill>/` | 13 | 1.3 | 1 | 0 | 0 | sim | 4 |
| `/settlements/settlements/` | 15 | 1.6 | 1 | 0 | 0 | sim | 4 |
| `/dashboard_v2/` | 9 | 0.7 | 0 | 0 | 0 | sim | 4 |
| `/sla/prazos/` | 16 | 1.2 | 1 | 0 | 0 | sim | 4 |
| `/settlements/empresas/<int:empresa_id>/portal/` | 46 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/settlements/empresas/<int:empresa_id>/portal/claims/` | 13 | 0.7 | 1 | 0 | 0 | não | 4 |
| `/settlements/empresas/<int:empresa_id>/portal/contratos/` | 12 | 0.8 | 1 | 0 | 0 | não | 4 |
| `/settlements/empresas/<int:empresa_id>/portal/documentos/` | 12 | 1.4 | 1 | 0 | 0 | não | 4 |
| `/settlements/empresas/<int:empresa_id>/portal/faturas/` | 12 | 0.9 | 4 | 0 | 0 | não | 4 |
| `/settlements/empresas/<int:empresa_id>/portal/motoristas/` | 14 | 1.0 | 1 | 0 | 0 | não | 4 |
| `/settlements/empresas/<int:empresa_id>/portal/perfil/` | 11 | 1.0 | 1 | 0 | 0 | não | 4 |
| `/settlements/empresas/<int:empresa_id>/portal/relatorios/` | 390 | 2.1 | 1 | 0 | 0 | não | 4 |
| `/contracts/portal/<int:driver_id>/` | 0 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/contracts/portal/<int:driver_id>/sign/<int:template_id>/` | 0 | 0.8 | 1 | 0 | 0 | não | 4 |
| `/contracts/portal/<int:driver_id>/view/<int:contract_id>/` | 0 | 1.2 | 1 | 0 | 0 | não | 4 |
| `/driversapp/portal/<int:driver_id>/` | 98 | 1.7 | 4 | 0 | 0 | não | 4 |
| `/driversapp/portal/<int:driver_id>/descontos/` | 13 | 1.5 | 1 | 0 | 0 | sim | 4 |
| `/driversapp/portal/<int:driver_id>/documentos/` | 12 | 1.6 | 1 | 0 | 0 | sim | 4 |
| `/driversapp/portal/<int:driver_id>/editar/` | 28 | 2.7 | 1 | 0 | 0 | sim | 4 |
| `/driversapp/portal/<int:driver_id>/faturas/` | 39 | 1.2 | 3 | 0 | 0 | não | 4 |
| `/driversapp/portal/<int:driver_id>/helpers/` | 12 | 1.8 | 1 | 0 | 0 | sim | 4 |
| `/driversapp/portal/<int:driver_id>/indicacoes/` | 18 | 1.3 | 1 | 0 | 0 | não | 4 |
| `/driversapp/portal/<int:driver_id>/logins/` | 14 | 1.3 | 33 | 0 | 0 | sim | 4 |
| `/driversapp/portal/<int:driver_id>/perfil/` | 14 | 1.6 | 1 | 0 | 0 | não | 4 |
| `/driversapp/portal/<int:driver_id>/pf/<int:pre_invoice_id>/` | 37 | 2.1 | 1 | 0 | 0 | sim | 4 |
| `/driversapp/portal/<int:driver_id>/pudos/` | 14 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/driversapp/portal/<int:driver_id>/reclamacoes/` | 29 | 1.9 | 1 | 0 | 0 | sim | 4 |
| `/driversapp/portal/<int:driver_id>/relatorios/` | 40 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/driversapp/portal/<int:driver_id>/veiculos/` | 11 | 1.3 | 1 | 0 | 0 | sim | 4 |
| `/pricing/calculator/` | 0 | 1.5 | 1 | 0 | 0 | não | 4 |
| `/core/integrations/dashboard/` | 0 | 1.8 | 1 | 0 | 0 | sim | 4 |
| `/core/partners/` | 0 | 1.7 | 1 | 0 | 0 | sim | 4 |
| `/pricing/tariffs/` | 0 | 2.0 | 1 | 0 | 0 | sim | 4 |
| `/pricing/zones/` | 0 | 1.1 | 1 | 0 | 0 | sim | 4 |
| `/contracts/admin/signed/` | 0 | 1.2 | 1 | 0 | 0 | sim | 4 |
| `/contracts/admin/templates/` | 0 | 1.1 | 1 | 0 | 0 | sim | 4 |
| `/contracts/admin/templates/create/` | 0 | 1.3 | 1 | 0 | 0 | não | 4 |
| `/contracts/admin/missing/` | 0 | 1.2 | 1 | 0 | 0 | sim | 4 |
| `/driversapp/empresas-parceiras/` | 12 | 2.1 | 17 | 0 | 0 | sim | 4 |
| `/analytics/reports/fleet-costs/` | 0 | 1.1 | 2 | 0 | 0 | sim | 4 |
| `/analytics/integrations/status/` | 0 | 1.0 | 1 | 0 | 0 | sim | 4 |
| `/analytics/incidents/` | 0 | 1.1 | 1 | 0 | 0 | sim | 4 |
| `/analytics/vehicles/` | 0 | 1.5 | 1 | 0 | 0 | sim | 4 |
| `/analytics/integrations/logs/` | 15 | 1.2 | 1 | 0 | 0 | sim | 4 |
| `/system/atualizacao/` | 0 | 1.7 | 1 | 0 | 0 | não | 4 |
| `/system/recovery-keys/` | 0 | 1.3 | 1 | 0 | 0 | sim | 4 |
| `/system/users/<int:pk>/edit/` | 0 | 1.3 | 1 | 0 | 0 | não | 4 |
| `/system/users/create/` | 0 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/system/whatsapp/` | 0 | 1.0 | 1 | 0 | 0 | não | 4 |
| `/system/` | 0 | 1.5 | 4 | 1 | 1 | sim | 4 |
| `/management/tools/qr-generator/` | 9 | 1.1 | 1 | 0 | 0 | não | 4 |
| `/system/users/` | 0 | 1.6 | 1 | 0 | 0 | sim | 4 |
| `/pricing/tariffs/<int:pk>/edit/` | 0 | 1.9 | 1 | 0 | 0 | não | 4 |
| `/pricing/tariffs/create/` | 0 | 1.8 | 1 | 0 | 0 | não | 4 |
| `/pricing/tariffs/import/` | 0 | 1.0 | 1 | 0 | 0 | sim | 4 |
| `/pricing/zones/<int:pk>/edit/` | 0 | 2.4 | 1 | 0 | 0 | não | 4 |
| `/pricing/zones/create/` | 0 | 1.8 | 1 | 0 | 0 | não | 4 |
| `/pricing/zones/import/` | 0 | 1.6 | 1 | 0 | 0 | sim | 4 |

### 10 páginas com mais queries

| URL | Queries |
|---|---|
| `/settlements/empresas/<int:empresa_id>/portal/relatorios/` | 390 |
| `/driversapp/portal/<int:driver_id>/` | 98 |
| `/settlements/empresas/<int:empresa_id>/portal/` | 46 |
| `/driversapp/portal/<int:driver_id>/relatorios/` | 40 |
| `/driversapp/admin/central/` | 39 |
| `/driversapp/admin/` | 39 |
| `/driversapp/portal/<int:driver_id>/faturas/` | 39 |
| `/driversapp/admin/pagamentos/` | 37 |
| `/driversapp/portal/<int:driver_id>/pf/<int:pre_invoice_id>/` | 37 |
| `/` | 34 |

### Erros de consola

| Ocorrências (páginas) | Mensagem |
|---|---|
| 2 | Failed to load resource: the server responded with a status of 404 (Not Found) |
| 1 | Error: <rect> attribute height: Unexpected end of attribute. Expected length, "". |
| 1 | Error: <rect> attribute y: Unexpected end of attribute. Expected length, "". |
| 1 | h is not defined |
| 1 | i is not defined |
| 1 | Unexpected number |
| 1 | Unexpected token ',' |
| 1 | init is not defined |
| 1 | Cannot read properties of null (reading 'addEventListener') |

### Pedidos falhados

| Páginas | Pedido |
|---|---|
| 2 | `404 /media/seed/documento.pdf` |
| 1 | `falhou https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.css` |

## 6. Páginas especiais

| Página | URL | Estado |
|---|---|---|
| Modo TV | `/?tv=1` | Parâmetro da página `/`. Captura `modo-tv-*` |
| Erro 404 | `/pagina-inexistente/` | Captura `erro-404-*` |
| Erro 500 | `/accounting/relatorios/` | Captura `erro-500-*`. A rota falha de verdade |
| Django admin | `/admin/` | Captura `django-admin-*`. 335 rotas fora do rebrand |

## 7. Rotas sem página

| URL | View | Estado (superuser) | Tipo |
|---|---|---|---|
| `/accounting/a-pagar/marcar-pago/` | `accounting.views_payables.payables_mark_paid` | 405 | text/html |
| `/accounting/a-pagar/pf/<int:pf_id>/compare/` | `accounting.views_payables.payables_pf_compare` | 200 | application/json |
| `/accounting/a-pagar/pf/<int:pf_id>/health/` | `accounting.views_payables.payables_pf_health` | 200 | application/json |
| `/accounting/a-pagar/pf/<int:pf_id>/notes/` | `accounting.views_payables.payables_pf_notes` | 200 | application/json |
| `/accounting/break-even/data/` | `accounting.views.break_even_data` | 200 | application/json |
| `/accounting/centros-custo/<int:pk>/toggle-ativo/` | `accounting.views_cost_centers.cost_center_toggle_active` | 405 | text/html |
| `/accounting/centros-custo/sync-hubs/` | `accounting.views_cost_centers.cost_center_sync_hubs` | 405 | text/html |
| `/accounting/contas-a-pagar/<int:pk>/apagar/` | `accounting.views.bill_delete` | 405 | text/html |
| `/accounting/contas-a-pagar/<int:pk>/aprovar/` | `accounting.views.bill_approve` | 405 | text/html |
| `/accounting/contas-a-pagar/<int:pk>/eliminar-definitivo/` | `accounting.views.bill_hard_delete` | 405 | text/html |
| `/accounting/contas-a-pagar/<int:pk>/gerar-proxima/` | `accounting.views.bill_generate_next` | 405 | text/html |
| `/accounting/contas-a-pagar/<int:pk>/marcar-paga/` | `accounting.views.bill_mark_paid` | 405 | text/html |
| `/accounting/contas-a-pagar/<int:pk>/rejeitar/` | `accounting.views.bill_reject` | 405 | text/html |
| `/accounting/contas-a-pagar/<int:pk>/restaurar/` | `accounting.views.bill_restore` | 405 | text/html |
| `/accounting/contas-a-pagar/anexo/<int:pk>/apagar/` | `accounting.views.bill_attachment_delete` | 405 | text/html |
| `/accounting/despesas/` | `accounting.views.expense_list` | 500 | text/html |
| `/accounting/despesas/<int:pk>/` | `accounting.views.expense_detail` | 500 | text/html |
| `/accounting/despesas/<int:pk>/deletar/` | `accounting.views.expense_delete` | 405 | text/html |
| `/accounting/despesas/<int:pk>/toggle-pagamento/` | `accounting.views.expense_toggle_payment` | 405 | text/html |
| `/accounting/dre/export/` | `accounting.views_dre_export.dre_export` | 200 | text/csv |
| `/accounting/extractos/transacao/<int:pk>/conciliar/` | `accounting.views.bank_transaction_match` | 405 | text/html |
| `/accounting/extractos/transacao/<int:pk>/desconciliar/` | `accounting.views.bank_transaction_unmatch` | 405 | text/html |
| `/accounting/fornecedores/<int:pk>/toggle-ativo/` | `accounting.views_suppliers.fornecedor_toggle_active` | 405 | text/html |
| `/accounting/fornecedores/api/<int:pk>/` | `accounting.views_suppliers.fornecedor_detail_api` | 200 | application/json |
| `/accounting/fornecedores/api/quick-create/` | `accounting.views_suppliers.fornecedor_quick_create_api` | 405 | text/html |
| `/accounting/fornecedores/api/search/` | `accounting.views_suppliers.fornecedor_search_api` | 200 | application/json |
| `/accounting/fornecedores/tags/<int:pk>/apagar/` | `accounting.views_suppliers.fornecedor_tag_delete` | 405 | text/html |
| `/accounting/impostos/<int:pk>/anular/` | `accounting.views_taxes.imposto_anular` | 405 | text/html |
| `/accounting/impostos/<int:pk>/marcar-pago/` | `accounting.views_taxes.imposto_mark_paid` | 405 | text/html |
| `/accounting/impostos/ocr-extract/` | `accounting.views_taxes.imposto_ocr_extract` | 405 | text/html |
| `/accounting/impostos/planos/<int:pk>/` | `accounting.views_taxes.plano_detail` | 404 | text/html |
| `/accounting/ocr/extract/` | `accounting.views_ocr.ocr_extract_api` | 405 | text/html |
| `/accounting/periodos/toggle/` | `accounting.views_period_lock.period_lock_toggle` | 405 | text/html |
| `/accounting/receitas/` | `accounting.views.revenue_list` | 500 | text/html |
| `/accounting/receitas/<int:pk>/` | `accounting.views.revenue_detail` | 500 | text/html |
| `/accounting/receitas/<int:pk>/deletar/` | `accounting.views.revenue_delete` | 405 | text/html |
| `/accounting/reconciliacao-bancaria/<int:tx_id>/clear/` | `accounting.views_reconciliation.bank_match_clear` | 405 | text/html |
| `/accounting/reconciliacao-bancaria/<int:tx_id>/confirm/` | `accounting.views_reconciliation.bank_match_confirm` | 405 | text/html |
| `/accounting/relatorios/` | `accounting.views.reports` | 500 | text/html |
| `/analytics/integrations/logs/<int:log_id>/retry/` | `analytics.views.retry_failed_sync` | 302 | text/html |
| `/api/app/v1/auth/logout` | `app_api.views.logout` | não testada | - |
| `/api/app/v1/auth/request-code` | `app_api.views.request_code` | 405 | text/html |
| `/api/app/v1/auth/verify-code` | `app_api.views.verify_code` | 405 | text/html |
| `/api/app/v1/complaints` | `app_api.views.complaints` | 401 | application/json |
| `/api/app/v1/discounts` | `app_api.views.discounts` | 401 | application/json |
| `/api/app/v1/incidences/add` | `app_api.views.incidences_add` | 405 | text/html |
| `/api/app/v1/incidences/complete` | `app_api.views.incidences_complete` | 405 | text/html |
| `/api/app/v1/incidences/confirm-ocr` | `app_api.views.incidences_confirm_ocr` | 405 | text/html |
| `/api/app/v1/incidences/drivers` | `app_api.views.incidences_drivers` | 401 | application/json |
| `/api/app/v1/incidences/history` | `app_api.views.incidences_history` | 401 | application/json |
| `/api/app/v1/incidences/ocr` | `app_api.views.incidences_process_scan` | 405 | text/html |
| `/api/app/v1/incidences/scan` | `app_api.views.incidences_process_scan` | 405 | text/html |
| `/api/app/v1/invoices` | `app_api.views.invoices` | 401 | application/json |
| `/api/app/v1/invoices/<int:pk>` | `app_api.views.invoice_detail` | 401 | application/json |
| `/api/app/v1/invoices/<int:pk>/pdf` | `app_api.views.invoice_pdf` | 401 | application/json |
| `/api/app/v1/me` | `app_api.views.me` | 401 | application/json |
| `/api/app/v1/sorting` | `app_api.views.sorting` | 401 | application/json |
| `/auth/driver/logout/` | `customauth.driver_auth_views.driver_logout` | não testada | - |
| `/auth/driver/send-code/` | `customauth.driver_auth_views.driver_login_send_code` | 405 | text/html |
| `/auth/driver/verify-code/` | `customauth.driver_auth_views.driver_login_verify_code` | 405 | text/html |
| `/auth/empresa/logout/` | `customauth.empresa_auth_views.empresa_logout` | não testada | - |
| `/auth/logout/` | `customauth.views.logout_view` | não testada | - |
| `/contracts/admin/contract/<int:pk>/revoke/` | `contracts.views.admin_revoke_contract` | 405 | text/html |
| `/contracts/admin/gerado/<int:pk>/acao/` | `contracts.views_generator.generated_contract_action` | 405 | text/html |
| `/contracts/admin/gerar/<int:driver_id>/registar/` | `contracts.views_generator.contract_generator_save` | 405 | text/html |
| `/converter/validate-addresses/` | `converter.views_geoapi.validate_addresses` | 405 | application/json |
| `/core/cainiao/detect-lost-packages/` | `core.views.cainiao_detect_lost_packages` | 405 | text/html |
| `/core/drivers/<int:driver_id>/couriers/` | `core.views.driver_courier_logins_list` | 200 | application/json |
| `/core/drivers/<int:driver_id>/couriers/<int:mapping_id>/delete/` | `core.views.driver_courier_login_delete` | 405 | text/html |
| `/core/drivers/<int:driver_id>/couriers/save/` | `core.views.driver_courier_login_save` | 405 | text/html |
| `/core/financial-alerts/<int:alert_id>/resolve/` | `core.views.financial_alert_resolve` | 405 | text/html |
| `/core/integrations/<int:pk>/toggle-status/` | `core.views.integration_toggle_status` | 302 | text/html |
| `/core/partners/<int:partner_id>/saft-export/` | `core.views.pre_invoice_saft_export` | 200 | application/xml |
| `/core/partners/<int:pk>/bonus-rules/<int:rule_id>/delete/` | `core.views.partner_bonus_rule_delete` | 405 | text/html |
| `/core/partners/<int:pk>/bonus-rules/save/` | `core.views.partner_bonus_rule_save` | 405 | text/html |
| `/core/partners/<int:pk>/delete/` | `core.views.partner_delete` | 302 | text/html |
| `/core/partners/<int:pk>/drivers-search/` | `core.views.partner_drivers_search` | 200 | application/json |
| `/core/partners/<int:pk>/financial/generate-preview/` | `core.views.partner_financial_preview` | 400 | application/json |
| `/core/partners/<int:pk>/financial/generate/` | `core.views.partner_financial_generate` | 405 | text/html |
| `/core/partners/<int:pk>/link-courier/` | `core.views.partner_link_courier` | 405 | text/html |
| `/core/partners/<int:pk>/toggle-status/` | `core.views.partner_toggle_status` | 500 | text/html |
| `/core/pre-invoice/sign/<str:token>/` | `core.views.pre_invoice_remote_sign` | 404 | text/html |
| `/core/pre-invoices/<int:pre_invoice_id>/price-override/` | `core.views.pre_invoice_price_override_create` | 405 | text/html |
| `/core/pre-invoices/<int:pre_invoice_id>/send-whatsapp/` | `core.views.pre_invoice_send_whatsapp` | 405 | text/html |
| `/driversapp/admin/aprovar/<int:driver_id>/` | `drivers_app.views.admin_approve_driver_action` | 302 | text/html |
| `/driversapp/admin/atividade/recalcular/` | `drivers_app.central_views.drivers_activity_refresh` | 405 | text/html |
| `/driversapp/admin/pagamentos/lote/` | `drivers_app.payments_views.payments_bulk` | 405 | text/html |
| `/driversapp/admin/pedidos-alteracao/<int:pk>/acao/` | `drivers_app.admin_change_requests.change_request_action` | 405 | text/html |
| `/driversapp/api/admin/reclamacoes/driver-search/` | `drivers_app.views.admin_complaints_driver_search` | 200 | application/json |
| `/driversapp/api/admin/reclamacoes/list/` | `drivers_app.views.admin_complaints_list_api` | 200 | application/json |
| `/driversapp/api/complaints/<int:driver_id>/` | `drivers_app.views.driver_complaints_api` | 200 | application/json |
| `/driversapp/api/complaints/<int:driver_id>/create/` | `drivers_app.views.driver_complaint_create` | 405 | text/html |
| `/driversapp/api/complaints/attachment/<int:attachment_id>/delete/` | `drivers_app.views.driver_complaint_delete_attachment` | 405 | text/html |
| `/driversapp/api/complaints/item/<int:complaint_id>/attachment/add/` | `drivers_app.views.driver_complaint_add_attachment` | 405 | text/html |
| `/driversapp/api/complaints/item/<int:complaint_id>/delete/` | `drivers_app.views.driver_complaint_delete` | 405 | text/html |
| `/driversapp/api/complaints/item/<int:complaint_id>/mark-lost/` | `drivers_app.views.driver_complaint_mark_lost` | 405 | text/html |
| `/driversapp/api/complaints/item/<int:complaint_id>/notificar-whatsapp/` | `drivers_app.views.driver_complaint_notify_whatsapp` | 405 | text/html |
| `/driversapp/api/complaints/item/<int:complaint_id>/update/` | `drivers_app.views.driver_complaint_update` | 405 | text/html |
| `/driversapp/api/complaints/ocr-extract/` | `drivers_app.views.complaint_ocr_extract` | 405 | text/html |
| `/driversapp/api/empresas-parceiras/<int:empresa_id>/auto-emit/` | `drivers_app.views.empresa_auto_emit_config` | 200 | application/json |
| `/driversapp/api/empresas-parceiras/<int:empresa_id>/auto-emit/run-now/` | `drivers_app.views.empresa_auto_emit_run_now` | 405 | text/html |
| `/driversapp/api/empresas-parceiras/<int:empresa_id>/delete/` | `drivers_app.views.empresa_parceira_delete` | 405 | text/html |
| `/driversapp/api/empresas-parceiras/<int:empresa_id>/lancamentos/create/` | `drivers_app.views.empresa_lancamento_create` | 405 | application/json |
| `/driversapp/api/empresas-parceiras/<int:empresa_id>/motoristas/` | `drivers_app.views.empresa_parceira_motoristas` | 200 | application/json |
| `/driversapp/api/empresas-parceiras/<int:empresa_id>/motoristas/<int:driver_id>/assign/` | `drivers_app.views.empresa_parceira_assign_driver` | 200 | application/json |
| `/driversapp/api/empresas-parceiras/<int:empresa_id>/motoristas/<int:driver_id>/remove/` | `drivers_app.views.empresa_parceira_remove_driver` | 405 | text/html |
| `/driversapp/api/empresas-parceiras/<int:empresa_id>/motoristas/search/` | `drivers_app.views.empresa_parceira_search_drivers` | 200 | application/json |
| `/driversapp/api/empresas-parceiras/<int:empresa_id>/prefaturas/` | `drivers_app.views.empresa_parceira_prefaturas` | 200 | application/json |
| `/driversapp/api/empresas-parceiras/<int:empresa_id>/update/` | `drivers_app.views.empresa_parceira_update` | 405 | text/html |
| `/driversapp/api/empresas-parceiras/create/` | `drivers_app.views.empresa_parceira_create` | 405 | text/html |
| `/driversapp/api/empresas-parceiras/lancamentos/<int:lancamento_id>/delete/` | `drivers_app.views.empresa_lancamento_delete` | 405 | application/json |
| `/driversapp/api/empresas-parceiras/lancamentos/<int:lancamento_id>/update/` | `drivers_app.views.empresa_lancamento_update` | 405 | application/json |
| `/driversapp/api/referrals/<int:driver_id>/` | `drivers_app.views.referral_list` | 200 | application/json |
| `/driversapp/api/referrals/<int:driver_id>/add/` | `drivers_app.views.referral_add` | 405 | text/html |
| `/driversapp/api/referrals/item/<int:referral_id>/delete/` | `drivers_app.views.referral_delete` | 405 | text/html |
| `/driversapp/api/referrals/item/<int:referral_id>/update/` | `drivers_app.views.referral_update` | 405 | text/html |
| `/driversapp/api/referrals/search/` | `drivers_app.views.referral_search_drivers` | 200 | application/json |
| `/driversapp/api/tickets-cainiao/<int:batch_id>/auto-close/` | `drivers_app.views_ticket_import.tickets_import_auto_close` | 405 | text/html |
| `/driversapp/api/tickets-cainiao/<int:batch_id>/bulk-action/` | `drivers_app.views_ticket_import.tickets_import_bulk_action` | 405 | text/html |
| `/driversapp/api/tickets-cainiao/<int:batch_id>/bulk-open/` | `drivers_app.views_ticket_import.tickets_import_bulk_open` | 405 | text/html |
| `/driversapp/api/tickets-cainiao/<int:batch_id>/bulk-select/` | `drivers_app.views_ticket_import.tickets_import_bulk_select` | 405 | text/html |
| `/driversapp/api/tickets-cainiao/<int:batch_id>/export/xlsx/` | `drivers_app.views_ticket_import.tickets_import_export_xlsx` | 200 | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
| `/driversapp/api/tickets-cainiao/<int:batch_id>/export/zip/` | `drivers_app.views_ticket_import.tickets_import_export_zip` | 200 | application/zip |
| `/driversapp/api/tickets-cainiao/<int:batch_id>/reresolve-drivers/` | `drivers_app.views_ticket_import.tickets_import_reresolve_drivers` | 405 | text/html |
| `/driversapp/api/tickets-cainiao/<int:batch_id>/rows/` | `drivers_app.views_ticket_import.tickets_import_rows_api` | 200 | application/json |
| `/driversapp/api/tickets-cainiao/attach/<int:att_id>/delete/` | `drivers_app.views_ticket_import.tickets_import_attach_delete` | 405 | text/html |
| `/driversapp/api/tickets-cainiao/driver-search/` | `drivers_app.views_ticket_import.tickets_import_driver_search` | 200 | application/json |
| `/driversapp/api/tickets-cainiao/preview/` | `drivers_app.views_ticket_import.tickets_import_preview` | 405 | text/html |
| `/driversapp/api/tickets-cainiao/row/<int:row_id>/attach/` | `drivers_app.views_ticket_import.tickets_import_row_attach` | 405 | text/html |
| `/driversapp/api/tickets-cainiao/row/<int:row_id>/open/` | `drivers_app.views_ticket_import.tickets_import_open_one` | 405 | text/html |
| `/driversapp/api/tickets-cainiao/row/<int:row_id>/update/` | `drivers_app.views_ticket_import.tickets_import_row_update` | 405 | text/html |
| `/driversapp/api/tickets-cainiao/upload/` | `drivers_app.views_ticket_import.tickets_import_upload` | 405 | text/html |
| `/driversapp/api/waybill-lookup/` | `drivers_app.views.waybill_lookup_for_complaint` | 400 | application/json |
| `/driversapp/complaints/<int:complaint_id>/pdf/` | `drivers_app.views.driver_complaint_pdf` | 200 | application/pdf |
| `/driversapp/empresas-parceiras/<int:empresa_id>/prefatura/pdf/` | `drivers_app.views.empresa_parceira_prefatura_pdf` | 500 | application/json |
| `/driversapp/logout/` | `drivers_app.views.driver_logout_view` | não testada | - |
| `/driversapp/portal/<int:driver_id>/caderneta/<int:year>/pdf/` | `drivers_app.portal_views.driver_caderneta_pdf` | 200 | application/pdf |
| `/driversapp/portal/<int:driver_id>/descontos/<int:claim_id>/aplicar/` | `drivers_app.portal_admin_views.driver_claim_apply_now` | 405 | text/html |
| `/driversapp/portal/<int:driver_id>/descontos/<int:claim_id>/decidir/` | `drivers_app.portal_admin_views.driver_claim_action` | 405 | text/html |
| `/driversapp/portal/<int:driver_id>/descontos/<int:claim_id>/recorrer/` | `drivers_app.portal_admin_views.driver_claim_appeal` | 405 | text/html |
| `/driversapp/portal/<int:driver_id>/descontos/aplicar-todos/` | `drivers_app.portal_admin_views.driver_claims_apply_all` | 405 | text/html |
| `/driversapp/portal/<int:driver_id>/financeiro/` | `drivers_app.portal_admin_views.driver_financeiro` | 302 | text/html |
| `/driversapp/portal/<int:driver_id>/logins/<int:mapping_id>/transfer/` | `drivers_app.portal_admin_views.driver_login_transfer` | 405 | text/html |
| `/driversapp/portal/<int:driver_id>/logins/<int:mapping_id>/transfer/preview/` | `drivers_app.portal_admin_views.driver_login_transfer_preview` | 400 | application/json |
| `/driversapp/portal/<int:driver_id>/pf/<int:pre_invoice_id>/clear-recibo/` | `drivers_app.portal_views.driver_pre_invoice_clear_recibo` | 405 | application/json |
| `/driversapp/portal/<int:driver_id>/pf/<int:pre_invoice_id>/pdf/` | `drivers_app.portal_views.driver_pre_invoice_pdf` | 500 | text/html |
| `/driversapp/portal/<int:driver_id>/pf/<int:pre_invoice_id>/upload-recibo/` | `drivers_app.portal_views.driver_pre_invoice_upload_recibo` | 405 | application/json |
| `/driversapp/portal/<int:driver_id>/reclamacoes/<int:complaint_id>/aplicar-desconto/` | `drivers_app.portal_admin_views.driver_complaint_apply_claim` | 405 | text/html |
| `/driversapp/portal/<int:driver_id>/unify/execute/` | `drivers_app.portal_admin_views.driver_unify_execute` | 405 | text/html |
| `/driversapp/portal/<int:driver_id>/unify/preview/<int:target_id>/` | `drivers_app.portal_admin_views.driver_unify_preview` | 400 | application/json |
| `/driversapp/portal/<int:driver_id>/unify/search/` | `drivers_app.portal_admin_views.driver_unify_search` | 200 | application/json |
| `/fleet/incidents/` | `fleet_management.views.incident_list` | 500 | text/html |
| `/fleet/vehicles/<int:pk>/` | `fleet_management.views.vehicle_detail` | 500 | text/html |
| `/fleet/vehicles/<int:pk>/toggle-status/` | `fleet_management.views.vehicle_toggle_status` | 500 | text/html |
| `/geozonas/api/zonas/export/` | `geozonas.views.api_zonas_export` | 401 | application/json |
| `/health/` | `my_project.urls.healthcheck` | 200 | application/json |
| `/payroll/folhas/<int:pk>/aprovar/` | `payroll.views.payroll_approve` | 405 | text/html |
| `/payroll/folhas/<int:pk>/cancelar/` | `payroll.views.payroll_cancel` | 405 | text/html |
| `/payroll/folhas/<int:pk>/component/<int:cid>/delete/` | `payroll.views.payroll_component_delete` | 405 | text/html |
| `/payroll/folhas/<int:pk>/component/add/` | `payroll.views.payroll_component_add` | 405 | text/html |
| `/payroll/folhas/<int:pk>/pagar/` | `payroll.views.payroll_pay` | 405 | text/html |
| `/payroll/folhas/<int:pk>/recalc/` | `payroll.views.payroll_recalc` | 405 | text/html |
| `/payroll/folhas/<int:pk>/recibo.pdf` | `payroll.views.payroll_recibo_pdf` | 200 | application/pdf |
| `/payroll/funcionarios/<int:pk>/delete/` | `payroll.views.employee_delete` | 405 | text/html |
| `/pricing/tariffs/<int:pk>/` | `pricing.views.tariff_detail` | 500 | text/html |
| `/pricing/tariffs/<int:pk>/toggle-status/` | `pricing.views.tariff_toggle_status` | 302 | text/html |
| `/pricing/zones/<int:pk>/` | `pricing.views.zone_detail` | 500 | text/html |
| `/pricing/zones/<int:pk>/toggle-status/` | `pricing.views.zone_toggle_status` | 302 | text/html |
| `/settlements/cainiao/cleanup-stale/` | `settlements.cainiao_views.cainiao_cleanup_stale_rows_view` | 405 | text/html |
| `/settlements/cainiao/consolidate-waybills/` | `settlements.cainiao_views.cainiao_consolidate_waybills_view` | 405 | text/html |
| `/settlements/cainiao/courier-backfill/` | `settlements.cainiao_views.cainiao_courier_backfill` | 405 | text/html |
| `/settlements/cainiao/courier-backfill/status/` | `settlements.cainiao_views.cainiao_courier_backfill_status` | 200 | application/json |
| `/settlements/cainiao/create-driver/` | `settlements.cainiao_views.cainiao_create_driver` | 405 | text/html |
| `/settlements/cainiao/debug-headers/` | `settlements.cainiao_views.cainiao_debug_headers_view` | 405 | text/html |
| `/settlements/cainiao/dedup-signatures/` | `settlements.cainiao_views.cainiao_dedup_signatures_view` | 405 | text/html |
| `/settlements/cainiao/detect-xlsx-type/` | `settlements.cainiao_views.cainiao_detect_xlsx_type` | 405 | text/html |
| `/settlements/cainiao/diagnose/<str:waybill>/` | `settlements.cainiao_views.cainiao_waybill_diagnose` | 200 | application/json |
| `/settlements/cainiao/driver-detail/import/` | `settlements.cainiao_views.cainiao_driver_detail_import` | 405 | text/html |
| `/settlements/cainiao/driver-detail/preview/` | `settlements.cainiao_views.cainiao_driver_detail_preview` | 405 | text/html |
| `/settlements/cainiao/driver-packages/` | `settlements.cainiao_views.cainiao_driver_packages` | 400 | text/html |
| `/settlements/cainiao/driver-stat/guided-import/` | `settlements.cainiao_views.cainiao_driver_stat_guided_import` | 405 | text/html |
| `/settlements/cainiao/driver-stat/import/` | `settlements.cainiao_views.cainiao_driver_stat_import` | 405 | text/html |
| `/settlements/cainiao/driver-stat/preview/` | `settlements.cainiao_views.cainiao_driver_stat_preview` | 405 | text/html |
| `/settlements/cainiao/driver/<int:driver_id>/helpers/` | `settlements.cainiao_views.cainiao_helpers_api` | 200 | application/json |
| `/settlements/cainiao/drivers-by-status/` | `settlements.cainiao_views.cainiao_drivers_by_status` | 400 | application/json |
| `/settlements/cainiao/drivers/` | `settlements.cainiao_views.cainiao_drivers_list` | 200 | application/json |
| `/settlements/cainiao/existing-logins/` | `settlements.cainiao_views.cainiao_existing_logins` | 200 | application/json |
| `/settlements/cainiao/flags/` | `settlements.cainiao_views.waybill_flag_list` | 200 | application/json |
| `/settlements/cainiao/flags/bulk/` | `settlements.cainiao_views.waybill_flag_bulk` | 405 | text/html |
| `/settlements/cainiao/forecast-orphans/` | `settlements.cainiao_views.cainiao_forecast_orphans` | 200 | application/json |
| `/settlements/cainiao/forecast/cp4/` | `settlements.cainiao_views.cainiao_forecast_cp4` | 200 | application/json |
| `/settlements/cainiao/forecast/excel/` | `settlements.cainiao_views.cainiao_forecast_excel` | 200 | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
| `/settlements/cainiao/forecast/manual/` | `settlements.cainiao_views.cainiao_manual_forecast_list` | 200 | application/json |
| `/settlements/cainiao/forecast/manual/<int:manual_id>/delete/` | `settlements.cainiao_views.cainiao_manual_forecast_delete` | 405 | text/html |
| `/settlements/cainiao/forecast/manual/save/` | `settlements.cainiao_views.cainiao_manual_forecast_save` | 405 | text/html |
| `/settlements/cainiao/forecast/pdf/` | `settlements.cainiao_views.cainiao_forecast_pdf` | 200 | application/pdf |
| `/settlements/cainiao/forecast/reset/` | `settlements.cainiao_views.cainiao_forecast_reset` | 405 | text/html |
| `/settlements/cainiao/hubs-with-counts/` | `settlements.cainiao_views.cainiao_hubs_with_counts` | 200 | application/json |
| `/settlements/cainiao/hubs/` | `settlements.cainiao_views.cainiao_hubs_list` | 200 | application/json |
| `/settlements/cainiao/hubs/<int:hub_id>/cp4/add/` | `settlements.cainiao_views.cainiao_hub_cp4_add` | 405 | text/html |
| `/settlements/cainiao/hubs/<int:hub_id>/cp4/remove/` | `settlements.cainiao_views.cainiao_hub_cp4_remove` | 405 | text/html |
| `/settlements/cainiao/hubs/<int:hub_id>/delete/` | `settlements.cainiao_views.cainiao_hub_delete` | 405 | text/html |
| `/settlements/cainiao/hubs/<int:hub_id>/update/` | `settlements.cainiao_views.cainiao_hub_update` | 405 | text/html |
| `/settlements/cainiao/hubs/create/` | `settlements.cainiao_views.cainiao_hub_create` | 405 | text/html |
| `/settlements/cainiao/import/confirm/` | `settlements.cainiao_views.cainiao_import_confirm` | 405 | text/html |
| `/settlements/cainiao/import/forecast/` | `settlements.cainiao_views.cainiao_import_forecast` | 405 | text/html |
| `/settlements/cainiao/import/forecast/preview/` | `settlements.cainiao_views.cainiao_import_forecast_preview` | 405 | text/html |
| `/settlements/cainiao/import/preview/` | `settlements.cainiao_views.cainiao_import_preview` | 405 | text/html |
| `/settlements/cainiao/link-driver/` | `settlements.cainiao_views.cainiao_link_driver` | 405 | text/html |
| `/settlements/cainiao/map-missing-coords/` | `settlements.cainiao_views.cainiao_map_missing_coords` | 200 | application/json |
| `/settlements/cainiao/map-overlays/` | `settlements.cainiao_views.cainiao_map_overlays` | 200 | application/json |
| `/settlements/cainiao/map-pins/` | `settlements.cainiao_views.cainiao_map_pins` | 200 | application/json |
| `/settlements/cainiao/mark-deliveries-courier-id/` | `settlements.cainiao_views.cainiao_mark_deliveries_courier_id` | 405 | text/html |
| `/settlements/cainiao/mark-stale-armazem/` | `settlements.cainiao_views.cainiao_mark_stale_armazem_view` | 405 | text/html |
| `/settlements/cainiao/not-arrived/` | `settlements.cainiao_views.cainiao_not_arrived` | 200 | application/json |
| `/settlements/cainiao/not-arrived/bulk-resolve/` | `settlements.cainiao_views.waybill_bulk_resolve` | 405 | text/html |
| `/settlements/cainiao/not-arrived/scan-xlsx/` | `settlements.cainiao_views.cainiao_not_arrived_scan_xlsx` | 405 | text/html |
| `/settlements/cainiao/not-arrived/whatsapp-driver/` | `settlements.cainiao_views.cainiao_whatsapp_driver_stuck` | 405 | text/html |
| `/settlements/cainiao/not-arrived/xlsx/` | `settlements.cainiao_views.cainiao_not_arrived_xlsx` | 200 | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
| `/settlements/cainiao/operation/audit/` | `settlements.cainiao_views.cainiao_operation_audit` | 405 | text/html |
| `/settlements/cainiao/operation/import/` | `settlements.cainiao_views.cainiao_operation_import` | 400 | application/json |
| `/settlements/cainiao/operation/preview/` | `settlements.cainiao_views.cainiao_operation_preview` | 405 | text/html |
| `/settlements/cainiao/packages/search/` | `settlements.cainiao_views.cainiao_packages_search` | 200 | application/json |
| `/settlements/cainiao/parcel-list/import/` | `settlements.cainiao_views.cainiao_parcel_list_import` | 405 | text/html |
| `/settlements/cainiao/parcel-list/preview/` | `settlements.cainiao_views.cainiao_parcel_list_preview` | 400 | application/json |
| `/settlements/cainiao/planning/import/` | `settlements.cainiao_views.cainiao_planning_import` | 405 | text/html |
| `/settlements/cainiao/planning/preview/` | `settlements.cainiao_views.cainiao_planning_preview` | 405 | text/html |
| `/settlements/cainiao/priority-settings/` | `settlements.cainiao_views.priority_settings_get` | 200 | application/json |
| `/settlements/cainiao/priority-settings/save/` | `settlements.cainiao_views.priority_settings_save` | 405 | text/html |
| `/settlements/cainiao/reliable-sync/` | `settlements.views_reliable_sync.api_reliable_sync` | 200 | application/json |
| `/settlements/cainiao/resolutions/` | `settlements.cainiao_views.cainiao_resolutions_list` | 200 | application/json |
| `/settlements/cainiao/return-batches/` | `settlements.cainiao_views.return_batch_list` | 200 | application/json |
| `/settlements/cainiao/return-batches/<int:batch_id>/xlsx/` | `settlements.cainiao_views.return_batch_xlsx` | 200 | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
| `/settlements/cainiao/returns/` | `settlements.cainiao_views.waybill_return_list` | 200 | application/json |
| `/settlements/cainiao/returns/bulk/` | `settlements.cainiao_views.waybill_return_bulk` | 405 | text/html |
| `/settlements/cainiao/roll-forward/` | `settlements.cainiao_views.cainiao_roll_forward_view` | 405 | text/html |
| `/settlements/cainiao/saved-filters/` | `settlements.cainiao_views.saved_filters` | 200 | application/json |
| `/settlements/cainiao/snapshots/` | `settlements.cainiao_views.cainiao_snapshot_list` | 200 | application/json |
| `/settlements/cainiao/snapshots/<int:snapshot_id>/` | `settlements.cainiao_views.cainiao_snapshot_detail` | 200 | application/json |
| `/settlements/cainiao/snapshots/<int:snapshot_id>/xlsx/` | `settlements.cainiao_views.cainiao_snapshot_xlsx` | 200 | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
| `/settlements/cainiao/snapshots/create/` | `settlements.cainiao_views.cainiao_snapshot_create` | 405 | text/html |
| `/settlements/cainiao/snapshots/diff/` | `settlements.cainiao_views.cainiao_snapshot_diff` | 404 | application/json |
| `/settlements/cainiao/unmapped/create-driver/` | `settlements.views_courier_onboarding.cainiao_unmapped_create_driver` | 405 | text/html |
| `/settlements/cainiao/unmapped/lookup/` | `settlements.views_courier_onboarding.cainiao_unmapped_lookup` | 400 | application/json |
| `/settlements/cainiao/waybill-search/` | `settlements.cainiao_views.cainiao_waybill_search` | 200 | application/json |
| `/settlements/calendar/<int:holiday_id>/delete/` | `settlements.holiday_views.holiday_delete` | 405 | text/html |
| `/settlements/calendar/<int:holiday_id>/update/` | `settlements.holiday_views.holiday_update` | 405 | text/html |
| `/settlements/calendar/blackout/<int:blackout_id>/delete/` | `settlements.holiday_views.blackout_delete` | 405 | text/html |
| `/settlements/calendar/blackout/create/` | `settlements.holiday_views.blackout_create` | 405 | text/html |
| `/settlements/calendar/check/` | `settlements.holiday_views.holiday_check` | 400 | application/json |
| `/settlements/calendar/create/` | `settlements.holiday_views.holiday_create` | 405 | text/html |
| `/settlements/calendar/import-preset/` | `settlements.holiday_views.holiday_import_preset` | 405 | text/html |
| `/settlements/cash-entries/<int:entry_id>/cancel/` | `settlements.views_cash_entries.cash_entry_cancel` | 405 | text/html |
| `/settlements/cash-entries/<int:entry_id>/delete/` | `settlements.views_cash_entries.cash_entry_delete` | 405 | text/html |
| `/settlements/cash-entries/<int:entry_id>/update/` | `settlements.views_cash_entries.cash_entry_update` | 405 | text/html |
| `/settlements/cash-entries/bulk-create/` | `settlements.views_cash_entries.cash_entry_bulk_create` | 405 | text/html |
| `/settlements/cash-entries/create/` | `settlements.views_cash_entries.cash_entry_create` | 405 | text/html |
| `/settlements/cash-entries/list/` | `settlements.views_cash_entries.cash_entry_list` | 200 | application/json |
| `/settlements/claims/<int:claim_id>/delete/` | `settlements.views.claim_delete` | 405 | text/html |
| `/settlements/claims/<int:claim_id>/notificar-whatsapp/` | `settlements.views.claim_notify_whatsapp` | 405 | text/html |
| `/settlements/claims/<int:claim_id>/update/` | `settlements.views.claim_update` | 405 | text/html |
| `/settlements/drivers/<int:driver_id>/account-statement/` | `settlements.views.driver_account_statement` | 200 | application/json |
| `/settlements/drivers/<int:driver_id>/day-waybills/` | `settlements.views.driver_day_waybills` | 400 | application/json |
| `/settlements/drivers/<int:driver_id>/delivery-report/` | `settlements.views.driver_delivery_report` | 500 | text/html |
| `/settlements/drivers/<int:driver_id>/fleet-invoice-lines/` | `settlements.views.driver_fleet_invoice_lines_api` | 200 | application/json |
| `/settlements/drivers/<int:driver_id>/pre-invoice-preview/` | `settlements.views.driver_pre_invoice_preview` | 200 | application/json |
| `/settlements/drivers/<int:driver_id>/set-capacity/` | `settlements.forecast_plan_views.driver_set_capacity` | 405 | text/html |
| `/settlements/drivers/<int:driver_id>/yearly-heatmap/` | `settlements.views.driver_yearly_heatmap` | 200 | application/json |
| `/settlements/drivers/dropdown/` | `settlements.views.drivers_dropdown` | 200 | application/json |
| `/settlements/empresas/<int:empresa_id>/dashboard-stats/` | `settlements.views.empresa_dashboard_stats` | 200 | application/json |
| `/settlements/empresas/<int:empresa_id>/fleet-invoices/` | `settlements.views.empresa_fleet_invoices_list` | 200 | application/json |
| `/settlements/empresas/<int:empresa_id>/lote-emit/` | `settlements.views.empresa_lote_emit` | 405 | text/html |
| `/settlements/empresas/<int:empresa_id>/lote-preview/` | `settlements.views.empresa_lote_preview` | 200 | application/json |
| `/settlements/empresas/<int:empresa_id>/portal/anexos/<int:attachment_id>/delete/` | `settlements.views_fleet_portal.empresa_portal_attachment_delete` | 405 | text/html |
| `/settlements/empresas/<int:empresa_id>/portal/contratos/<int:contract_id>/delete/` | `settlements.views_fleet_portal.empresa_portal_contract_delete` | 405 | text/html |
| `/settlements/empresas/<int:empresa_id>/portal/contratos/<int:contract_id>/update/` | `settlements.views_fleet_portal.empresa_portal_contract_update` | 405 | text/html |
| `/settlements/empresas/<int:empresa_id>/portal/contratos/create/` | `settlements.views_fleet_portal.empresa_portal_contract_create` | 405 | text/html |
| `/settlements/empresas/<int:empresa_id>/portal/documentos/<int:document_id>/delete/` | `settlements.views_fleet_portal.empresa_portal_document_delete` | 405 | text/html |
| `/settlements/empresas/<int:empresa_id>/portal/documentos/upload/` | `settlements.views_fleet_portal.empresa_portal_document_upload` | 405 | text/html |
| `/settlements/empresas/<int:empresa_id>/portal/faturas/<int:fleet_invoice_id>/anexos/upload/` | `settlements.views_fleet_portal.empresa_portal_attachment_upload` | 405 | text/html |
| `/settlements/empresas/<int:empresa_id>/whatsapp-lote/` | `settlements.views.empresa_whatsapp_lote` | 405 | text/html |
| `/settlements/fleet-invoices/<int:fleet_invoice_id>/` | `settlements.views.empresa_fleet_invoice_detail` | 200 | application/json |
| `/settlements/fleet-invoices/<int:fleet_invoice_id>/delete/` | `settlements.views.empresa_fleet_invoice_delete` | 405 | text/html |
| `/settlements/fleet-invoices/<int:fleet_invoice_id>/pdf/` | `settlements.views.empresa_fleet_invoice_pdf` | 500 | application/json |
| `/settlements/fleet-invoices/<int:fleet_invoice_id>/recalcular/` | `settlements.views.empresa_fleet_invoice_recalculate` | 405 | text/html |
| `/settlements/fleet-invoices/<int:fleet_invoice_id>/status/` | `settlements.views.empresa_fleet_invoice_change_status` | 405 | text/html |
| `/settlements/forecast-plan/` | `settlements.forecast_plan_views.forecast_plan_get_or_create` | 400 | application/json |
| `/settlements/forecast-plan/<int:plan_id>/assign/` | `settlements.forecast_plan_views.forecast_plan_assign` | 405 | text/html |
| `/settlements/forecast-plan/<int:plan_id>/auto-distribute/` | `settlements.forecast_plan_views.forecast_plan_auto_distribute` | 405 | text/html |
| `/settlements/forecast-plan/<int:plan_id>/clear/` | `settlements.forecast_plan_views.forecast_plan_clear` | 405 | text/html |
| `/settlements/forecast-plan/<int:plan_id>/clone-to/` | `settlements.forecast_plan_views.forecast_plan_clone_to` | 405 | text/html |
| `/settlements/forecast-plan/<int:plan_id>/publish/` | `settlements.forecast_plan_views.forecast_plan_publish` | 405 | text/html |
| `/settlements/forecast-plan/<int:plan_id>/toggle-skip/` | `settlements.forecast_plan_views.forecast_plan_toggle_skip` | 405 | text/html |
| `/settlements/forecast-plan/<int:plan_id>/unpublish/` | `settlements.forecast_plan_views.forecast_plan_unpublish` | 405 | text/html |
| `/settlements/forecast-plan/assignment/<int:assignment_id>/delete/` | `settlements.forecast_plan_views.forecast_plan_delete_assignment` | 405 | text/html |
| `/settlements/forecast-plan/history/` | `settlements.forecast_plan_views.forecast_plan_history` | 200 | application/json |
| `/settlements/invoices/<int:invoice_id>/pdf/` | `settlements.views.invoice_download_pdf` | 200 | application/pdf |
| `/settlements/invoices/<int:invoice_id>/status/` | `settlements.views.invoice_change_status` | 405 | text/html |
| `/settlements/invoices/cainiao/<int:import_id>/claims/<int:line_id>/assign/` | `settlements.views_cainiao_billing.cainiao_billing_assign_claim` | 405 | text/html |
| `/settlements/invoices/cainiao/<int:import_id>/claims/bulk/` | `settlements.views_cainiao_billing.cainiao_billing_assign_claims_bulk` | 405 | text/html |
| `/settlements/invoices/cainiao/<int:import_id>/create-overrides/` | `settlements.views_cainiao_billing.cainiao_billing_create_overrides` | 405 | text/html |
| `/settlements/invoices/cainiao/<int:import_id>/delete/` | `settlements.views_cainiao_billing.cainiao_billing_delete` | 405 | text/html |
| `/settlements/invoices/cainiao/<int:import_id>/export/<str:kind>/` | `settlements.views_cainiao_billing.cainiao_billing_export_xlsx` | 400 | text/html |
| `/settlements/invoices/cainiao/<int:import_id>/reresolve/` | `settlements.views_cainiao_billing.cainiao_billing_reresolve` | 405 | text/html |
| `/settlements/invoices/cainiao/upload/` | `settlements.views_cainiao_billing.cainiao_billing_upload` | 405 | text/html |
| `/settlements/pre-invoices/` | `settlements.views.pre_invoice_admin_list` | 302 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/adiantamento/add/` | `settlements.views.pre_invoice_add_advance` | 405 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/attach-entries/` | `settlements.views_cash_entries.pre_invoice_attach_entries` | 405 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/bonus/add/` | `settlements.views.pre_invoice_add_bonus` | 405 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/delete/` | `settlements.views.driver_pre_invoice_delete` | 405 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/extra/add/` | `settlements.views.pre_invoice_add_extra` | 405 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/linha/add/` | `settlements.views.pre_invoice_line_add` | 405 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/pacote-perdido/add/` | `settlements.views.pre_invoice_add_lost_package` | 405 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/pdf/` | `settlements.views.driver_pre_invoice_pdf` | 500 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/pending-entries/` | `settlements.views_cash_entries.pre_invoice_pending_entries` | 200 | application/json |
| `/settlements/pre-invoices/<int:pre_invoice_id>/recalculate/` | `settlements.views.driver_pre_invoice_recalculate` | 405 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/status/` | `settlements.views.pre_invoice_change_status` | 405 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/update/` | `settlements.views.driver_pre_invoice_update` | 405 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/upload-fatura/` | `settlements.views.pre_invoice_upload_fatura` | 405 | text/html |
| `/settlements/pre-invoices/<int:pre_invoice_id>/whatsapp/` | `settlements.views.pre_invoice_send_whatsapp` | 405 | text/html |
| `/settlements/pre-invoices/adiantamento/<int:advance_id>/delete/` | `settlements.views.pre_invoice_delete_advance` | 405 | text/html |
| `/settlements/pre-invoices/bonus/<int:bonus_id>/delete/` | `settlements.views.pre_invoice_delete_bonus` | 405 | text/html |
| `/settlements/pre-invoices/bulk-status/` | `settlements.views.pre_invoice_bulk_status` | 405 | text/html |
| `/settlements/pre-invoices/driver/<int:driver_id>/` | `settlements.views.driver_pre_invoices_api` | 200 | application/json |
| `/settlements/pre-invoices/driver/<int:driver_id>/create/` | `settlements.views.driver_pre_invoice_create` | 405 | text/html |
| `/settlements/pre-invoices/empresa-lancamento/<int:lancamento_id>/detail/` | `settlements.views.empresa_lancamento_detail_api` | 200 | application/json |
| `/settlements/pre-invoices/empresa-lancamento/<int:lancamento_id>/pdf/` | `settlements.views.empresa_lancamento_pdf` | 500 | text/html |
| `/settlements/pre-invoices/empresa-lancamento/<int:lancamento_id>/status/` | `settlements.views.empresa_lancamento_change_status` | 405 | text/html |
| `/settlements/pre-invoices/empresa-lancamento/<int:lancamento_id>/update/` | `settlements.views.empresa_lancamento_update` | 405 | text/html |
| `/settlements/pre-invoices/extra/<int:extra_id>/delete/` | `settlements.views.pre_invoice_delete_extra` | 405 | text/html |
| `/settlements/pre-invoices/import/<int:partner_id>/` | `settlements.views.import_partner_sheet` | 405 | text/html |
| `/settlements/pre-invoices/import/<int:partner_id>/preview/` | `settlements.views.import_partner_sheet_preview` | 405 | text/html |
| `/settlements/pre-invoices/linha/<int:line_id>/delete/` | `settlements.views.pre_invoice_line_delete` | 405 | text/html |
| `/settlements/pre-invoices/linha/<int:line_id>/update/` | `settlements.views.pre_invoice_line_update` | 405 | text/html |
| `/settlements/pre-invoices/pacote-perdido/<int:package_id>/delete/` | `settlements.views.pre_invoice_delete_lost_package` | 405 | text/html |
| `/settlements/pre-invoices/report/pdf/` | `settlements.views.pre_invoice_report_pdf` | 200 | application/pdf |
| `/settlements/pre-invoices/report/summary/` | `settlements.views.pre_invoice_report_summary` | 200 | application/json |
| `/settlements/price-overrides/<int:override_id>/delete/` | `settlements.views.package_price_override_delete` | 405 | text/html |
| `/settlements/price-overrides/create/` | `settlements.views.package_price_override_create` | 405 | text/html |
| `/settlements/pudo/fake-delivery-suspects/<int:task_id>/confirm/` | `settlements.views_pudo.confirm_fake_delivery` | 405 | text/html |
| `/settlements/recursos/<int:claim_id>/motivo/` | `settlements.views.appeals_set_reason` | 405 | text/html |
| `/settlements/reembolsos/` | `settlements.views_shareholder.reimbursement_list_api` | 200 | application/json |
| `/settlements/reembolsos/<int:reimbursement_id>/cancel/` | `settlements.views_shareholder.reimbursement_cancel` | 405 | text/html |
| `/settlements/reembolsos/<int:reimbursement_id>/delete/` | `settlements.views_shareholder.reimbursement_delete` | 405 | text/html |
| `/settlements/reembolsos/<int:reimbursement_id>/mark-paid/` | `settlements.views_shareholder.reimbursement_mark_paid` | 405 | text/html |
| `/settlements/reembolsos/<int:reimbursement_id>/update/` | `settlements.views_shareholder.reimbursement_update` | 405 | text/html |
| `/settlements/reembolsos/bulk-mark-paid/` | `settlements.views_shareholder.reimbursement_bulk_mark_paid` | 405 | text/html |
| `/settlements/reembolsos/create/` | `settlements.views_shareholder.reimbursement_create` | 405 | text/html |
| `/settlements/socios/<int:shareholder_id>/delete/` | `settlements.views_shareholder.shareholder_delete` | 405 | text/html |
| `/settlements/socios/<int:shareholder_id>/update/` | `settlements.views_shareholder.shareholder_update` | 405 | text/html |
| `/settlements/socios/create/` | `settlements.views_shareholder.shareholder_create` | 405 | text/html |
| `/settlements/socios/list/` | `settlements.views_shareholder.shareholder_list_api` | 200 | application/json |
| `/settlements/transfers/<int:override_id>/delete/` | `settlements.views.waybill_transfer_delete` | 405 | text/html |
| `/settlements/transfers/create/` | `settlements.views.waybill_transfer_create` | 405 | text/html |
| `/settlements/waybill/<str:waybill>/comments/` | `settlements.cainiao_views.waybill_comments_list` | 200 | application/json |
| `/settlements/waybill/<str:waybill>/comments/add/` | `settlements.cainiao_views.waybill_comments_add` | 405 | text/html |
| `/settlements/waybill/<str:waybill>/flag/` | `settlements.cainiao_views.waybill_flag_get` | 200 | application/json |
| `/settlements/waybill/<str:waybill>/flag/clear/` | `settlements.cainiao_views.waybill_flag_clear` | 405 | text/html |
| `/settlements/waybill/<str:waybill>/flag/create/` | `settlements.cainiao_views.waybill_flag_create` | 405 | text/html |
| `/settlements/waybill/<str:waybill>/history/` | `settlements.views.waybill_history` | 200 | application/json |
| `/settlements/waybill/<str:waybill>/lifecycle/` | `settlements.cainiao_views.cainiao_waybill_lifecycle` | 200 | application/json |
| `/settlements/waybill/<str:waybill>/resolution/` | `settlements.cainiao_views.waybill_get_resolution` | 200 | application/json |
| `/settlements/waybill/<str:waybill>/resolve/` | `settlements.cainiao_views.waybill_resolve` | 405 | text/html |
| `/settlements/waybill/<str:waybill>/return/` | `settlements.cainiao_views.waybill_return_get` | 200 | application/json |
| `/settlements/waybill/<str:waybill>/return/delete/` | `settlements.cainiao_views.waybill_return_delete` | 405 | text/html |
| `/settlements/waybill/<str:waybill>/return/save/` | `settlements.cainiao_views.waybill_return_create` | 405 | text/html |
| `/settlements/waybill/<str:waybill>/tags/` | `settlements.cainiao_views.waybill_tags_list` | 200 | application/json |
| `/settlements/waybill/<str:waybill>/tags/add/` | `settlements.cainiao_views.waybill_tag_add` | 405 | text/html |
| `/settlements/waybill/<str:waybill>/unresolve/` | `settlements.cainiao_views.waybill_unresolve` | 405 | text/html |
| `/settlements/waybill/<str:waybill>/watch/` | `settlements.cainiao_views.waybill_watch_toggle` | 405 | text/html |
| `/settlements/waybill/comments/<int:comment_id>/delete/` | `settlements.cainiao_views.waybill_comments_delete` | 405 | text/html |
| `/settlements/waybill/tags/<int:tag_id>/delete/` | `settlements.cainiao_views.waybill_tag_delete` | 405 | text/html |
| `/settlements/waybill/watch/list/` | `settlements.cainiao_views.waybill_watch_list` | 200 | application/json |
| `/system/atualizacao/aplicar/` | `system_config.views_updates.updates_apply` | 405 | text/html |
| `/system/atualizacao/github/configurar/` | `system_config.views_updates.github_save_config` | 405 | text/html |
| `/system/atualizacao/status/` | `system_config.views_updates.updates_status` | 200 | application/json |
| `/system/atualizacao/sugestao/<int:suggestion_id>/atualizar/` | `system_config.views_updates.suggestion_update_status` | 405 | text/html |
| `/system/atualizacao/sugestao/criar/` | `system_config.views_updates.suggestion_create` | 405 | text/html |
| `/system/atualizacao/verificar/` | `system_config.views_updates.updates_check` | 502 | application/json |
| `/system/backups/` | `system_config.backup_views.backups_manager` | 500 | text/html |
| `/system/backups/delete/` | `system_config.backup_views.delete_backup` | 405 | text/html |
| `/system/backups/download/<str:filename>/` | `system_config.backup_views.download_backup` | 404 | application/json |
| `/system/backups/restore/` | `system_config.backup_views.restore_backup` | 405 | text/html |
| `/system/backups/upload-cloud/` | `system_config.backup_views.upload_backup_to_cloud` | 405 | text/html |
| `/system/recovery-keys/download/` | `system_config.views_recovery.recovery_keys_download_env` | 200 | text/plain |
| `/system/save/` | `system_config.views.save_config` | 405 | text/html |
| `/system/typebot/auto-login/` | `system_config.views.typebot_auto_login` | 302 | text/html |
| `/system/typebot/generate-secret/` | `system_config.views.typebot_generate_encryption_secret` | 405 | text/html |
| `/system/typebot/test-connection/` | `system_config.views.typebot_test_connection` | 405 | text/html |
| `/system/users/<int:pk>/delete/` | `system_config.user_views.user_delete` | 405 | text/html |
| `/system/users/<int:pk>/reset-password/` | `system_config.user_views.user_reset_password` | 405 | text/html |
| `/system/users/<int:pk>/toggle-active/` | `system_config.user_views.user_toggle_active` | 405 | text/html |
| `/system/whatsapp/diagnose/` | `system_config.views.whatsapp_diagnose` | 200 | application/json |
| `/system/whatsapp/ensure/` | `system_config.views.whatsapp_ensure` | 405 | text/html |
| `/system/whatsapp/generate-token/` | `system_config.views.whatsapp_generate_token` | 405 | text/html |
| `/system/whatsapp/logout/` | `system_config.views.whatsapp_logout` | não testada | - |
| `/system/whatsapp/qrcode/` | `system_config.views.whatsapp_qrcode` | 400 | application/json |
| `/system/whatsapp/send-test/` | `system_config.views.whatsapp_send_test` | 405 | text/html |
| `/system/whatsapp/start/` | `system_config.views.whatsapp_start_session` | 405 | text/html |
| `/system/whatsapp/status/` | `system_config.views.whatsapp_status` | 400 | application/json |
| `/system/whatsapp/update-config/` | `system_config.views.whatsapp_update_config` | 405 | text/html |
| `/system/whatsapp/webhook/` | `system_config.views.whatsapp_webhook` | 405 | text/html |
