# 🚀 Guia de Deployment em Produção - Celery

Este guia explica como configurar o Celery em produção usando Supervisor ou systemd.

## 📋 Pré-requisitos

- Servidor Linux (Ubuntu/Debian recomendado)
- Python 3.8+
- Redis ou RabbitMQ instalado
- MySQL/PostgreSQL instalado
- Nginx + Gunicorn para Django
- Supervisor ou systemd

## 🔧 Opção 1: Supervisor (Recomendado)

### 1. Instalar Supervisor

```bash
sudo apt-get update
sudo apt-get install supervisor
```

### 2. Criar Diretórios de Log

```bash
sudo mkdir -p /var/log/celery
sudo mkdir -p /var/run/celery
sudo chown -R www-data:www-data /var/log/celery
sudo chown -R www-data:www-data /var/run/celery
```

### 3. Configurar Supervisor

**Editar arquivo de configuração:**

```bash
sudo nano /etc/supervisor/conf.d/leguas-celery.conf
```

**Copiar conteúdo de** `deployment/supervisor/celery.conf` **e adaptar:**

```ini
[program:leguas-celery-worker]
command=/home/user/venv/bin/celery -A my_project worker -l info
directory=/home/user/app.leguasfranzinas.pt/app.leguasfranzinas.pt
user=www-data
numprocs=1
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker_error.log
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
killasgroup=true
priority=998

[program:leguas-celery-beat]
command=/home/user/venv/bin/celery -A my_project beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
directory=/home/user/app.leguasfranzinas.pt/app.leguasfranzinas.pt
user=www-data
numprocs=1
stdout_logfile=/var/log/celery/beat.log
stderr_logfile=/var/log/celery/beat_error.log
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
killasgroup=true
priority=999

[group:leguas-celery]
programs=leguas-celery-worker,leguas-celery-beat
priority=999
```

**Substituir:**
- `/home/user/venv` → caminho correto do seu virtualenv
- `/home/user/app.leguasfranzinas.pt/app.leguasfranzinas.pt` → caminho do projeto
- `www-data` → seu usuário (se diferente)

### 4. Recarregar Supervisor

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status
```

### 5. Comandos Úteis do Supervisor

```bash
# Ver status
sudo supervisorctl status

# Iniciar grupo Celery
sudo supervisorctl start leguas-celery:*

# Parar grupo Celery
sudo supervisorctl stop leguas-celery:*

# Reiniciar grupo Celery
sudo supervisorctl restart leguas-celery:*

# Ver logs em tempo real
sudo tail -f /var/log/celery/worker.log
sudo tail -f /var/log/celery/beat.log

# Reiniciar supervisor
sudo systemctl restart supervisor
```

## 🔧 Opção 2: systemd

### 1. Criar Diretórios

```bash
sudo mkdir -p /var/log/celery
sudo mkdir -p /var/run/celery
sudo chown -R www-data:www-data /var/log/celery
sudo chown -R www-data:www-data /var/run/celery
```

### 2. Criar Service Files

**Celery Worker:**

```bash
sudo nano /etc/systemd/system/celery-worker.service
```

Copiar conteúdo de `deployment/systemd/celery-worker.service` e adaptar caminhos.

**Celery Beat:**

```bash
sudo nano /etc/systemd/system/celery-beat.service
```

Copiar conteúdo de `deployment/systemd/celery-beat.service` e adaptar caminhos.

### 3. Habilitar e Iniciar Serviços

```bash
# Recarregar systemd
sudo systemctl daemon-reload

# Habilitar para iniciar no boot
sudo systemctl enable celery-worker.service
sudo systemctl enable celery-beat.service

# Iniciar serviços
sudo systemctl start celery-worker.service
sudo systemctl start celery-beat.service

# Verificar status
sudo systemctl status celery-worker.service
sudo systemctl status celery-beat.service
```

### 4. Comandos Úteis do systemd

```bash
# Ver status
sudo systemctl status celery-worker
sudo systemctl status celery-beat

