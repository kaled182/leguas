# 📦 Léguas Franzinas — Deployment Guide

Guia completo para correr o sistema em produção (VM dedicada Linux).

> **Quick start:** `cd production && ./install.sh` — wizard automático.

---

## 1. Pré-requisitos do servidor

| | Mínimo | Recomendado |
|---|---|---|
| **OS** | Ubuntu 22.04 / Debian 12 / CentOS Stream 9 | Ubuntu 24.04 LTS |
| **CPU** | 2 vCPU | 4 vCPU |
| **RAM** | 4 GB | 8 GB |
| **Disco** | 20 GB | 50 GB SSD |
| **Rede** | Portas 80, 443 abertas | Domínio com DNS aponta ao IP |
| **Docker** | 24+ | 27+ |
| **Docker Compose** | v2 (`docker compose`) | v2 |

### Instalar Docker (se não tiver)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# logout/login
```

---

## 2. Instalação automática (recomendada)

```bash
# Clonar/extrair projecto
git clone <repo-url> leguas
cd leguas/production

# Wizard interactivo
chmod +x install.sh
./install.sh
```

O wizard pede:
- Domínio (vazio → HTTP-only no IP)
- Email Let's Encrypt
- Username + password admin

E gera automaticamente:
- `SECRET_KEY` (50 chars random)
- `FERNET_KEY` (Fernet key encriptação)
- `DB_PASSWORD` + `DB_ROOT_PASSWORD` (24 chars hex)
- `WPPCONNECT_SECRET` (64 chars hex)
- `BACKUP_ZIP_PASSWORD`

Faz build da imagem (~5 min primeira vez), sobe stack, e mostra a URL final.

---

## 3. Instalação manual

```bash
cd production
cp .env.example .env
nano .env                       # preencher [OBRIGATÓRIO]s
docker compose up -d --build
docker compose logs -f web      # validar arranque
```

---

## 4. Domínio e SSL

### Modo HTTP-only (sem SSL)

Para VPN interna, IP do servidor sem domínio, ou desenvolvimento:

```dotenv
DOMAIN=:80
LETSENCRYPT_EMAIL=internal
```

Acesso: `http://IP-DO-SERVIDOR/`

### Modo HTTPS automático (Let's Encrypt)

1. Apontar DNS A do domínio para IP do servidor
2. Confirmar portas 80 e 443 abertas
3. Editar `.env`:
   ```dotenv
   DOMAIN=app.exemplo.com
   LETSENCRYPT_EMAIL=admin@exemplo.com
   ```
4. `docker compose up -d caddy`
5. Caddy emite cert automaticamente (~30s)

Acesso: `https://app.exemplo.com/`

---

## 5. Configurar integrações externas

Após primeiro login (`admin@.../senha`):

### WhatsApp WPPConnect
1. `/system/whatsapp/` → "Iniciar sessão" → escanear QR
2. Sessão persiste no volume `wppconnect_tokens`

### Cainiao
1. `/system/` → secção "Cainiao"
2. Importar planilhas via UI

### Delnext
1. Editar `.env`: `DELNEXT_ADMIN_NAME=`, `DELNEXT_ADMIN_PASS=`
2. `docker compose restart celery_worker celery_beat`
3. Sync diária às 06h via Celery Beat

### Google Drive (backup)
1. `/system/storage/` → "Activar Google Drive"
2. Inserir Service Account JSON ou OAuth credentials
3. Backups com `--upload` enviam automaticamente

---

## 6. Operação diária

| Comando | Função |
|---|---|
| `docker compose ps` | Status |
| `docker compose logs -f web` | Logs Django |
| `docker compose logs -f celery_worker` | Logs Celery |
| `docker compose restart web` | Reiniciar Django |
| `docker compose down` | Parar tudo (mantém volumes) |
| `docker compose up -d` | Subir tudo |
| `./update.sh` | Update sem perder dados |
| `./backup.sh` | Backup on-demand |
| `./backup.sh --upload` | Backup + upload Google Drive |

---

## 7. Backup automático

### Cron diário (recomendado)

```bash
crontab -e
# Adicionar linha:
0 3 * * * cd /caminho/para/production && ./backup.sh --upload >> backup.log 2>&1
```

### Retenção
- Default: 30 dias (configurável em `.env`: `BACKUP_RETENTION_DAYS=30`)
- Cada backup ~12 MB (db + media)
- Cleanup automático: ficheiros mais antigos que retenção são apagados

### Recuperação

