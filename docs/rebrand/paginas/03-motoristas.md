# Motoristas — /driversapp/admin/, /aprovar/, /criar/, /pedidos-alteracao/, /empresas-parceiras/

## Resumo
A Central passa ao cabeçalho único, com 4 KPI no topo. As restantes páginas de Motoristas ficam sem gradientes nem emojis.

## Erros encontrados
| # | Tipo | Gravidade | Descrição | Ficheiro |
|---|---|---|---|---|
| 1 | Visual | Alto | 8 KPI em 8 cores (achado 13) | `admin/drivers_central.html` |
| 2 | Visual | Médio | Donut dominado por vermelho (achado 13) | `admin/drivers_central.html` |
| 3 | Visual | Médio | Hero gradiente | `admin/drivers_central.html` |
| 4 | Texto | Baixo | "Empresas subcontratantes" e emojis | `empresas_parceiras.html`, `admin_complaints.html` |

## O que foi feito
| # | Alteração |
|---|---|
| 1 | Cabeçalho `lf-page-header`, com "Novo motorista" como ação primária |
| 2 | 4 KPI no topo. Os outros 4 passam a "Mais indicadores" |
| 3 | Vermelho no donut só para mais de 30 dias sem atividade |
| 4 | Faturas de frota com ligação "Ver faturas" na ficha |

## Em todo o sistema
- 147 gradientes passam a cor sólida da marca.
- 44 títulos passam ao estilo único. 14 quadrados com ícone saíram.
- A Pesquisa de pacotes exporta CSV com os filtros aplicados.

## Pendente
- 27 páginas ainda têm scroll horizontal em telemóvel, incluindo Aprovar, Novo motorista e Reclamações de clientes. Passagem própria no fim da Fase 3.
- As ações e os dados das views não mudaram.

## Métricas
336 capturas: 0 erros novos de consola e 0 pedidos falhados novos, depois da correção. Dados sintéticos.
