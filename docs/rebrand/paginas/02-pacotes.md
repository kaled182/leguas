# Pacotes — /settlements/packages/, /claims/, /recursos/, /pacote/, /pudo/

## Resumo
6 páginas passam ao cabeçalho único, com 4 KPI no topo, sem emojis e com estados em português.

## Erros encontrados
| # | Tipo | Gravidade | Descrição | Ficheiro |
|---|---|---|---|---|
| 1 | Texto | Médio | Inglês na Pesquisa: Wrong HUB, Exception, Date from / to (achado 7) | `cainiao_packages.html` |
| 2 | Texto | Médio | 18 emojis em títulos e chips | `cainiao_packages.html` |
| 3 | UX | Médio | 7 KPI em Reclamações e em Recursos | `claim_list_v2.html`, `appeals_inbox.html` |
| 4 | Texto | Médio | Estados Cainiao crus na tabela | `cainiao_packages.html`, `package_360.html` |
| 5 | Texto | Baixo | Datas ISO | `cainiao_packages.html` |

## O que foi feito
| # | Alteração |
|---|---|
| 1 | Cabeçalho `lf-page-header` em 6 páginas |
| 2 | 4 KPI em neutro no topo. Os restantes passam a "Mais indicadores" |
| 3 | Estados traduzidos, com o valor original no tooltip |
| 4 | Datas em dd/mm/aaaa |
| 5 | Banners sem gradiente e sem emojis no detalhe do pacote |

## Não alterado (precisa de decisão)
- O botão "Exportar" da Pesquisa ainda não gera CSV. O código indica "ainda não implementado". Bug de lógica.
- Os filtros, URLs e chamadas à API não mudaram.

## Métricas
Erros de consola: 0 em 14 capturas. Dados sintéticos.
