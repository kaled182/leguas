# Changelog

Todas as alterações relevantes do projecto. Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [v1.0.0-rc1] — 2026-05-02

Primeira release production-ready. Stack reduzida e plug-in-play.

### Adicionado
- 📦 **Pasta `production/`** completa com tudo para deploy:
  - Dockerfile multi-stage (builder + runtime, user `django` não-root)
  - `docker-compose.yml` production-ready (7 serviços, healthchecks)
  - `Caddyfile` com SSL automático Let's Encrypt
  - `gunicorn_config.py` (auto-detect CPUs, sync workers, max-requests anti-leak)
  - `entrypoint.sh` (migrate + collectstatic + auto-superuser)
  - `install.sh` (wizard interactivo primeira instalação)
  - `update.sh` (update sem perder dados)
  - `backup.sh` (DB + media + Google Drive opcional, retenção 30 dias)
  - `DEPLOYMENT.md` guia completo
- 🔒 **Healthcheck `/health/`** Django com verificação DB + cache
- 📊 **Conta-Corrente Motoristas** (refactor `PreInvoiceAdvance`):
  - Lançamentos PENDENTE/INCLUIDO_PF/CANCELADO independentes da PF
  - Página `/settlements/adiantamentos/` com bulk + single create
  - Modal "Lançamento do Dia" para entrada em lote
  - Prompt automático de inclusão ao criar PF
- 🤝 **Reembolsos a Sócios (Terceiros)**:
  - Models `Shareholder` + `ThirdPartyReimbursement`
  - Auto-criação de reembolso quando lançamento `paid_by_source=TERCEIRO`
  - Página `/settlements/socios/` para gestão e marcação como pago
  - KPI clicável no dashboard financeiro
- 💰 **Page Liquidações de Motoristas** funcional (lista PFs filtráveis)
- 🚛 **Cainiao** import com salvaguardas anti-duplicação:
  - Detecção `filename_date_mismatch` (warning antes de gravar)
  - Detecção `filename_already_imported` (avisa se ficheiro já foi importado noutra data)
  - Helper `_extract_date_from_filename` para parsing
- 🏢 **Fleet Invoice** PDF refeito:
  - Header com logo Léguas + dados fiscais
  - Compactação de 5 → 2 páginas (sem PageBreak entre drivers)
  - Cálculo de bónus por login (consistente com PF individual)
- 🚫 **Bloqueio**: motorista de frota não emite PF individual
- 📱 **Lançamento manual**: campo "Pago por" (Empresa/Sócio) per-linha em modal de adiantamento
- 🔧 Toast notifications (padrão visual unificado em vez de `alert()`)

### Removido
- ❌ **Chatwoot stack** (3 containers + 2 volumes Postgres/Redis) — não usado
- ❌ **Typebot stack** (3 containers + 1 volume Postgres) — não usado
- ❌ **Mailhog** — só desenvolvimento, sem uso real
- ❌ **wppconnect_bridge** — só ligava Chatwoot ao WPPConnect
- ❌ **3 volumes Evolution órfãos** — Evolution API legacy
- ❌ **`files/Dump20250927/`** (22 MB SQL dumps antigos)
- ❌ **`files/leguas-monitoring-v1.2/`** (1.1 GB cópia legacy do projecto)
- ❌ **`.env.evolution.example`** template legacy
- ❌ **`channels==4.3.1`** dependência (zero imports)

### Alterado
- 🔁 **Stack reduzida**: 16 → 7 containers (~50% RAM, de 3.4 GB → 1.7 GB)
- 🔁 **Repo size**: 1.8 GB → 663 MB
- 🔁 `requirements.txt` reorganizado em 9 secções com comentários
- 🔁 `django_celery_beat` adicionado a `INSTALLED_APPS` (DatabaseScheduler em vez de file)
- 🔁 `.gitignore` mais robusto (cobre `.env*`, `backups/`, `.claude/`, etc.)
- 🔁 `docker-compose.yml` (dev) sem passwords hardcoded — usa env vars

### Segurança
- 🛡️ User `django` não-root no container production
- 🛡️ MySQL não exposto ao host por defeito
- 🛡️ Caddy adiciona security headers (HSTS, X-Frame-Options, X-Content-Type-Options)
- 🛡️ `.env` em `chmod 600`
- 🛡️ Removidos secrets reais (`EVOLUTION_API_KEY`, etc.) de ficheiros tracked

### Garantias
- ✅ Backup garantido em `backups/` (DB + media + checksums SHA-256)
- ✅ Git tag `pre-cleanup-20260502_000844` marca estado anterior
- ✅ Restore guide documentado (`backups/RESTORE_GUIDE.md`)

---

## [v0.x] — Pré-2026-05

Histórico anterior em commits. Principais marcos:

- Sistema de Pré-Faturas (PFs) com bónus domingo/feriado, ajustes, indicações
- Empresas Parceiras (frotas) com pricing diferenciado em cascata
- Imports Cainiao (PARCEL_LIST, Operation, Driver Stat)
- Sync Delnext via Playwright
- Sync Paack API
- Geocodificação GeoAPI.pt
- Dashboard Analytics
- Conta a pagar / DRE / Fluxo Caixa
- Conciliação bancária

---

[v1.0.0-rc1]: https://github.com/kaled182/leguas/releases/tag/v1.0.0-rc1
