# Léguas Franzinas — Production Deployment

Stack Docker Compose **plug-in-play** para correr em qualquer VPS Linux.

```
┌──────────────────────────────────────────────────────┐
│  Caddy (reverse proxy + SSL automático Let's Encrypt) │
│         ↓                                              │
│  Django (gunicorn) ←→ MySQL                           │
│      ↓                                                 │
│  Celery worker + beat (tarefas agendadas)             │
│      ↓                                                 │
│  Redis (cache + queue)                                │
│      ↓                                                 │
│  WPPConnect (WhatsApp)                                │
└──────────────────────────────────────────────────────┘
```

**7 containers, ~1.7 GB RAM, suporta 4 GB RAM mínimo (~50 motoristas + 5K pacotes/mês).**

## ⚡ Quick start (instalação automática)

```bash
git clone https://github.com/.../leguasfranzinas.git
cd leguasfranzinas/production
chmod +x install.sh
./install.sh
```

O wizard pergunta tudo (domínio, admin, etc.), gera secrets seguros automaticamente, e sobe a stack.

## 📋 Pré-requisitos

- **Linux** (Ubuntu 22.04+ / Debian 12 / CentOS Stream 9 / equivalente)
- **Docker** 24+ e **Docker Compose v2** (`docker compose`)
- **4 GB RAM**, **20 GB disco** mínimo, **2 vCPU**
- **Portas** 80 e 443 abertas (firewall + DNS)
- (Opcional) **Domínio** apontado ao IP do servidor — para SSL automático

## 🔧 Configuração manual (alternativa ao install.sh)

```bash
cp .env.example .env
nano .env                    # editar todas as variáveis [OBRIGATÓRIO]
docker compose up -d --build
docker compose logs -f web
```

## 🌐 Domínio + SSL

**Com domínio** (recomendado, SSL automático):
```dotenv
DOMAIN=app.exemplo.com
LETSENCRYPT_EMAIL=admin@exemplo.com
```
Caddy emite certificado Let's Encrypt sozinho.

**Sem domínio** (HTTP-only no IP):
```dotenv
DOMAIN=:80
```

## 💾 Backup

**Manual:**
```bash
./backup.sh
```

**Automático (cron diário 03h):**
```bash
crontab -e
# Adicionar linha:
0 3 * * * cd /caminho/para/production && ./backup.sh >> backup.log 2>&1
```

**Upload Google Drive** (após configurar em /system/storage/):
```bash
./backup.sh --upload
```

Retém últimos 30 backups (configurável via `BACKUP_RETENTION_DAYS`).

## 🚀 Operação diária

| Comando | Função |
|---|---|
| `docker compose ps` | Status dos serviços |
| `docker compose logs -f web` | Logs Django em tempo real |
| `docker compose logs -f celery_worker` | Logs Celery worker |
| `docker compose restart web` | Reiniciar Django |
| `docker compose down` | Parar tudo (sem apagar dados) |
| `docker compose up -d` | Subir tudo |
| `./update.sh` | Atualizar para versão mais recente |
| `./backup.sh` | Backup on-demand |

## 🔒 Segurança

- **Não exponhas o porto 3306** (MySQL) ao público — só Docker network
- **Mantém o `.env` em `chmod 600`** (já feito pelo install.sh)
- **Firewall**: só permite 80/443 públicos
- **Backup off-site**: Google Drive (configurar em /system/storage/)

## 🆘 Troubleshooting

**App não arranca:**
```bash
docker compose logs web | tail -50
```

**BD inacessível:**
```bash
docker compose exec db mysql -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME}
```

**Healthcheck status:**
```bash
curl http://localhost/health/
# Resposta esperada: {"status": "ok", "checks": {"db": "ok", "cache": "ok"}}
```

**Reset password admin:**
```bash
docker compose exec web python manage.py changepassword <username>
```

**Restaurar backup:**
Ver `backups/RESTORE_GUIDE.md`.

## 📁 Estrutura

```
production/
├── Dockerfile                   # Multi-stage
├── docker-compose.yml          # Stack production
├── Caddyfile                   # Reverse proxy + SSL
├── gunicorn_config.py          # Tuning workers
├── entrypoint.sh               # Init container (migrate + collectstatic)
├── .env.example                # Template config
├── .env                        # Config real (gerado por install.sh)
├── install.sh                  # Wizard primeira instalação
├── update.sh                   # Update sem perder dados
├── backup.sh                   # Backup DB + media
└── backups/                    # Backups locais (gerados)
```
