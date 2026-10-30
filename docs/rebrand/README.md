# Rebrand Léguas Gestão — Fase 0

**Estado:** concluída, a aguardar decisões. Branch `rebrand/leguas-gestao`, sem push.
**Base:** commit `469a7d8`, em 2026-10-30.

| Ficheiro | Conteúdo |
|---|---|
| [00-inventario.md](00-inventario.md) | Stack, 164 páginas, 402 rotas sem página, métricas |
| [01-auditoria-estilos.md](01-auditoria-estilos.md) | Cores, tipografia, raios, sombras, componentes duplicados |
| [02-navegacao.md](02-navegacao.md) | Proposta de menu e mapa das 57 entradas |
| [03-sem-uso.md](03-sem-uso.md) | Candidatos a remoção e comandos para produção |
| `screenshots/antes/` | 640 capturas de 168 páginas. Só no servidor, fora do git |
| `dados/` | Resultados em JSON |
| `ferramentas/` | Scripts para repetir a baseline na Fase 4 |

## Como a baseline foi feita

1. O servidor local correu num container na rede interna `rb-net`, sem saída para a internet.
2. A base foi um SQLite com seed sintético: 148 modelos, 900 tarefas, nomes fictícios.
3. O teste de rotas correu com 6 perfis: público, autenticado, staff, superuser, motorista e frota.
4. O Playwright capturou desktop e telemóvel, em tema claro e escuro.

**AVISO:** os dados são sintéticos. Queries e tempos servem só para comparar antes e depois.

**NOTA:** 32 capturas de tema escuro não existem, porque 16 páginas não têm tema escuro.

## Estado dos 15 achados do briefing

| # | Achado | Estado na Fase 0 | Evidência |
|---|---|---|---|
| 1 | Faturas Frota | Confirmado. Falta a lista global: decisão D1 | `sidebar.html:396`, `settlements/models.py:3256` |
| 2 | Botão de tema | Confirmado | `screenshots/antes/driversapp-admin-central-desktop-claro.png` |
| 3 | Cabeçalhos | Confirmado. São 19 variantes de hero e 5 outros padrões | `01-auditoria-estilos.md` |
| 4 | Moeda | Confirmado. 430 com `€` antes e 23 depois | `01-auditoria-estilos.md` |
| 5 | Enum cru | Confirmado | `accounting/templates/accounting/hub.html:232` |
| 6 | Cards do Hub | Confirmado | `screenshots/antes/accounting-hub-desktop-claro.png` |
| 7 | Pesquisa Global em inglês | Confirmado no código | `settlements/templates/settlements/cainiao_packages.html` |
| 8 | Ortografia | Confirmado. Activo 16, Inactivo 9, Acções 29 | Pesquisa em templates |
| 9 | pt-BR | Confirmado em 19 templates | Pesquisa em templates |
| 10 | Botão Apagar | Confirmado. Já tem modal de confirmação | `core/templates/core/partner_list.html:156` |
| 11 | Plurais forçados | Confirmado. 24 ocorrências | Pesquisa em templates |
| 12 | Dashboard duplicado | Confirmado | `dashboard_leguas/templates/dashboard_leguas/home.html:129`, `:156`, `:178` |
| 13 | 8 KPI em 8 cores | Confirmado | `screenshots/antes/driversapp-admin-central-desktop-claro.png` |
| 14 | `console.log` | Confirmado. 6 em `sidebar.js` e 31 no projeto | `static/js/sidebar.js:75` |
| 15 | Módulos sem uso | Aguarda `usage_report` | `03-sem-uso.md` |

## Bugs de lógica — não corrigidos

| # | Gravidade | Problema | Local |
|---|---|---|---|
| B1 | Alto | 105 páginas abrem para qualquer utilizador autenticado sem `is_staff`, incluindo finanças | `accounting/views.py` e outras views só com `login_required` |
| B2 | Alto | 4 rotas alteram dados com um GET, sem CSRF | `/core/partners/<pk>/toggle-status/`, `/core/integrations/<pk>/toggle-status/`, `/pricing/zones/<pk>/toggle-status/`, `/pricing/tariffs/<pk>/toggle-status/` |
| B3 | Médio | `/dashboard_v2/` abre sem login. A página é estática, mas mostra o menu interno | `dashboard_leguas/views.py:4` |
| B4 | Médio | 5 rotas devolvem 500 porque o template não existe | `/accounting/receitas/`, `/despesas/`, `/relatorios/` |
| B5 | Médio | Editar feriado falha no JS: `stringformat:"q"` devolve vazio | `settlements/templates/settlements/holiday_calendar.html:152` |
| B6 | Médio | Break-even: `floatformat` escreve vírgula dentro de JS e o script para | `accounting/templates/accounting/break_even.html:424` |
| B7 | Médio | `<template x-for>` dentro de SVG falha no Alpine | `accounting/templates/accounting/payables_inbox.html:325` |
| B8 | Médio | `addEventListener` sobre `modalRejeitar` nulo | `settlements/templates/settlements/claim_detail.html:478` |
| B9 | Médio | `init is not defined` na página do pacote. Local exato a confirmar | `/settlements/cainiao/waybill/<waybill>/` |
| B10 | Médio | 4 rotas de frota e tarifas devolvem 500 com 1 registo | `03-sem-uso.md`, secção 5 |
| B11 | Baixo | `driver_delivery_report` falha em motoristas com reclamações. A rota não tem ligações no código | `settlements/views.py:4231` |
| B12 | Baixo | 3 ícones não existem no `lucide@latest`. `github` saiu no Lucide 1.x. `receipt-percent` e `crystal-ball` também não existem nas versões 0.300.0 e 0.460.0 | Templates de `accounting` e `system_config` |
| B13 | Baixo | CSS do FullCalendar bloqueado pelo browser (ORB) | `fleet_management/templates/fleet_management/maintenance_calendar.html:7` |

**NOTA:** em 2026-10-30, produção tem 0 utilizadores ativos sem `is_staff`. B1 não afeta ninguém hoje. Todos os utilizadores `is_staff` veem finanças.

## Decisões pedidas

- **D1:** criar a lista global de `FleetInvoice`. Hoje só existe detalhe e JSON por frota.
- **D2:** aprovar a lista de remoção, depois do `usage_report`.
- **D3:** incluir os portais do motorista e da frota no rebrand.
- **D4:** dizer como tratar B1 a B13. Regra 1 do briefing: não corrigir sem ordem.
- **D5:** manter as capturas fora do git.

## Decisão técnica tomada

A Fase 1 usa o Tailwind standalone CLI, porque o deploy não tem Node. O `content` tem de ler templates, `.js` e `.py`, porque há classes geradas em JavaScript.
