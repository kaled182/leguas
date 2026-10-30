# Mapa de permissões — por aprovar

**Estado:** aprovado em 2026-10-30, com as correções ao mapa. Nenhuma permissão foi alterada.
**Base:** 164 páginas do inventário da Fase 0.

## Regras

- **Gestão:** tudo. Superuser, ou membro do novo grupo `Gestão`.
- **Operador:** `is_staff`, sem Finanças, Tarifas, Sistema e Utilizadores.
- **Motorista e Frota:** só o próprio portal. O código atual já bloqueia o acesso cruzado.
- **Sem perfil:** sem acesso. Hoje existem 0 utilizadores ativos sem `is_staff`.
- **Rotas JSON, CSV e PDF:** seguem o perfil da página que as usa.

## Implementação proposta

Um middleware central, com regras por prefixo de URL e negação por omissão. Motivo: as 402 rotas sem página ficam protegidas sem editar cada view. O menu esconde as entradas sem acesso.

**Exceções ao middleware:** `/health/`, `/auth/`, `/api/app/v1/` (token), `/geozonas/api/zonas/export/` (chave), webhooks, `/driversapp/cadastro*`. Lista completa em `allowlist.md`.

## Decisões

| # | Questão | Estado |
|---|---|---|
| P1 | Quem fica em Gestão? | Hoje 4 utilizadores, todos superuser. Ver a nota abaixo |
| P2 | O Operador vê faturas, descontos e relatórios na ficha do motorista? | Não |
| P3 | O Operador vê preços? | Não |
| P4 | O Operador vê os KPI de pagamentos no Dashboard? | Não, esconder o bloco |
| Reclamações | Quem vê `/settlements/claims/` e `/settlements/recursos/`? | Só Gestão: os julgamentos chegam por API para cobrança |

**NOTA:** o perfil Gestão inclui todo o superuser. O grupo `Gestão` só é preciso para quem não for superuser.

**CUIDADO:** hoje existem 0 Operadores. O perfil só tem efeito depois de criar utilizadores `is_staff` sem superuser.

## Totais

| Grupo | Páginas |
|---|---|
| Finanças | 66 |
| Operação | 30 |
| Portal do motorista | 17 |
| Autenticação e registo | 11 |
| Tarifas | 9 |
| Portal da frota | 8 |
| Contratos | 7 |
| Clientes e plataformas | 7 |
| Sistema e utilizadores | 7 |
| Painel antigo | 1 |
| Frotas subcontratadas | 1 |

## Mapa

