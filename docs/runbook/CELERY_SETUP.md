# Configuração e Uso do Celery

Este documento explica como configurar e usar o Celery para sincronizações automáticas no projeto Léguas Franzinas.

## 📋 O que é Celery?

Celery é um sistema de processamento assíncrono distribuído que permite:
- Executar tarefas em background (não bloquear requisições web)
- Agendar tarefas periódicas (como um cron melhorado)
- Distribuir processamento entre múltiplos workers
- Retry automático em caso de falhas

## 🔧 Instalação e Configuração

### 1. Instalar Dependências

```bash
# Ativar ambiente virtual
.venv\Scripts\activate

# Instalar Celery e Redis (broker recomendado)
pip install celery redis django-celery-beat django-celery-results

# Atualizar requirements.txt
pip freeze > requirements.txt
```

### 2. Instalar Redis (Broker de Mensagens)

**Windows:**
```powershell
# Opção 1: Usar WSL2
wsl --install
wsl
sudo apt-get update
sudo apt-get install redis-server
redis-server

# Opção 2: Docker (recomendado)
docker run -d -p 6379:6379 redis:alpine

# Opção 3: Memurai (Redis para Windows)
# Baixar de: https://www.memurai.com/
```

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# Mac
brew install redis
brew services start redis
```

### 3. Verificar Redis

```bash
# Testar conexão
redis-cli ping
# Deve retornar: PONG
```

### 4. Aplicar Migrações (se usar django-celery-beat)

```bash
python manage.py migrate
```

## 🚀 Executar Celery

### Modo Desenvolvimento (3 terminais)

**Terminal 1 - Django:**
```bash
python manage.py runserver
```

**Terminal 2 - Celery Worker:**
```bash
# Windows
celery -A my_project worker -l info --pool=solo

# Linux/Mac
celery -A my_project worker -l info
```

**Terminal 3 - Celery Beat (agendador):**
```bash
celery -A my_project beat -l info
```

### Modo Produção (melhor opção)

**Usando Supervisor ou systemd:**

Criar `/etc/supervisor/conf.d/celery.conf`:
```ini
[program:celery-worker]
command=/path/to/venv/bin/celery -A my_project worker -l info
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker_error.log

[program:celery-beat]
command=/path/to/venv/bin/celery -A my_project beat -l info
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
stdout_logfile=/var/log/celery/beat.log
stderr_logfile=/var/log/celery/beat_error.log
```

Recarregar:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status
```

## ⏰ Tarefas Agendadas

As seguintes tarefas estão configuradas em `my_project/celery.py`:

### 1. **sync-delnext-daily** 
- **Horário:** 6:00 AM (todos os dias)
- **Função:** Sincroniza pedidos Delnext do último dia útil
- **Task:** `core.sync_delnext_last_weekday`

### 2. **sync-all-partners-daily**
- **Horário:** 7:00 AM (todos os dias)
- **Função:** Sincroniza todos os parceiros ativos
- **Task:** `core.sync_all_active_integrations`

### 3. **cleanup-old-data-weekly**
- **Horário:** Segunda-feira às 3:00 AM
- **Função:** Limpa dados com mais de 90 dias
- **Task:** `core.cleanup_old_partner_data`

### 4. **send-weekly-report**
- **Horário:** Sexta-feira às 18:00 (6 PM)
- **Função:** Envia relatório semanal por email
- **Task:** `core.send_sync_report`

## 🎯 Executar Tarefas Manualmente

### Via Django Shell

```python
python manage.py shell

# Executar tarefa agora (síncrono - bloqueia)
from core.tasks import sync_delnext
result = sync_delnext(date='2026-02-27', zone='VianaCastelo')
print(result)

# Executar tarefa assíncrona (envia para Celery)
from core.tasks import sync_delnext
task = sync_delnext.delay(date='2026-02-27', zone='VianaCastelo')
print(f"Task ID: {task.id}")

# Verificar status da task
from celery.result import AsyncResult
task_result = AsyncResult(task.id)
print(f"Status: {task_result.status}")  # PENDING, SUCCESS, FAILURE
print(f"Result: {task_result.result}")  # Resultado quando concluída
```

### Via Management Command (CLI)

```bash
# Sincronizar Delnext agora
python manage.py shell -c "from core.tasks import sync_delnext; print(sync_delnext())"

# Testar Celery
python manage.py shell -c "from core.tasks import test_task; test_task.delay()"
```

## 🔍 Monitorar Tarefas

### Flower (Web UI para Celery)

```bash
# Instalar
pip install flower

# Executar
celery -A my_project flower

# Acessar: http://localhost:5555
```

**Recursos do Flower:**
- Ver tasks em execução, concluídas, falhadas
- Monitorar workers
- Ver estatísticas em tempo real
- Executar tasks manualmente

### Logs

```bash
# Ver logs do worker
tail -f /var/log/celery/worker.log

# Ver logs do beat
tail -f /var/log/celery/beat.log

# Filtrar erros
grep ERROR /var/log/celery/worker.log
```

## 🛠️ Tarefas Disponíveis

### 1. sync_delnext

Sincroniza pedidos Delnext de uma data específica.

```python
from core.tasks import sync_delnext

# Usar data específica
result = sync_delnext.delay(date='2026-02-27', zone='VianaCastelo')

# Usar configuração padrão (último dia útil)
result = sync_delnext.delay()
```

**Retorno:**
```python
{
    "success": True,
    "stats": {
        "total": 144,
        "created": 144,
        "updated": 0,
        "errors": 0,
        "zone": "VianaCastelo",
        "date": "2026-02-27"
    }
}
```

### 2. sync_delnext_last_weekday

