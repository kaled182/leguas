# Léguas Franzinas

Sistema de gestão logística para operadores de última-milha em Portugal. Gere motoristas, entregas, pré-faturas, frotas parceiras e integra-se com Cainiao, Delnext e Paack.

[![Production Ready](https://img.shields.io/badge/production-ready-success)](production/DEPLOYMENT.md)
[![Docker](https://img.shields.io/badge/docker-compose%20v2-blue)](production/docker-compose.yml)
[![License](https://img.shields.io/badge/license-Proprietary-red)](LICENSE)

---

## ⚡ Quick Start

### Produção (recomendado)

```bash
git clone https://github.com/kaled182/leguas.git
cd leguas/production
chmod +x install.sh
./install.sh
```

Wizard interactivo: pergunta domínio, admin user/pass — gera secrets automáticos, sobe stack, mostra URL final.

📖 [**Guia completo de deploy →**](production/DEPLOYMENT.md)

### Desenvolvimento

```bash
git clone https://github.com/kaled182/leguas.git
cd leguas
cp .env.docker.example .env.docker  # editar
docker compose -f deploy/dev/docker-compose.yml up -d
```

App em `http://localhost:8000`.

---

## 🔗 URLs principais

> Substitui `<host>` por `http://localhost` (dev) ou pelo teu domínio em produção.

### Públicas (sem login)
| URL | Descrição |
|---|---|
| `<host>/driversapp/cadastro/` | **Auto-cadastro motorista** (formulário simples) |
| `<host>/driversapp/cadastro-completo/` | Auto-cadastro completo (com docs e veículos) |
| `<host>/auth/driver/` | **Login motorista** (DriverAccess) |
| `<host>/auth/login/` | Login administrador |

### Portal do motorista (autenticado)
| URL | Descrição |
|---|---|
| `<host>/driversapp/portal/<id>/` | Visão geral do motorista (KPIs, heatmap, top CP4) |
| `<host>/driversapp/portal/<id>/relatorios/` | Relatórios mensais e anuais |
| `<host>/driversapp/portal/<id>/faturas/` | Faturas + anexar fatura-recibo |
| `<host>/driversapp/portal/<id>/perfil/` | Perfil + pedidos de alteração |

### Admin / Operação
| URL | Descrição |
|---|---|
| `<host>/` | **Dashboard principal** (Cainiao + alertas + KPIs) |
| `<host>/driversapp/admin/` | **Central de Motoristas** (lista moderna com filtros e KPIs) |
| `<host>/driversapp/admin/aprovar/` | Aprovar cadastros pendentes |
| `<host>/driversapp/admin/pedidos-alteracao/` | Aprovar pedidos de alteração de perfil |
| `<host>/driversapp/admin/reclamacoes/` | Reclamações de clientes |
| `<host>/converter/` | Conversor de listas Paack/Cainiao para XLSX |

### Financeiro
| URL | Descrição |
|---|---|
| `<host>/accounting/a-pagar/` | **A Pagar** — inbox unificado (motoristas, frotas, sócios, contas) |
| `<host>/settlements/invoices/` | A Receber (faturas dos parceiros) |
| `<host>/settlements/financial/` | Análise — Dashboard |
| `<host>/accounting/dre/` | Análise — DRE |
| `<host>/accounting/fluxo-caixa/` | Análise — Fluxo de caixa |
| `<host>/accounting/break-even/` | Análise — Break-even |
| `<host>/accounting/extractos/` | Análise — Conciliação bancária |
| `<host>/settlements/adiantamentos/` | Conta-corrente motoristas |
| `<host>/settlements/socios/` | Sócios & reembolsos |

### Sistema
| URL | Descrição |
|---|---|
| `<host>/system/` | **Configurações** (Empresa, Mapas, Comunicações, Backup) |
| `<host>/system/atualizacao/` | **Atualização** — changelog, sugestões, auto-update GitHub |
| `<host>/system/whatsapp/` | WhatsApp dashboard (QR, sessões, envio de teste) |
| `<host>/system/users/` | Gestão de utilizadores (superuser only) |
| `<host>/admin/` | Django Admin (low-level) |

---

## ✨ Funcionalidades principais

### Gestão operacional
- 👥 **Motoristas** — cadastro, aprovação, documentos, veículos, fotos perfil
- 🚚 **Frotas parceiras** — empresas subcontratantes com pricing diferenciado
- 📦 **Pacotes** — importação de planilhas Cainiao (PARCEL_LIST), forecast, planning
- 🗺️ **Geocodificação** — endereços via GeoAPI.pt + cache local
- 📊 **Dashboard analytics** — performance motoristas, métricas diárias, alertas

### Financeiro
- 💰 **Pré-Faturas (PFs)** — geração mensal por motorista com bónus domingo/feriado, ajustes, indicações
- 🏢 **Fleet Invoices** — pré-fatura agregada por frota com detalhe por motorista
- 💸 **Conta-Corrente Motoristas** — adiantamentos, combustível, lançamentos pendentes
- 🤝 **Reembolsos a Sócios** — quando sócio adianta dinheiro do bolso
- 📈 **DRE + Fluxo de Caixa + Break-even** — gestão contábil completa
- 🏦 **Conciliação bancária** — import extratos, matching automático

### Integrações
- 📱 **WhatsApp** (WPPConnect) — relatórios automáticos, lembretes pagamentos
- 🚛 **Cainiao** — import Excel + sincronização API
- 📦 **Delnext** — sync diário via Playwright scraping
- 📮 **Paack** — sync API diário (legacy, descontinuação planeada)
- ☁️ **Backup** — Google Drive ou FTP

### Tarefas agendadas (Celery Beat)
- 06:00 — Sync Delnext
- 06:30 — Auto-emissão Fleet Invoices
- 07:00 — Sync todos parceiros
- 09:00 — Lembretes WhatsApp contas vencidas
- 18:00 — Snapshot Not-Arrived + relatório semanal (sex)
- 19:00 — Alerta break-even
- 03:00 (seg) — Cleanup dados antigos

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│  Caddy (reverse proxy, SSL automático Let's Encrypt)         │
│         ↓                                                     │
│  Django (gunicorn, multi-worker)                             │
│         ↓                                                     │
│  MySQL 8.0  +  Redis 7  +  Celery (worker + beat)            │
│                                                               │
│  WPPConnect (WhatsApp, container interno)                    │
└─────────────────────────────────────────────────────────────┘
```

**Stack production: 7 containers, ~1.7 GB RAM, suporta VPS 4 GB.**

📖 [Arquitectura detalhada →](production/DEPLOYMENT.md#12-stack-final--referência-rápida)

---

## 📁 Estrutura do projeto

```
leguas/
├── production/                  ← Deploy production (Docker + Caddy)
│   ├── Dockerfile               (multi-stage)
│   ├── docker-compose.yml       (7 serviços)
│   ├── Caddyfile                (SSL automático)
│   ├── install.sh               (wizard primeira instalação)
│   ├── update.sh                (update sem perder dados)
│   ├── backup.sh                (DB + media + Google Drive)
│   └── DEPLOYMENT.md            (guia completo)
│
├── my_project/                  ← Settings Django, urls, ASGI/WSGI
│
├── customauth/                  ← Autenticação custom
├── core/                        ← Partners (Cainiao, Delnext, Paack)
├── drivers_app/                 ← Motoristas + Empresas Parceiras
├── settlements/                 ← PFs, Fleet Invoices, Cash Entries
├── accounting/                  ← Contas a pagar, DRE, Fluxo Caixa
├── analytics/                   ← Dashboards de performance
├── orders_manager/              ← Gestão de pedidos genérica
├── fleet_management/            ← Veículos + manutenções
├── pricing/                     ← Tarifas + zonas postais
├── route_allocation/            ← Turnos + rotas
├── system_config/               ← Configurações + WhatsApp + Backup
├── converter/                   ← Conversão XLSX
├── management/                  ← Ferramentas (gerador QR, etc.)
│
├── ordersmanager_paack/         ← Legacy Paack (descontinuação)
├── paack_dashboard/             ← Legacy dashboard Paack
├── send_paack_reports/          ← Legacy relatórios
├── manualorders_paack/          ← Legacy correção manual
│
├── deploy/dev/                  ← Dev environment (Docker)
│   ├── Dockerfile, docker-compose.yml
│   ├── docker-entrypoint.sh, init-db.sql
│   └── wppconnect/              (Dockerfile, config.json, patch.js)
│
├── examples/                    ← CSVs de exemplo (tarifas, zonas postais)
│
├── docs/
│   ├── ARCHITECTURE.md, DOCKER.md, ROADMAP.md
│   ├── integrations/   (DELNEXT, PAACK, WHATSAPP, OMNICHANNEL, TYPEBOT)
│   ├── runbook/        (TROUBLESHOOTING, CRON_JOBS, INSTALL_CHECKLIST)
│   └── archive/        (snapshots históricos de evolução)
│
├── requirements.txt             ← Python deps
├── .env.docker.example          ← Template dev
└── README.md
```

---

## 🔧 Stack técnica

| Componente | Tech |
|---|---|
| **Backend** | Django 4.2 + DRF |
| **Database** | MySQL 8.0 |
| **Cache + Queue** | Redis 7 |
| **Async tasks** | Celery 5.4 + Beat (DatabaseScheduler) |
| **Frontend** | Tailwind CSS + Alpine.js (vanilla, sem framework JS) |
| **Templating** | Django templates + Jinja2 |
| **Web server** | Gunicorn |
| **Reverse proxy** | Caddy 2 (SSL automático) |
| **Scraping** | Playwright (Chromium) |
| **Reports** | ReportLab (PDFs) + openpyxl (XLSX) |
| **Geocoding** | GeoAPI.pt + Folium (mapas) |
| **WhatsApp** | WPPConnect Server |
| **Encriptação** | Fernet (cryptography) |
| **Backup** | Google API Client (Drive) + pyzipper (FTP) |

---

## 🚀 Comandos úteis

### Em produção (`production/`)

```bash
docker compose ps                       # Status containers
docker compose logs -f web              # Logs Django
docker compose restart web              # Reiniciar Django
./backup.sh                             # Backup on-demand
./backup.sh --upload                    # Backup + Google Drive
./update.sh                             # Update sem perder dados
```

### Em desenvolvimento

```bash
docker compose exec web python manage.py shell
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py test
```

### Health check

```bash
curl http://localhost/health/
# {"status": "ok", "checks": {"db": "ok", "cache": "ok"}}
```

---

## 📚 Documentação

- 📦 [`production/DEPLOYMENT.md`](production/DEPLOYMENT.md) — guia completo de deploy
- 📖 [`production/README.md`](production/README.md) — overview production
- 📝 [`CHANGELOG.md`](CHANGELOG.md) — versões e mudanças
- ⚖️ [`LICENSE`](LICENSE) — termos de uso

---

## 🤝 Suporte

- **Issues**: <https://github.com/kaled182/leguas/issues>
- **Healthcheck**: `curl http://localhost/health/`
- **Logs**: `docker compose logs --tail 100`

---

## 📜 Licença

Proprietary — Léguas Franzinas Unipessoal Lda. Todos os direitos reservados.

Ver [`LICENSE`](LICENSE).
