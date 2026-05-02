# 📦 Deployment Configuration

Este diretório contém todos os arquivos de configuração necessários para fazer deploy do projeto em produção.

## 📂 Estrutura

```
deployment/
├── supervisor/          # Configurações do Supervisor
│   └── celery.conf     # Config para Celery Worker e Beat
├── systemd/            # Configurações do systemd
│   ├── celery-worker.service
│   └── celery-beat.service
├── scripts/            # Scripts auxiliares
│   └── celery-manager.sh
├── DEPLOYMENT_GUIDE.md # Guia completo de deployment
└── README.md           # Este arquivo
```

## 🚀 Quick Start

### Desenvolvimento Local (Windows)

```powershell
# Terminal 1 - Django
python manage.py runserver

# Terminal 2 - Celery Worker
celery -A my_project worker -l info --pool=solo

# Terminal 3 - Celery Beat
celery -A my_project beat -l info
```

### Produção Linux (Supervisor)

```bash
# 1. Copiar arquivo de config
sudo cp supervisor/celery.conf /etc/supervisor/conf.d/leguas-celery.conf

# 2. Editar caminhos no arquivo
sudo nano /etc/supervisor/conf.d/leguas-celery.conf

# 3. Criar diretórios de log
sudo mkdir -p /var/log/celery
sudo chown www-data:www-data /var/log/celery

# 4. Recarregar Supervisor
sudo supervisorctl reread
sudo supervisorctl update

# 5. Iniciar Celery
sudo supervisorctl start leguas-celery:*

# 6. Verificar status
sudo supervisorctl status
```

### Produção Linux (systemd)

```bash
# 1. Copiar service files
sudo cp systemd/celery-worker.service /etc/systemd/system/
sudo cp systemd/celery-beat.service /etc/systemd/system/

# 2. Editar caminhos nos arquivos
sudo nano /etc/systemd/system/celery-worker.service
sudo nano /etc/systemd/system/celery-beat.service

# 3. Recarregar systemd
sudo systemctl daemon-reload

# 4. Habilitar serviços
sudo systemctl enable celery-worker celery-beat

# 5. Iniciar serviços
sudo systemctl start celery-worker celery-beat

# 6. Verificar status
sudo systemctl status celery-worker celery-beat
```

## 🛠️ Script de Gerenciamento

O script `celery-manager.sh` facilita o gerenciamento do Celery em produção.

### Instalação

```bash
# Copiar script para /usr/local/bin
sudo cp scripts/celery-manager.sh /usr/local/bin/celery-manager
sudo chmod +x /usr/local/bin/celery-manager

# Editar configurações no início do script
sudo nano /usr/local/bin/celery-manager
```

### Uso

```bash
# Menu interativo
celery-manager

# Comandos diretos
celery-manager start
celery-manager stop
celery-manager restart
celery-manager status
celery-manager logs
celery-manager test
```

## 📋 Checklist de Deployment

### Pré-requisitos

- [ ] Servidor Linux configurado (Ubuntu/Debian)
- [ ] Python 3.8+ instalado
- [ ] Redis instalado e rodando
- [ ] MySQL/PostgreSQL configurado
- [ ] Usuário `www-data` ou equivalente criado
- [ ] Nginx + Gunicorn configurados

### Instalação

- [ ] Virtualenv criado
- [ ] Dependências instaladas (`pip install -r requirements.txt`)
- [ ] Variáveis de ambiente configuradas (`.env`)
- [ ] Migrações aplicadas (`python manage.py migrate`)
- [ ] Arquivos estáticos coletados (`python manage.py collectstatic`)

### Celery

- [ ] Supervisor/systemd configurado
- [ ] Workers iniciando corretamente
- [ ] Beat agendando tasks
- [ ] Logs sendo escritos
- [ ] Testado task manual

### Segurança

- [ ] Firewall configurado
- [ ] Redis protegido (apenas localhost)
- [ ] Flower com autenticação (se usado)
- [ ] SSL/TLS habilitado
- [ ] Backups automáticos configurados

### Monitoramento

- [ ] Logs rotacionados (logrotate)
- [ ] Sentry configurado (opcional)
- [ ] Alertas por email configurados
- [ ] Flower acessível (opcional)

## 📖 Documentação

- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Guia completo de deployment
- **[../docs/CELERY_SETUP.md](../docs/CELERY_SETUP.md)** - Configuração do Celery
- **[../PROXIMOS_PASSOS_FRONTEND.md](../PROXIMOS_PASSOS_FRONTEND.md)** - Frontend e próximos passos

## 🔧 Configurações Importantes

### Variáveis de Ambiente (.env)

```env
# Django
SECRET_KEY=sua-chave-secreta-aqui
DEBUG=False
ALLOWED_HOSTS=seu-dominio.com

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Database
DATABASE_URL=mysql://user:password@localhost:3306/leguas_db

# Email (para alertas)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-senha-app
```

### Caminhos a Configurar

Nos arquivos de configuração, substitua:

- `/home/user/venv` → Caminho do seu virtualenv
- `/home/user/app.leguasfranzinas.pt/app.leguasfranzinas.pt` → Caminho do projeto
- `www-data` → Seu usuário de aplicação
- `seu-dominio.com` → Seu domínio

## 🐛 Troubleshooting

### Workers não iniciam

```bash
# Ver logs
sudo tail -f /var/log/celery/worker_error.log

# Testar comando manual
sudo su - www-data -s /bin/bash
cd /path/to/project
source venv/bin/activate
celery -A my_project worker -l debug
```

### Beat não agenda tasks

```bash
# Verificar se Beat está rodando
sudo supervisorctl status leguas-celery-beat

# Ver logs
sudo tail -f /var/log/celery/beat.log

# Verificar schedule no código
python manage.py shell
>>> from my_project.celery import app
>>> print(app.conf.beat_schedule)
```

### Redis não conecta

```bash
# Verificar se Redis está rodando
redis-cli ping

# Iniciar Redis
sudo systemctl start redis

# Ver logs do Redis
sudo tail -f /var/log/redis/redis-server.log
```

## 📞 Suporte

Consulte a documentação completa em [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

Para problemas específicos:
1. Verifique os logs em `/var/log/celery/`
2. Teste comandos manualmente
3. Consulte a documentação oficial do Celery

## 🔗 Links Úteis

- [Documentação Celery](https://docs.celeryq.dev/)
- [Supervisor Manual](http://supervisord.org/)
- [systemd Documentation](https://www.freedesktop.org/wiki/Software/systemd/)
- [Redis Documentation](https://redis.io/docs/)