Sincroniza usando o último dia útil automaticamente.

```python
from core.tasks import sync_delnext_last_weekday

result = sync_delnext_last_weekday.delay(zone='VianaCastelo')
```

**Lógica de dia útil:**
- Se hoje é **Segunda**: pega Sexta passada (-3 dias)
- Se hoje é **Sábado**: pega Sexta passada (-1 dia)
- Se hoje é **Domingo**: pega Sexta passada (-2 dias)
- Outros dias: pega dia anterior (-1 dia)

### 3. sync_all_active_integrations

Sincroniza todos os parceiros ativos.

```python
from core.tasks import sync_all_active_integrations

result = sync_all_active_integrations.delay()
```

**Retorno:**
```python
{
    "Delnext": {
        "success": True,
        "stats": {...}
    },
    "OutroParceiro": {
        "success": True,
        "stats": {...}
    }
}
```

### 4. cleanup_old_partner_data

Remove dados antigos.

```python
from core.tasks import cleanup_old_partner_data

# Manter 90 dias (padrão)
result = cleanup_old_partner_data.delay()

# Manter 30 dias
result = cleanup_old_partner_data.delay(days=30)
```

### 5. send_sync_report

Envia relatório por email.

```python
from core.tasks import send_sync_report

# Enviar para admin padrão
result = send_sync_report.delay()

# Enviar para email específico
result = send_sync_report.delay(email_to='seu@email.com')
```

### 6. test_task

Tarefa de teste para verificar se Celery está funcionando.

```python
from core.tasks import test_task

result = test_task.delay()
# Retorna: {"success": True, "message": "Celery está funcionando!", "timestamp": "..."}
```

## ⚙️ Configuração de Agendamento Personalizado

Editar `my_project/celery.py`:

```python
app.conf.beat_schedule = {
    'minha-tarefa-personalizada': {
        'task': 'core.tasks.sync_delnext',
        'schedule': crontab(hour=8, minute=30),  # 8:30 AM
        'kwargs': {
            'zone': 'VianaCastelo'
        },
        'options': {
            'expires': 3600,  # Expira após 1 hora
        }
    },
}
```

**Exemplos de Schedules:**

```python
# A cada 30 minutos
'schedule': crontab(minute='*/30')

# Toda Segunda às 9h
'schedule': crontab(hour=9, minute=0, day_of_week=1)

# Primeiro dia do mês às 0h
'schedule': crontab(hour=0, minute=0, day_of_month=1)

# A cada 5 minutos
'schedule': 300  # 300 segundos = 5 minutos

# Usando timedelta
from datetime import timedelta
'schedule': timedelta(hours=1)  # A cada 1 hora
```

## 🐛 Troubleshooting

### Erro: "Cannot connect to Redis"

```bash
# Verificar se Redis está rodando
redis-cli ping

# Iniciar Redis
# Windows (Docker)
docker start <container_id>

# Linux
sudo systemctl start redis
```

### Erro: "No module named 'celery'"

```bash
# Instalar no ambiente correto
.venv\Scripts\activate
pip install celery redis
```

### Tasks não executam

```bash
# Verificar worker está rodando
celery -A my_project inspect active

# Verificar beat está rodando
celery -A my_project inspect scheduled

# Reiniciar worker
# Ctrl+C no terminal do worker e executar novamente
```

### Tasks ficam em PENDING

- Worker não está rodando
- Broker (Redis) não está acessível
- Nome da task está incorreto

```bash
# Ver registered tasks
celery -A my_project inspect registered
```

### Erros de timeout em Playwright

```python
# Aumentar timeout em DelnextAdapter
page.wait_for_load_state("networkidle", timeout=60000)  # 60 segundos
```

## 📊 Monitoramento em Produção

### Alertas por Email

Configurar em `settings.py`:

```python
# Email para admins
ADMINS = [
    ('Seu Nome', 'seu@email.com'),
]

# Celery enviará emails em caso de erro
CELERY_SEND_TASK_ERROR_EMAILS = True
```

### Integração com Sentry

```bash
pip install sentry-sdk
```

```python
# settings.py
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[CeleryIntegration()],
)
```

## 🔒 Segurança

### Não Expor Flower em Produção sem Autenticação

```bash
# Executar com autenticação básica
celery -A my_project flower --basic_auth=user:password

# Ou configurar via settings
# flower_conf.py
basic_auth = ['user:password']
```

### Limpar Tasks Antigas

```python
# Celery automaticamente limpa com CELERY_RESULT_EXPIRES
# Mas você pode forçar:
from celery.task.control import purge
purge()
```

## 📚 Recursos Adicionais

- **Documentação Celery:** https://docs.celeryq.dev/
- **Flower:** https://flower.readthedocs.io/
- **Redis:** https://redis.io/docs/
- **Crontab Guru:** https://crontab.guru/ (testar expressões cron)

## ✅ Checklist de Produção

- [ ] Redis configurado e rodando
- [ ] Celery worker rodando (supervisor/systemd)
- [ ] Celery beat rodando (supervisor/systemd)
- [ ] Flower protegido com autenticação
- [ ] Logs configurados e rotacionados
- [ ] Alertas de erro configurados (email/Sentry)
- [ ] Backup de dados ativo
- [ ] Monitoramento de memória do worker
- [ ] Testes de todas as tasks críticas
- [ ] Documentação atualizada

## 🎉 Próximos Passos

Agora que o Celery está configurado, você pode:
1. ✅ Testar sincronização manual via shell
2. ✅ Verificar logs dos workers
3. ✅ Acessar Flower para monitoramento
4. ✅ Configurar alertas de erro
5. ✅ Criar tarefas personalizadas conforme necessidade
