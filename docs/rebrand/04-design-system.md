# Sistema de design — Fase 1

**Estado:** concluída no branch `rebrand/leguas-gestao`. Sem deploy.
**Página interna:** `/_design/`, só para staff.

## Ficheiros

| Ficheiro | Conteúdo |
|---|---|
| `static/brand/tokens.css` | Cores, tipografia, espaçamento de 4 px, raios, sombras, camadas e transições, nos 2 temas |
| `static/brand/logo/` | 16 logótipos SVG oficiais |
| `static/brand/favicon.ico`, `favicon-32.png`, `apple-touch-icon.png` | Gerados a partir do símbolo |
| `theme/tailwind.config.js`, `theme/static/src/input.css` | Tailwind e classes `lf-*` |
| `templates/components/` | 19 componentes |
| `templates/brand/base.html` | Base mínima da Fase 1 |
| `core/templatetags/ui.py` | Filtros `eur`, `pt_int`, `pct`, `status_label`, `status_tone` e tag `query_with` |
| `static/brand/ui.js`, `chart-theme.js` | Modal, toast, tema, menu, `Ctrl+K` e tema dos gráficos |

## Build do Tailwind

A stage `css` do `production/Dockerfile` compila o CSS com `tailwindcss 3.4.17` do lockfile. O Node fica só nessa stage. O `app.css` não entra no Git.

Compile localmente com:

```bash
docker run --rm -v "$PWD":/src -w /src/theme node:22-alpine sh -c "npm ci && npx tailwindcss -c tailwind.config.js -i static/src/input.css -o ../static/brand/app.css --minify"
```

**CUIDADO:** classes montadas com variáveis (`lf-btn-{{ variant }}`) têm de estar no `safelist` de `theme/tailwind.config.js`. Sem isso, o build remove-as sem aviso.

**NOTA:** a Fase 0 previa o Tailwind standalone CLI. O modo automático recusou executar um binário descarregado no servidor. A stage Node usa o lockfile do projeto e é mais segura.

## Contraste

Todos os pares passam WCAG AA (4,5:1) nos 2 temas.

| Texto | Fundo | Claro | Escuro |
|---|---|---|---|
| Texto | Fundo | 17,2 | 16,6 |
| Texto secundário | Superfície | 6,1 | 7,9 |
| Texto secundário | Superfície alternativa | 5,1 | 7,0 |
| Botão primário | Primária | 17,1 | 7,5 |
| Botão secundário | Laranja | 7,5 | 7,5 |
| Laranja como texto | Superfície | 5,1 | 7,5 |
| Sucesso | Fundo do estado | 5,5 | 7,6 |
| Erro | Fundo do estado | 5,2 | 7,4 |
| Aviso | Fundo do estado | 6,5 | 8,2 |
| Neutro | Fundo do estado | 6,6 | 7,6 |

## Cores acrescentadas à secção 5

**Precisa de validação:** estas cores não estão no manual.

- **Tema escuro:** superfícies `#2A1138` e `#351B45`. O manual só define o fundo `#1C0627`.
- **Estados:** fundos e textos derivados, porque `--success`, `--danger` e `--warning` não passam AA em texto pequeno.
- **Laranja como texto:** `#A65A05`. `--brand-orange-dark` dá 3,1:1 sobre branco e não passa AA.

## Pendente para a Fase 2

- O `Sidebar` ainda não é drawer em telemóvel.
- O seletor de data segue a língua do browser.
- `eur` existe, mas as páginas atuais ainda não o usam.
