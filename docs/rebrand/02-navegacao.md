# Nova arquitetura de navegação — proposta

**Estado:** proposta da Fase 0. Nenhum menu foi alterado.
**Fonte:** `templates/layouts/partials/sidebar.html` (commit `469a7d8`).

## 1. Situação atual

- O menu principal tem **57 ligações**. O briefing indica 58. A navegação de 30/10 foi anterior à remoção de Sorting, Mapa e lista legacy.
- Existem **2 ligações** para o mesmo destino: "Empresas Parceiras" e "Faturas Frota" (`drivers_app:empresas-parceiras`).
- Existe um **segundo menu** em `dashboard_sidebar.html`, com 30 ligações. Só `/dashboard_v2/` o usa.
- `/dashboard_v2/` é uma página estática antiga, aberta sem login. A página real é `/`.
- `sidebar_links.html` é um terceiro menu, com 11 ligações, usado por `templates/base.html` e `templates/base_drivers_app.html`.

## 2. Correções à proposta do briefing

| # | Proposta do briefing | Facto no código | Alteração proposta |
|---|---|---|---|
| 1 | Folha de pagamento em "Pagamentos a motoristas" | `payroll.Employee` é para funcionários mensalistas, "distinto de DriverProfile" (`payroll/models.py:16`) | Mover para **A pagar** |
| 2 | Faturas de frotas subcontratadas em "A pagar" | `FleetInvoice`: "É o que o parceiro paga à frota" (`settlements/models.py:3257`). A Léguas paga | Confirmado. Falta a lista global (decisão D1) |
| 3 | Modo TV como página própria | Hoje é o parâmetro `/?tv=1`, aberto por um botão no Dashboard (`home.html:53`) | Manter o URL. Renomear o botão para "Modo ecrã" |
| 4 | "Novo Template" não consta da proposta | Ligação atual do menu | Mover para botão primário em Contratos › Modelos |
| 5 | Relatórios com Incidências, Performance e Custos de frota | Os 3 relatórios dependem da app de frota (`analytics/views.py:15`) | Saem com a Frota, se a Fase 0.7 aprovar |

## 3. Estrutura proposta

```
HOJE
  Painel do dia                 /
  Precisa de atenção · N        (vista nova, Fase 3)
OPERAÇÃO
  Pacotes                       Pesquisa · Reclamações · Recursos · Suspeitas de entrega falsa (PUDO)
  Motoristas                    Central · Aprovar cadastros · Pedidos de alteração · Novo motorista
  Frota                         Painel · Veículos · Manutenções · Incidentes     ← depende de 03-sem-uso.md
REDE
  Clientes e plataformas        Lista · Integrações · Zonas postais · Tarifas · Calculadora
  Frotas subcontratadas
  Contratos                     Assinados · Por assinar · Modelos
FINANÇAS
  Visão geral                   Visão financeira · Resumo executivo · Tesouraria
  Pagamentos a motoristas       Pagamentos · Conta-corrente · Pré-faturas
  A receber                     Faturas de clientes · Reconciliação bancária · Extratos OFX
  A pagar                       Inbox · Contas a pagar · Faturas de frotas subcontratadas ·
                                Pendentes de regularização · Fornecedores · Folha de pagamento
  Impostos                      Impostos · Planos prestacionais
  Análise                       DRE · Fluxo de caixa · Break-even · Centros de custo · Categorias
  Controlo                      Fechos de período · Auditoria · Calendário · Sócios e reembolsos
RELATÓRIOS
  Relatórios                    Estado das APIs · Registos de sincronização
                                (+ Incidências · Performance · Custos, se a Frota ficar)
SISTEMA
  Utilizadores · Configurações · Ferramentas (Gerador de QR Code)
```

**Regras:** máximo 2 níveis. Grupo colapsável só com mais de 3 itens. Contador só em itens com ação pendente.