Ver `backups/RESTORE_GUIDE.md` (gerado pelo backup script). Contém comandos exactos para:
- Restaurar BD (zcat + mysql)
- Restaurar volume media (tar)
- Voltar a versão anterior do código (git checkout tag)

---

## 8. Atualização

```bash
cd production
./update.sh
```

Faz:
1. Backup pré-update (segurança)
2. `git pull` (se for git repo)
3. Rebuild imagem
4. Aplica migrations
5. Reinicia serviços
6. Aguarda `/health/` responder OK

Para forçar sem backup: `./update.sh --no-backup`

---

## 9. Troubleshooting

### App não arranca

```bash
docker compose logs web | tail -50
```

Causas comuns:
- DB ainda a iniciar (esperar healthcheck `db`)
- `.env` mal preenchido (`DEBUG=True` em produção causa warnings)
- Permissão volume static (apagar volume e refazer collectstatic)

### BD inacessível

```bash
docker compose exec db mysql -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e "SELECT 1;"
```

### Healthcheck falha

```bash
curl http://localhost/health/
# Esperado: {"status": "ok", "checks": {"db": "ok", "cache": "ok"}}
```

Se `db` der erro: container db não está healthy.
Se `cache` der erro: Redis não acessível.

### Reset password admin

```bash
docker compose exec web python manage.py changepassword admin
```

### Recriar superuser

```bash
docker compose exec web python manage.py createsuperuser
```

### Estatística rápida do sistema

```bash
docker compose exec web python manage.py shell -c "
from settlements.models import CainiaoOperationTask, DriverPreInvoice
from drivers_app.models import DriverProfile
print(f'Tasks: {CainiaoOperationTask.objects.count()}')
print(f'PFs: {DriverPreInvoice.objects.count()}')
print(f'Drivers: {DriverProfile.objects.count()}')
"
```

### Logs estruturados

Logs Django em `docker compose logs web`:
- `INFO`: requests normais
- `WARNING`: problemas não-fatais
- `ERROR`: erros aplicacionais

Logs Celery em `docker compose logs celery_worker`:
- Tasks executadas, retries, errors

---

## 10. Migrar para outro servidor

### No servidor antigo

```bash
cd production
./backup.sh
# Copiar pasta backups/ para servidor novo
scp -r backups/ user@novo-servidor:~/leguas-backup/
```

### No servidor novo

```bash
git clone <repo> leguas
cd leguas/production
cp ~/leguas-backup/.env .env  # ou ./install.sh para gerar novo
docker compose up -d
docker compose exec db mysql -u root -p${DB_ROOT_PASSWORD} -e "DROP DATABASE IF EXISTS ${DB_NAME}; CREATE DATABASE ${DB_NAME} CHARACTER SET utf8mb4;"
zcat ~/leguas-backup/db_*.sql.gz | docker compose exec -T db mysql -u root -p${DB_ROOT_PASSWORD} ${DB_NAME}
docker run --rm -v appleguasfranzinaspt_media_volume:/dest -v ~/leguas-backup:/source:ro alpine sh -c "cd /dest && tar xzf /source/media_*.tar.gz"
docker compose restart
```

---

## 11. Segurança

### Boas práticas activas

- ✅ Container Django corre como user `django` (não-root)
- ✅ `.env` em `chmod 600`
- ✅ MySQL não exposto ao host (só Docker network)
- ✅ Caddy adiciona security headers (HSTS, X-Frame-Options, etc.)
- ✅ Healthcheck em todos os containers
- ✅ Restart policies (`unless-stopped`)

### Recomendações adicionais

- Ativar UFW/firewalld no servidor: só portas 80, 443 e 22 (SSH)
- Backup off-site (Google Drive automatizado em `.env`)
- Mudar password admin no primeiro login (UI)
- Rotação de logs (Docker tem `--log-opt max-size=10m max-file=3`)

---

## 12. Stack final — referência rápida

```
Caddy (80/443)                     ← entrada pública
   ↓
Django (gunicorn 9 workers)        ← /health/ /admin/ /...
   ↓
MySQL 8.0 + Redis 7
   ↑
Celery (worker + beat)             ← tarefas agendadas
   ↑
WPPConnect (21465 interno)         ← WhatsApp
```

**RAM total: ~1.7 GB** (vs 3.4 GB antes da limpeza)
**Containers: 7** (vs 16 antes)

---

## 13. Suporte

- Logs locais: `docker compose logs --tail 100`
- Status: `docker compose ps`
- Healthcheck: `curl http://localhost/health/`
- Restore: `backups/RESTORE_GUIDE.md`
