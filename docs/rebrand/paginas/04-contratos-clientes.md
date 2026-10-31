# Contratos e Clientes — /contracts/admin/, /core/partners/, /core/integrations/

## Resumo
Contratos e Clientes passam ao cabeçalho único, com tabelas e estados da marca. "Parceiros" passa a "Clientes e plataformas". O Apagar sai da linha para um menu de ações.

## Erros encontrados
| # | Tipo | Gravidade | Descrição | Estado |
|---|---|---|---|---|
| 1 | Permissões | Alto | O Operador via o valor por pacote, o IVA e o IRS no modal Configurações da Cainiao (decisão P4) | Corrigido |
| 2 | Apresentação | Médio | A coluna Cobertura de "Por assinar" saía vazia (`/2`) | Corrigido |
| 3 | Apresentação | Médio | O KPI "Ativos" de Clientes mostrava o total filtrado, não os ativos | KPI retirado. O subtítulo mostra os resultados |
| 4 | Visual | Alto | Botão Apagar em cada linha (achado 10) | Corrigido |
| 5 | Texto | Baixo | "integração(ões)" e outros plurais forçados (achado 11) | Corrigido em Clientes. Falta nos outros blocos |
| 6 | Lógica | Alto | "Nova regra" chama `/partners/…/save/`, sem `/core`. A rota devolve 404 e a regra não é guardada | **Por decidir** |
| 7 | Lógica | Médio | "Resolver" alerta chama `/financial-alerts/…`, sem `/core`. A rota devolve 404 | **Por decidir** |
| 8 | Permissões | Médio | A API de "Não chegaram" ainda envia `total_cost_eur` ao Operador. A página já não o mostra | **Por decidir** |

## O que foi feito
| # | Alteração |
|---|---|
| 1 | Ficha Cainiao: 4 KPI no topo, o resto em "Mais indicadores", 1 botão primário |
| 2 | Estados em português: Entregues, Em distribuição, Atribuídos, Falhadas, Não chegaram |
| 3 | Modelos, Assinados, Por assinar e formulários com tokens, `lf-table` e `lf-badge` |
| 4 | Financeiro do cliente com 4 KPI e valores no formato `1 234,56 €` |
| 5 | Central: separadores "Ativos" e "Inativos" e KPI sem ícones |
| 6 | Em 11 templates, os gerúndios pt-BR passam a "A mostrar", "A aguardar" e "A carregar" |
| 7 | Novo `window.lfEur` para valores em JavaScript |

## Pendente
- Textos de ajuda em `core/models.py` ainda dizem "parceiro". Alterá-los exige migration, proibida no rebrand.
- `generator.html` mantém o layout próprio, porque gera o documento legal.
- As `alert()` da ficha Cainiao ainda não usam toast.

## Métricas
229 testes: as mesmas 4 falhas antigas de `main`, 0 regressões. 42 capturas: 0 erros de consola e 0 scroll horizontal em telemóvel. Operador verificado no browser. Dados sintéticos.