# Iniciar
sudo systemctl start celery-worker
sudo systemctl start celery-beat

# Parar
sudo systemctl stop celery-worker
sudo systemctl stop celery-beat

# Reiniciar
sudo systemctl restart celery-worker
sudo systemctl restart celery-beat

# Ver logs
sudo journalctl -u celery-worker -f
sudo journalctl -u celery-beat -f

# Ver últimas 100 linhas
sudo journalctl -u celery-worker -n 100
```

## 📊 Configurar Flower (Monitoramento)

Flower é uma web UI para monitorar o Celery em produção.

### 1. Instalar Flower

```bash
source /path/to/venv/bin/activate
pip install flower
```

### 2. Criar Serviço Supervisor

```bash
sudo nano /etc/supervisor/conf.d/leguas-flower.conf
```

```ini
[program:leguas-flower]
command=/home/user/venv/bin/celery -A my_project flower --port=5555 --basic_auth=admin:senha_segura_aqui
directory=/home/user/app.leguasfranzinas.pt/app.leguasfranzinas.pt
user=www-data
numprocs=1
stdout_logfile=/var/log/celery/flower.log
stderr_logfile=/var/log/celery/flower_error.log
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
```

### 3. Configurar Nginx Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/leguas.conf
```

Adicionar location para Flower:

```nginx
location /flower/ {
    proxy_pass http://localhost:5555/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Autenticação adicional (opcional)
    # auth_basic "Área Restrita";
    # auth_basic_user_file /etc/nginx/.htpasswd;
}
```

Reiniciar Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Acessar: https://seu-dominio.com/flower/

## 🔒 Segurança em Produção

### 1. Variáveis de Ambiente

Criar arquivo `.env` no servidor:

```bash
nano /home/user/app.leguasfranzinas.pt/app.leguasfranzinas.pt/.env
```

```env
SECRET_KEY=sua-secret-key-segura-aqui
DEBUG=False
ALLOWED_HOSTS=seu-dominio.com,www.seu-dominio.com
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
DATABASE_URL=mysql://user:password@localhost:3306/leguas_db
```

**Importante:** Nunca commitar `.env` no Git!

### 2. Permissões de Arquivos

```bash
# Projeto deve pertencer ao usuário web
sudo chown -R www-data:www-data /home/user/app.leguasfranzinas.pt

# Logs devem ser writable
sudo chmod -R 755 /var/log/celery

# .env deve ser protegido
chmod 600 /home/user/app.leguasfranzinas.pt/app.leguasfranzinas.pt/.env
```

### 3. Firewall

```bash
# Permitir apenas portas necessárias
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable

# Redis deve estar apenas em localhost (NÃO expor publicamente)
# Verificar em /etc/redis/redis.conf:
# bind 127.0.0.1
```

## 📝 Logs e Monitoramento

### 1. Rotação de Logs

Criar arquivo de configuração logrotate:

```bash
sudo nano /etc/logrotate.d/celery
```

```
/var/log/celery/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 www-data www-data
    sharedscripts
    postrotate
        /usr/bin/supervisorctl restart leguas-celery:* > /dev/null
    endscript
}
```

### 2. Monitoramento de Performance

**Instalar Sentry (opcional mas recomendado):**

```bash
pip install sentry-sdk
```

Em `settings.py`:

```python
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="seu-dsn-sentry-aqui",
    integrations=[
        DjangoIntegration(),
        CeleryIntegration(),
    ],
    environment="production",
    traces_sample_rate=0.1,  # 10% das transações
)
```

### 3. Alertas por Email

Em `settings.py`:

```python
# Email para admins
ADMINS = [
    ('Admin Name', 'admin@seu-dominio.com'),
]

# Celery enviará emails em caso de erro
CELERY_SEND_TASK_ERROR_EMAILS = True

# Configurar SMTP
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'seu-email@gmail.com'
EMAIL_HOST_PASSWORD = 'senha-app-gmail'
DEFAULT_FROM_EMAIL = 'noreply@seu-dominio.com'
```

