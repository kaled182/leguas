# Finanças — /accounting/, /payroll/, /driversapp/admin/pagamentos/, /settlements/pre-invoices/

## Resumo
Finanças passa ao cabeçalho único, com `lf-table`, `lf-kpi` e `lf-badge`. A passagem cobriu 44 templates e 42 páginas. Os cálculos não mudam.

## Erros encontrados
| # | Tipo | Gravidade | Descrição | Estado |
|---|---|---|---|---|
| 1 | Apresentação | Médio | O Resumo executivo mostrava o mês em inglês ("September De 2026") | Corrigido |
| 2 | Texto | Médio | A Visão financeira mostrava estados crus (achado 5): `PENDING`, `CALCULADO` | Corrigido com o filtro `fin_status` |
| 3 | HTML | Médio | Um `<a>` dentro de outro `<a>` no cartão Tesouraria | Corrigido |
| 4 | Visual | Baixo | Chart.js 4.4.0 carregado por cima do tema | Tag retirada de Tesouraria e Break-even |
| 5 | Visual | Médio | PDF a vermelho, como ação destrutiva | Corrigido |
| 6 | Visual | Médio | Cor de texto sem variante escura em avisos e totais | Corrigido |

## O que foi feito
| # | Alteração |
|---|---|
| 1 | Visão financeira: 4 KPI, os restantes em "Mais indicadores" |
| 2 | Resumo executivo: cabeçalho da página separado da folha A4. A folha é sempre clara e imprime sem o menu |
| 3 | Moeda `1 234,56 €`, `1 235 €` (novo filtro `eur0`) e percentagem `94,8 %` |
| 4 | Termos: Conta, Pré-fatura, Cliente, Frota, Extrato, Reciclagem, Previsão |
| 5 | Plurais com `pluralize` em vez de `fatura(s)` |
| 6 | Blocos locais de mensagens retirados: o toast do shell mostra-as |
| 7 | Tabelas com `lf-table` e botões com `lf-btn` |

## Pendente
- `pre_invoice_admin_list.html` mantém 39 `toFixed` e 8 `alert()` em JavaScript.
- Outros `alert()` em `bill_form`, `payables_inbox`, `treasury_dashboard`, `cash_entries_dashboard` e `shareholder_dashboard`.
- Títulos e textos gerados em JavaScript não passaram pela substituição de termos.
- `bill_form` e `imposto_form` mantêm os campos com o estilo próprio.
- Nas linhas de Pré-faturas ficam até 4 botões. O menu de ações fica para a passagem final.
- Regras de bónus continuam sem guardar, por decisão do utilizador.
- `financial_dashboard_v2`, `invoice_list_v2`, `invoice_detail` e `settlement_list_v2` não entraram nesta passagem.
- As 126 capturas são anteriores aos últimos ajustes de texto. Depois delas, repeti só Tesouraria, Pagamentos e Break-even.

## Métricas
247 testes: as mesmas 4 falhas antigas de `main`, 0 regressões. 126 capturas (42 páginas × 3 modos): 0 erros de consola e 0 scroll horizontal. 0 alterações em `{% %}`, `{{ }}` e atributos de código, além das listadas. Dados sintéticos.
