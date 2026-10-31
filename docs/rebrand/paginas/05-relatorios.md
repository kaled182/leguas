# Relatórios — /analytics/integrations/status/, /analytics/integrations/logs/

## Resumo
As 2 páginas passam ao cabeçalho único, com 4 KPI, `lf-table` e `lf-badge`. Os dados e as regras de saúde não mudam. As 2 páginas não mostram a sincronização real com o ReliableMaps.

## Erros encontrados
| # | Tipo | Gravidade | Descrição | Estado |
|---|---|---|---|---|
| 1 | Lógica | Alto | Nenhuma tarefa ativa escreve em `SyncLog` nem em `last_sync_at`. O commit 28c9836 removeu quem escrevia. Na Fase 0, `core_synclog` tinha 0 linhas e `core_partnerintegration` tinha 1 | **Por decidir** |
| 2 | Lógica | Alto | "Repetir" (antes "Retry") não repete nada. Grava um registo `PARTIAL` e marca a integração como `SUCCESS`, por isso uma falha passa a "Operacional" | **Por decidir** |
| 3 | Lógica | Baixo | `?days=abc` e `?integration=abc` devolvem 500 | **Por decidir** |
| 4 | Apresentação | Médio | Sem sincronizações em 24 h, a página mostrava 0 % a vermelho | Corrigido: mostra — |
| 5 | Apresentação | Baixo | "Hoje" mostrava também ontem | Texto passa a "Desde ontem". O filtro não muda |
| 6 | Visual | Médio | `.lf-table th` anulava `text-right` e `text-center` em todas as tabelas | Corrigido de forma global |
| 7 | Desempenho | Baixo | 2 queries por integração e contagens sem uso | Corrigido: 1 query, com os mesmos valores |

## O que foi feito
| # | Alteração |
|---|---|
| 1 | Termos: "Parceiro" passa a "Cliente", "Registros" a "Registos", "Timestamp" a "Início", "Retry" a "Repetir" |
| 2 | Estados em português sem migration: filtros `sync_label`, `sync_tone`, `health_label`, `health_tone` e `sync_operation` |
| 3 | Colunas com "Novos, Atualizados, Falhados" em vez de `+N ~N -N`. A legenda saiu |
| 4 | Barra de progresso e pontos animados saem. O estado usa `lf-badge` |
| 5 | Tempo em pt-PT, com singular e plural: "há 1 hora" |
| 6 | Filtros ficam no URL e há "Limpar". Acima de 100 registos, a página indica o total |

## Pendente
- A mensagem do "Repetir" ainda diz "Retry executado com sucesso". Fica até à decisão do erro 2.
- `/core/integrations/dashboard/` e Estado das APIs usam os mesmos dados.
- Em telemóvel, os KPI ocupam 1 coluna. Fica para a passagem de responsivo.

## Métricas
240 testes: as mesmas 4 falhas antigas de `main`, 0 regressões. 9 capturas (3 páginas × 3 modos), todas 200, 0 erros de consola e 0 scroll horizontal. Dados sintéticos.