## 🔄 Atualizações e Manutenção

### Deploy de Nova Versão

```bash
# 1. Fazer backup do banco de dados
mysqldump -u user -p leguas_db > backup_$(date +%Y%m%d).sql

# 2. Atualizar código
cd /home/user/app.leguasfranzinas.pt
git pull origin main

# 3. Ativar virtualenv
source venv/bin/activate

# 4. Instalar dependências
pip install -r requirements.txt

# 5. Aplicar migrações
cd app.leguasfranzinas.pt
python manage.py migrate

# 6. Coletar arquivos estáticos
python manage.py collectstatic --noinput

# 7. Reiniciar serviços
sudo supervisorctl restart leguas-celery:*
sudo systemctl restart gunicorn
```

### Limpeza de Tasks Antigas

Criar tarefa agendada para limpar tasks antigas:

```python
# Em core/tasks.py
@shared_task
def cleanup_celery_results():
    """Remove resultados de tasks com mais de 30 dias"""
    from django_celery_results.models import TaskResult
    from datetime import timedelta
    from django.utils import timezone
    
    cutoff = timezone.now() - timedelta(days=30)
    deleted = TaskResult.objects.filter(date_done__lt=cutoff).delete()
    return f"Removidos {deleted[0]} resultados antigos"
```

Agendar em `celery.py`:

```python
app.conf.beat_schedule = {
    # ... outras tasks ...
    'cleanup-celery-results': {
        'task': 'core.tasks.cleanup_celery_results',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Domingo 2 AM
    },
}
```

## 🐛 Troubleshooting

### Workers não iniciam

```bash
# Verificar logs
sudo tail -f /var/log/celery/worker_error.log

# Verificar se Redis está rodando
redis-cli ping

# Verificar permissões
ls -la /var/log/celery
ls -la /var/run/celery

# Testar comando manualmente
sudo su - www-data -s /bin/bash
cd /home/user/app.leguasfranzinas.pt/app.leguasfranzinas.pt
source venv/bin/activate
celery -A my_project worker -l debug
```

### Tasks não executam

```bash
# Verificar se Beat está rodando
sudo supervisorctl status leguas-celery-beat

# Ver tasks agendadas
celery -A my_project inspect scheduled

# Ver tasks ativas
celery -A my_project inspect active

# Ver workers registrados
celery -A my_project inspect stats
```

### High Memory Usage

```bash
# Adicionar limite de memória no Supervisor
# Em /etc/supervisor/conf.d/leguas-celery.conf:
[program:leguas-celery-worker]
# ... outras configs ...
environment=MALLOC_ARENA_MAX=2

# Ou limitar tasks por worker
command=/home/user/venv/bin/celery -A my_project worker -l info --max-tasks-per-child=1000
```

## ✅ Checklist de Produção

- [ ] Redis instalado e rodando
- [ ] Supervisor/systemd configurado
- [ ] Workers iniciando automaticamente no boot
- [ ] Beat iniciando automaticamente no boot
- [ ] Logs sendo escritos corretamente
- [ ] Logrotate configurado
- [ ] Flower protegido com autenticação
- [ ] Variáveis de ambiente seguras (.env)
- [ ] Backups automáticos do banco
- [ ] Monitoramento ativo (Sentry/Flower)
- [ ] Alertas por email configurados
- [ ] Firewall configurado
- [ ] SSL/TLS habilitado (HTTPS)
- [ ] Testado deploy de nova versão
- [ ] Documentação atualizada

## 📞 Suporte

Em caso de problemas:

1. Verificar logs: `/var/log/celery/`
2. Verificar status: `sudo supervisorctl status`
3. Testar comando manual
4. Consultar documentação oficial do Celery

## 🔗 Links Úteis

- [Celery Documentation](https://docs.celeryq.dev/)
- [Supervisor Documentation](http://supervisord.org/)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Redis Documentation](https://redis.io/docs/)
