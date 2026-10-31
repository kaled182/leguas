# Relatório final — Rebrand Léguas Gestão

**Estado:** Fases 0 a 4 concluídas no branch `rebrand/leguas-gestao`. O branch tem 16 commits por publicar.
**Data:** 2026-10-31.

## Resumo
O sistema passa a ter um shell, um cabeçalho, uma paleta e um formato de moeda. A captura final abriu 169 páginas em desktop e em telemóvel. O rebrand encontrou falhas que vêm de antes, e as principais estão corrigidas no branch.

**AVISO:** as correções não estão em produção até ao deploy. Isto inclui a falha do IVA da frota e as permissões do Operador.

## Números
| Medida | Início | Fim |
|---|---|---|
| Páginas com scroll horizontal em telemóvel | 27 | 0 |
| Erros reais de consola | Vários | 0 (só `seed/documento.pdf`, do seed) |
| Testes | 135 | 261, com as mesmas 4 falhas antigas e 0 regressões |
| Capturas finais | 640 antes | 338 depois, com 4 páginas repetidas depois da última correção |
| Alteração total | — | 191 ficheiros, +5 992 e −7 227 linhas |

## Critérios de aceitação
| Critério | Estado |
|---|---|
| Relatório e capturas de cada página | Parcial: relatórios por bloco em `paginas/`, não por página |
| Zero erros de consola | Cumprido na captura final, com dados sintéticos |
| Zero cores fora de `tokens.css` | **Por cumprir:** 268 valores hex restam em templates, a maioria em mapas, folhas PDF e templates sem uso |
| Nenhum texto em inglês | Parcial: faltam mensagens de `views.py` e textos gerados em JavaScript |
| Lighthouse ≥ 90 | **Não medido** |
| KPIs iguais antes e depois | Parcial: não houve comparação automática. Os cálculos só mudaram onde está listado abaixo |
| URLs e parâmetros | Cumprido: rotas removidas têm redirect |
| Testes | Cumprido, mais testes novos de componentes |
| 15 achados da secção 1.1 | Cumprido: ver tabela |
| Faturas de frotas subcontratadas | Cumprido em produção |
| Tailwind compilado, sem CDN | Cumprido |
| Um cabeçalho de página | Cumprido nas páginas de trabalho. Fora disso: mapas, ficha de envio, contrato gerado, conta-corrente, admin Django |
| Moeda num formato | Parcial: restam 42 `toFixed`, parte deles fora de moeda |

## Código de cálculo que mudou
- `analytics/views.py`: as 2 páginas leem `ReliableEpodSync`, por decisão 1A.
- `settlements/cainiao_views.py`: retira o custo das respostas ao Operador.
- `core/views.py`, `settlements/views.py`, `central_views.py`: só textos.
- `contracts/views.py`: novo `signed_count` para a coluna Cobertura.
- `accounting/views_exec.py`: só o nome do mês.
- Fora disto, nenhuma view de cálculo mudou.

## Os 15 achados
| # | Estado |
|---|---|
| 1 | Corrigido: lista global de faturas de frotas |
| 2 | Corrigido: o botão de tema está na topbar |
| 3 | Corrigido: `lf-page-header` |
| 4 | Corrigido: filtros `eur`, `eur0` e `lfEur` |
| 5 | Corrigido: `fin_status` e outros filtros de estado |
| 6 | Corrigido: 4 KPI em Visão financeira |
| 7 | Corrigido na Pesquisa |
| 8 | Corrigido em textos visíveis |
| 9 | Corrigido nos templates tratados |
| 10 | Corrigido: menu de ações |
| 11 | Corrigido na maioria: restam casos em JavaScript |
| 12 | Corrigido no Painel do dia |
| 13 | Corrigido na Central |
| 14 | Corrigido na Fase 2 |
| 15 | Corrigido: Etapa A em produção |

## Falhas antigas encontradas
| Falha | Estado |
|---|---|
| Perfil da frota gravava IVA 0 e apagava o preço por omissão | Corrigida no branch. **Dados por verificar** |
| Operador via preços e custos da Cainiao | Corrigida no branch |
| Erros apareciam a verde (`MESSAGE_TAGS`) | Corrigida no branch |
| "Resolver" alerta financeiro devolvia 404 | Corrigida no branch |
| "Repetir" sincronização era simulado | Retirado do branch |
| Estado das APIs sem dados reais | Corrigido no branch: lê `ReliableEpodSync` |
| "Nova regra" de bónus não guarda | Mantida, por decisão do utilizador |

## Decisões pendentes
1. Autorizar o deploy.
2. Autorizar a leitura das frotas em produção.
3. Decidir a Etapa B: tabelas de módulos removidos.

## Decisões tomadas no fim
- 7 templates sem uso removidos. Ficam no histórico do git.
- O botão "Importar Pré-fatura Cainiao" fica até refazer a Faturação Cainiao.

## Não testado
- Sessão real de motorista e de frota. App Léguas.
- Login por WhatsApp. Envio do cadastro público até ao fim.
- Ações que gravam em Finanças. Impressão de PDF e de QR Code.
- Lighthouse. Conversor com lista processada. Página 500 no browser.