**NOTA:** o briefing usa "ANÁLISE" como secção e "Análise" como item de FINANÇAS. Para cumprir a regra de um termo por significado, a secção passa a "RELATÓRIOS".

## 4. Mapa das 57 entradas atuais

Todas as entradas têm destino. Os URL não mudam.

| # | Grupo atual | Entrada atual | Rota | Novo grupo | Novo nome |
|---|---|---|---|---|---|
| 1 | Dashboard | Dashboard Principal | `dashboard_leguas:home` | Hoje | Painel do dia |
| 2 | Motoristas | Cadastrar Motorista | `drivers_app:admin_create_driver` | Operação › Motoristas | Novo motorista |
| 3 | Motoristas | Aprovar Cadastros | `drivers_app:admin_approve_drivers` | Operação › Motoristas | Aprovar cadastros |
| 4 | Motoristas | Central de Motoristas | `drivers_app:drivers_central` | Operação › Motoristas | Central |
| 5 | Motoristas | Pagamentos a Motoristas | `drivers_app:payments_dashboard` | Finanças › Pagamentos a motoristas | Pagamentos |
| 6 | Motoristas | Pedidos de Alteração | `drivers_app:change_requests_list` | Operação › Motoristas | Pedidos de alteração |
| 7 | Pacotes | Pesquisa Global | `cainiao-packages-page` | Operação › Pacotes | Pesquisa |
| 8 | Pacotes | Claims (Motoristas) | `claim-list` | Operação › Pacotes | Reclamações |
| 9 | Pacotes | Recursos | `appeals-inbox` | Operação › Pacotes | Recursos |
| 10 | Contratos | Modelos de Contrato | `contracts:admin_templates_list` | Rede › Contratos | Modelos |
| 11 | Contratos | Assinados | `contracts:admin_signed_contracts` | Rede › Contratos | Assinados |
| 12 | Contratos | Por Assinar | `contracts:admin_missing_contracts` | Rede › Contratos | Por assinar |
| 13 | Contratos | Novo Template | `contracts:admin_template_create` | Rede › Contratos › Modelos | Botão "Novo modelo" |
| 14 | Gestão | Empresas Parceiras | `drivers_app:empresas-parceiras` | Rede | Frotas subcontratadas |
| 15 | Parceiros | Lista de Parceiros | `core:partner-list` | Rede › Clientes e plataformas | Lista |
| 16 | Parceiros | Dashboard Integrações | `core:integrations-dashboard` | Rede › Clientes e plataformas | Integrações |
| 17 | Parceiros | Zonas Postais | `pricing:zone-list` | Rede › Clientes e plataformas | Zonas postais |
| 18 | Parceiros | Tarifas | `pricing:tariff-list` | Rede › Clientes e plataformas | Tarifas |
| 19 | Parceiros | Calculadora de Preços | `pricing:price-calculator` | Rede › Clientes e plataformas | Calculadora |
| 20 | Frota | Dashboard Frota | `fleet:dashboard` | Operação › Frota | Painel |
| 21 | Frota | Veículos | `fleet:vehicle_list` | Operação › Frota | Veículos |
| 22 | Frota | Manutenções | `fleet:maintenance_list` | Operação › Frota | Manutenções |
| 23 | Frota | Incidentes | `fleet:incident_list` | Operação › Frota | Incidentes |
| 24 | Relatórios | Incidências | `analytics:incidents_report` | Relatórios | Incidências |
| 25 | Relatórios | Performance Veículos | `analytics:vehicles_report` | Relatórios | Performance de veículos |
| 26 | Relatórios | Custos de Frota | `analytics:fleet_cost_report` | Relatórios | Custos de frota |
| 27 | Relatórios | Status de APIs | `analytics:api_status_dashboard` | Relatórios | Estado das APIs |
| 28 | Relatórios | Logs de Sincronização | `analytics:sync_logs_list` | Relatórios | Registos de sincronização |
| 29 | Financeiro | Hub Financeiro | `accounting:hub_financeiro` | Finanças › Visão geral | Visão financeira |
| 30 | Financeiro | Faturas Parceiros | `invoice-list` | Finanças › A receber | Faturas de clientes |
| 31 | Financeiro | Faturas Frota | `drivers_app:empresas-parceiras` | Finanças › A pagar | Faturas de frotas subcontratadas (decisão D1) |
| 32 | Financeiro | Reconciliação Bancária | `accounting:bank_reconciliation` | Finanças › A receber | Reconciliação bancária |
| 33 | Financeiro | Inbox A Pagar | `accounting:payables_inbox` | Finanças › A pagar | Inbox |
| 34 | Financeiro | Pendentes Regularização | `accounting:pending_reconciliation` | Finanças › A pagar | Pendentes de regularização |
| 35 | Financeiro | Contas a Pagar | `accounting:bill_list` | Finanças › A pagar | Contas a pagar |
| 36 | Financeiro | Impostos | `accounting:imposto_list` | Finanças › Impostos | Impostos |
| 37 | Financeiro | Planos Prestacionais | `accounting:plano_list` | Finanças › Impostos | Planos prestacionais |
| 38 | Financeiro | Folha de Pagamento | `payroll:payroll_list` | Finanças › A pagar | Folha de pagamento |
| 39 | Financeiro | Conta-Corrente | `cash-entries-dashboard` | Finanças › Pagamentos a motoristas | Conta-corrente |
| 40 | Financeiro | Pré-Faturas (admin) | `pre-invoice-admin-list` | Finanças › Pagamentos a motoristas | Pré-faturas |
| 41 | Financeiro | Sócios & Reembolsos | `shareholder-dashboard` | Finanças › Controlo | Sócios e reembolsos |
| 42 | Financeiro | Tesouraria | `accounting:treasury_dashboard` | Finanças › Visão geral | Tesouraria |
| 43 | Financeiro | Fluxo de Caixa | `accounting:cash_flow` | Finanças › Análise | Fluxo de caixa |
| 44 | Financeiro | DRE | `accounting:dre` | Finanças › Análise | DRE |
| 45 | Financeiro | Break-Even | `accounting:break_even` | Finanças › Análise | Break-even |
| 46 | Financeiro | Resumo Executivo | `accounting:executive_dashboard` | Finanças › Visão geral | Resumo executivo |
| 47 | Financeiro | Fornecedores | `accounting:fornecedor_list` | Finanças › A pagar | Fornecedores |
| 48 | Financeiro | Centros de Custo | `accounting:cost_center_list` | Finanças › Análise | Centros de custo |
| 49 | Financeiro | Categorias de Despesa | `accounting:category_list` | Finanças › Análise | Categorias |
| 50 | Financeiro | Calendário | `holiday-list` | Finanças › Controlo | Calendário |
| 51 | Financeiro | Fechos de Período | `accounting:period_lock_list` | Finanças › Controlo | Fechos de período |
| 52 | Financeiro | Auditoria | `accounting:audit_timeline` | Finanças › Controlo | Auditoria |
| 53 | Financeiro | Extratos Bancários OFX | `accounting:bank_statement_list` | Finanças › A receber | Extratos OFX |
| 54 | Financeiro › Diagnóstico | Fake Delivery (PUDO) | `pudo-fake-delivery-suspects` | Operação › Pacotes | Suspeitas de entrega falsa (PUDO) |
| 55 | Ferramentas | Configurações | `system_config:index` | Sistema | Configurações |
| 56 | Ferramentas | Utilizadores | `system_config:user_list` | Sistema | Utilizadores |
| 57 | Ferramentas | Gerador de QR Code | `management:qr-generator` | Sistema | Ferramentas |

**NOTA:** a entrada 54 está hoje em Financeiro › Diagnóstico. A proposta move-a para Operação › Pacotes, porque trata suspeitas sobre pacotes, não dinheiro.
