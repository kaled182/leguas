# Painel do dia — /

## Resumo
Responde a "como está o dia". O hero saiu, ficam 4 KPI em neutro e 1 só visão do estado do dia.

## Antes / Depois
![antes](../screenshots/antes/painel-desktop-claro.png) ![depois](../screenshots/fase3/painel-desktop-light.png)

## Erros encontrados
| # | Tipo | Gravidade | Descrição | Ficheiro:linha |
|---|---|---|---|---|
| 1 | UX | Alto | 6 KPI em 6 cores | `home.html` |
| 2 | UX | Médio | "Dia concluído" e o donut "Estado do dia" mostravam o mesmo | `home.html` |
| 3 | Texto | Médio | "Stale", "Backlog", "Modo TV", "Taxa de sucesso" | `home.html` |
| 4 | Visual | Médio | Hero gradiente | `home.html` |
| 5 | Visual | Baixo | Datas do eixo rodadas a 45° | `home.html` |
| 6 | A11y | Médio | Texto secundário com pouco contraste no tema escuro | `input.css` |

## O que foi feito
| # | Alteração | Ficheiros |
|---|---|---|
| 1 | Cabeçalho compacto, com navegação de datas e Modo ecrã | `home.html` |
| 2 | 4 KPI no topo. Em distribuição e motoristas na estrada passam à linha do progresso | `home.html` |
| 3 | Donut removido. O gráfico de 30 dias ocupa a largura toda | `home.html` |
| 4 | Gráficos com a paleta da marca e rótulos sem rotação | `home.html`, `chart-theme.js` |
| 5 | Modo ecrã sempre escuro, sem menus, com números grandes | `shell.html`, `input.css` |
| 6 | Formatos pt-PT: `3 692`, `94,8 %` | `home.html` |

## Não alterado
- Nenhum cálculo mudou. `views_home.py` ficou igual, e os URL `?date=`, `?sla_days=`, `?sla_cal=` e `?tv=1` continuam.
- O bloco Gestão fica no fim da página, e o Operador não vê PF nem Pagamentos.

## Métricas
Erros de consola: 0 antes, 0 depois. Pedidos falhados: 0. Dados sintéticos.