| URL | Grupo | Gestão | Operador | Motorista | Frota | Nota |
|---|---|---|---|---|---|---|
| `/` | Operação | sim | sim | - | - |  |
| `/accounting/` | Finanças | sim | - | - | - |  |
| `/accounting/a-pagar/` | Finanças | sim | - | - | - |  |
| `/accounting/a-pagar/calendario/` | Finanças | sim | - | - | - |  |
| `/accounting/a-pagar/forecast/` | Finanças | sim | - | - | - |  |
| `/accounting/a-pagar/sem-ff/` | Finanças | sim | - | - | - |  |
| `/accounting/a-pagar/sem-pf/` | Finanças | sim | - | - | - |  |
| `/accounting/auditoria/` | Finanças | sim | - | - | - |  |
| `/accounting/break-even/` | Finanças | sim | - | - | - |  |
| `/accounting/categorias/` | Finanças | sim | - | - | - |  |
| `/accounting/categorias/<int:pk>/editar/` | Finanças | sim | - | - | - |  |
| `/accounting/categorias/nova/` | Finanças | sim | - | - | - |  |
| `/accounting/centros-custo/` | Finanças | sim | - | - | - |  |
| `/accounting/centros-custo/<int:pk>/editar/` | Finanças | sim | - | - | - |  |
| `/accounting/centros-custo/novo/` | Finanças | sim | - | - | - |  |
| `/accounting/contas-a-pagar/` | Finanças | sim | - | - | - |  |
| `/accounting/contas-a-pagar/<int:pk>/` | Finanças | sim | - | - | - |  |
| `/accounting/contas-a-pagar/<int:pk>/editar/` | Finanças | sim | - | - | - |  |
| `/accounting/contas-a-pagar/lixeira/` | Finanças | sim | - | - | - |  |
| `/accounting/contas-a-pagar/nova/` | Finanças | sim | - | - | - |  |
| `/accounting/despesas/<int:pk>/editar/` | Finanças | sim | - | - | - |  |
| `/accounting/despesas/nova/` | Finanças | sim | - | - | - |  |
| `/accounting/dre/` | Finanças | sim | - | - | - |  |
| `/accounting/exec/` | Finanças | sim | - | - | - |  |
| `/accounting/extractos/` | Finanças | sim | - | - | - |  |
| `/accounting/extractos/<int:pk>/` | Finanças | sim | - | - | - |  |
| `/accounting/extractos/upload/` | Finanças | sim | - | - | - |  |
| `/accounting/fluxo-caixa/` | Finanças | sim | - | - | - |  |
| `/accounting/fornecedores/` | Finanças | sim | - | - | - |  |
| `/accounting/fornecedores/<int:pk>/editar/` | Finanças | sim | - | - | - |  |
| `/accounting/fornecedores/novo/` | Finanças | sim | - | - | - |  |
| `/accounting/fornecedores/tags/` | Finanças | sim | - | - | - |  |
| `/accounting/hub/` | Finanças | sim | - | - | - |  |
| `/accounting/impostos/` | Finanças | sim | - | - | - |  |
| `/accounting/impostos/<int:pk>/editar/` | Finanças | sim | - | - | - |  |
| `/accounting/impostos/novo/` | Finanças | sim | - | - | - |  |
| `/accounting/impostos/planos/` | Finanças | sim | - | - | - |  |
| `/accounting/pendentes-regularizacao/` | Finanças | sim | - | - | - |  |
| `/accounting/periodos/` | Finanças | sim | - | - | - |  |
| `/accounting/receitas/<int:pk>/editar/` | Finanças | sim | - | - | - |  |
| `/accounting/receitas/nova/` | Finanças | sim | - | - | - |  |
| `/accounting/reconciliacao-bancaria/` | Finanças | sim | - | - | - |  |
| `/accounting/tesouraria/` | Finanças | sim | - | - | - |  |
| `/analytics/incidents/` | Operação | sim | sim | - | - |  |
| `/analytics/integrations/logs/` | Operação | sim | sim | - | - |  |
| `/analytics/integrations/status/` | Operação | sim | sim | - | - |  |
| `/analytics/reports/fleet-costs/` | Finanças | sim | - | - | - | Custos |
| `/analytics/vehicles/` | Operação | sim | sim | - | - |  |
| `/auth/` | Autenticação e registo | sim | sim | sim | sim | Público |
| `/auth/authenticate/` | Autenticação e registo | sim | sim | sim | sim | Público |
| `/auth/driver/` | Autenticação e registo | sim | sim | sim | sim | Público |
| `/auth/driver/credentials/<int:driver_id>/` | Autenticação e registo | sim | sim | sim | sim | Público |
| `/auth/driver/login/` | Autenticação e registo | sim | sim | sim | sim | Público |
| `/auth/empresa/` | Autenticação e registo | sim | sim | sim | sim | Público |
| `/auth/empresa/credentials/<int:empresa_id>/` | Autenticação e registo | sim | sim | sim | sim | Público |
| `/auth/empresa/login/` | Autenticação e registo | sim | sim | sim | sim | Público |
| `/auth/login/` | Autenticação e registo | sim | sim | sim | sim | Público |
| `/contracts/admin/gerado/<int:pk>/` | Contratos | sim | sim | - | - |  |
| `/contracts/admin/gerar/<int:driver_id>/` | Contratos | sim | sim | - | - |  |
| `/contracts/admin/missing/` | Contratos | sim | sim | - | - |  |
| `/contracts/admin/signed/` | Contratos | sim | sim | - | - |  |
| `/contracts/admin/templates/` | Contratos | sim | - | - | - | Modelos |
| `/contracts/admin/templates/<int:pk>/edit/` | Contratos | sim | - | - | - | Modelos |
| `/contracts/admin/templates/create/` | Contratos | sim | - | - | - | Modelos |
| `/contracts/portal/<int:driver_id>/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/contracts/portal/<int:driver_id>/sign/<int:template_id>/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/contracts/portal/<int:driver_id>/view/<int:contract_id>/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/converter/` | Operação | sim | sim | - | - |  |
| `/core/drivers/<int:driver_id>/account/` | Finanças | sim | - | - | - |  |
| `/core/financial-alerts/` | Finanças | sim | - | - | - |  |
| `/core/integrations/<int:pk>/edit/` | Clientes e plataformas | sim | - | - | - | Só leitura para Operador: P3 |
| `/core/integrations/dashboard/` | Clientes e plataformas | sim | sim | - | - | Só leitura |
| `/core/partners/` | Clientes e plataformas | sim | sim | - | - | Só leitura |
| `/core/partners/<int:partner_pk>/integrations/create/` | Clientes e plataformas | sim | - | - | - | Só leitura para Operador: P3 |
| `/core/partners/<int:pk>/` | Clientes e plataformas | sim | sim | - | - | Só leitura |
| `/core/partners/<int:pk>/bonus-rules/` | Finanças | sim | - | - | - |  |
| `/core/partners/<int:pk>/edit/` | Clientes e plataformas | sim | - | - | - | Só leitura para Operador: P3 |
| `/core/partners/<int:pk>/financial/` | Finanças | sim | - | - | - |  |
| `/core/partners/create/` | Clientes e plataformas | sim | - | - | - | Só leitura para Operador: P3 |
| `/dashboard_v2/` | Painel antigo | sim | - | - | - | Sai do público (B3) |
| `/driversapp/admin/` | Operação | sim | sim | - | - |  |
| `/driversapp/admin/aprovar/` | Operação | sim | sim | - | - |  |
| `/driversapp/admin/central/` | Operação | sim | sim | - | - |  |
| `/driversapp/admin/criar/` | Operação | sim | sim | - | - |  |
| `/driversapp/admin/pagamentos/` | Finanças | sim | - | - | - |  |
| `/driversapp/admin/pedidos-alteracao/` | Operação | sim | sim | - | - |  |
| `/driversapp/admin/reclamacoes/` | Operação | sim | sim | - | - |  |
| `/driversapp/admin/tickets-cainiao/` | Operação | sim | sim | - | - |  |
| `/driversapp/cadastro-completo/` | Autenticação e registo | sim | sim | sim | sim | Público |
| `/driversapp/cadastro/` | Autenticação e registo | sim | sim | sim | sim | Público |
| `/driversapp/empresas-parceiras/` | Frotas subcontratadas | sim | sim | - | - | Sem faturas: P3 |
| `/driversapp/portal/<int:driver_id>/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/driversapp/portal/<int:driver_id>/descontos/` | Portal do motorista | sim | - | sim | - | Sem Operador: P2 |
| `/driversapp/portal/<int:driver_id>/documentos/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/driversapp/portal/<int:driver_id>/editar/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/driversapp/portal/<int:driver_id>/faturas/` | Portal do motorista | sim | - | sim | - | Sem Operador: P2 |
| `/driversapp/portal/<int:driver_id>/helpers/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/driversapp/portal/<int:driver_id>/indicacoes/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/driversapp/portal/<int:driver_id>/logins/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/driversapp/portal/<int:driver_id>/perfil/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/driversapp/portal/<int:driver_id>/pf/<int:pre_invoice_id>/` | Portal do motorista | sim | - | sim | - | Sem Operador: P2 |
| `/driversapp/portal/<int:driver_id>/pudos/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/driversapp/portal/<int:driver_id>/reclamacoes/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/driversapp/portal/<int:driver_id>/relatorios/` | Portal do motorista | sim | - | sim | - | Sem Operador: P2 |
| `/driversapp/portal/<int:driver_id>/veiculos/` | Portal do motorista | sim | sim | sim | - | Só o próprio motorista |
| `/fleet/dashboard/` | Operação | sim | sim | - | - |  |
| `/fleet/maintenance/` | Operação | sim | sim | - | - |  |
| `/fleet/maintenance/<int:pk>/` | Operação | sim | sim | - | - |  |
| `/fleet/maintenance/<int:pk>/edit/` | Operação | sim | sim | - | - |  |
| `/fleet/maintenance/calendar/` | Operação | sim | sim | - | - |  |
| `/fleet/maintenance/create/` | Operação | sim | sim | - | - |  |
| `/fleet/vehicles/` | Operação | sim | sim | - | - |  |
| `/fleet/vehicles/<int:pk>/edit/` | Operação | sim | sim | - | - |  |
| `/fleet/vehicles/create/` | Operação | sim | sim | - | - |  |
| `/management/tools/qr-generator/` | Operação | sim | sim | - | - |  |
| `/payroll/folhas/` | Finanças | sim | - | - | - |  |
| `/payroll/folhas/<int:pk>/` | Finanças | sim | - | - | - |  |
| `/payroll/folhas/gerar/` | Finanças | sim | - | - | - |  |
| `/payroll/funcionarios/` | Finanças | sim | - | - | - |  |
| `/payroll/funcionarios/<int:pk>/` | Finanças | sim | - | - | - |  |
| `/payroll/funcionarios/novo/` | Finanças | sim | - | - | - |  |
| `/pricing/calculator/` | Tarifas | sim | - | - | - | Sem Operador: P3 |
| `/pricing/tariffs/` | Tarifas | sim | - | - | - | Sem Operador: P3 |
| `/pricing/tariffs/<int:pk>/edit/` | Tarifas | sim | - | - | - | Sem Operador: P3 |
| `/pricing/tariffs/create/` | Tarifas | sim | - | - | - | Sem Operador: P3 |
| `/pricing/tariffs/import/` | Tarifas | sim | - | - | - | Sem Operador: P3 |
| `/pricing/zones/` | Tarifas | sim | - | - | - | Sem Operador: P3 |
| `/pricing/zones/<int:pk>/edit/` | Tarifas | sim | - | - | - | Sem Operador: P3 |
| `/pricing/zones/create/` | Tarifas | sim | - | - | - | Sem Operador: P3 |
| `/pricing/zones/import/` | Tarifas | sim | - | - | - | Sem Operador: P3 |
| `/settlements/adiantamentos/` | Finanças | sim | - | - | - |  |
| `/settlements/cainiao/map/` | Operação | sim | sim | - | - |  |
| `/settlements/cainiao/map/compare/` | Operação | sim | sim | - | - |  |
| `/settlements/cainiao/waybill/<str:waybill>/` | Operação | sim | sim | - | - | Esconder valores ao Operador |
| `/settlements/calendar/` | Finanças | sim | - | - | - |  |
| `/settlements/claims/` | Finanças | sim | - | - | - | Reclamações: julgamentos por API para cobrança |
| `/settlements/claims/<int:claim_id>/` | Finanças | sim | - | - | - | Reclamações: julgamentos por API para cobrança |
| `/settlements/claims/appeals/` | Finanças | sim | - | - | - | Reclamações: julgamentos por API para cobrança |
| `/settlements/empresas/<int:empresa_id>/portal/` | Portal da frota | sim | - | - | sim | Só a própria frota |
| `/settlements/empresas/<int:empresa_id>/portal/claims/` | Portal da frota | sim | - | - | sim | Só a própria frota |
| `/settlements/empresas/<int:empresa_id>/portal/contratos/` | Portal da frota | sim | - | - | sim | Só a própria frota |
| `/settlements/empresas/<int:empresa_id>/portal/documentos/` | Portal da frota | sim | - | - | sim | Só a própria frota |
| `/settlements/empresas/<int:empresa_id>/portal/faturas/` | Portal da frota | sim | - | - | sim | Só a própria frota |
| `/settlements/empresas/<int:empresa_id>/portal/motoristas/` | Portal da frota | sim | - | - | sim | Só a própria frota |
| `/settlements/empresas/<int:empresa_id>/portal/perfil/` | Portal da frota | sim | - | - | sim | Só a própria frota |
| `/settlements/empresas/<int:empresa_id>/portal/relatorios/` | Portal da frota | sim | - | - | sim | Só a própria frota |
| `/settlements/financial/` | Finanças | sim | - | - | - |  |
| `/settlements/invoices/` | Finanças | sim | - | - | - |  |
| `/settlements/invoices/<int:invoice_id>/` | Finanças | sim | - | - | - |  |
| `/settlements/invoices/cainiao/<int:import_id>/` | Finanças | sim | - | - | - |  |
| `/settlements/packages/` | Operação | sim | sim | - | - |  |
| `/settlements/pacote/<str:waybill>/` | Operação | sim | sim | - | - | Esconder valores ao Operador |
| `/settlements/pudo/fake-delivery-suspects/` | Operação | sim | sim | - | - |  |
| `/settlements/recursos/` | Finanças | sim | - | - | - | Reclamações: julgamentos por API para cobrança |
| `/settlements/settlements/` | Finanças | sim | - | - | - |  |
| `/settlements/socios/` | Finanças | sim | - | - | - |  |
| `/sla/prazos/` | Operação | sim | sim | - | - |  |
| `/system/` | Sistema e utilizadores | sim | - | - | - |  |
| `/system/atualizacao/` | Sistema e utilizadores | sim | - | - | - |  |
| `/system/recovery-keys/` | Sistema e utilizadores | sim | - | - | - |  |
| `/system/users/` | Sistema e utilizadores | sim | - | - | - |  |
| `/system/users/<int:pk>/edit/` | Sistema e utilizadores | sim | - | - | - |  |
| `/system/users/create/` | Sistema e utilizadores | sim | - | - | - |  |
| `/system/whatsapp/` | Sistema e utilizadores | sim | - | - | - |  |
