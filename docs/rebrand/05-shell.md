# Shell da aplicação — Fase 2

**Estado:** concluída no branch `rebrand/leguas-gestao`. Sem deploy.

## O que mudou

| Área | Resultado |
|---|---|
| Layout | `templates/brand/shell.html`. `admin_base`, `settlements/base` e `management/base` passam a herdar dele |
| Menu | `core/navigation.py`: 2 níveis, filtrado por perfil, com contadores |
| Sidebar | Logótipo em negativo, 248 px, encolhe para 72 px, item ativo em laranja, gaveta em telemóvel |
| Topbar | Pesquisa global (`Ctrl+K`), tema, utilizador e sair |
| Pesquisa | `/search/`: pacote, motorista, CP4, cliente e contrato. Respeita o perfil |
| Título | `<Página> · Léguas Gestão` |
| Tema | Claro por omissão |
| Tailwind | Páginas internas sem CDN. Paleta azul, índigo, roxo e cinzentos remapeada para a marca |
| Faturas de frotas (D1) | `/settlements/fleet-invoices/`, com filtros, só para Gestão. Ligação "Ver faturas" na ficha da frota |
| Achados | 1, 2 e 14 resolvidos |

## Não feito nesta fase

| Item | Motivo |
|---|---|
| Heróis gradiente | Passam a usar a marca, mas continuam. Cada um tem ações próprias: Fase 3 |
| Seletor de hub e data na topbar | Decisão pedida. O Dashboard não tem filtro por hub |
| Precisa de atenção | Vista nova: Fase 3 |
| Portais, login e `converter` | Layout próprio, ainda com CDN: Fase 3 |

## CUIDADO

Classes montadas por variáveis têm de estar no `safelist` de `theme/tailwind.config.js`. Depois de cada página, compare as classes do DOM com o `app.css`.
