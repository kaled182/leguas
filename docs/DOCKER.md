# 🐳 Guia Docker - Leguas Franzinas

## Pré-requisitos

- Docker Desktop instalado ([Download](https://www.docker.com/products/docker-desktop))
- Docker Compose (incluído no Docker Desktop)
- Pelo menos 4GB de RAM disponível

## 🚀 Início Rápido

### 1. Configurar Variáveis de Ambiente

```bash
# Copiar o ficheiro de exemplo
cp .env.docker.example .env.docker

# Editar as variáveis necessárias
# Mínimo necessário: SECRET_KEY e credenciais de APIs externas
```

### 2. Construir e Iniciar os Containers

```bash
# Construir e iniciar todos os serviços
docker-compose up --build

# Ou em modo detached (background)
docker-compose up -d --build
```

A aplicação estará disponível em: **http://localhost:8000**

### 3. Criar Superutilizador (Primeira Vez)

```bash
# Executar comando dentro do container
docker-compose exec web python manage.py createsuperuser
```

### 4. Aceder ao Admin

Visite: **http://localhost:8000/admin/**

## 📋 Serviços Disponíveis

| Serviço    | URL                      | Descrição                    |
|------------|--------------------------|------------------------------|
| Web App    | http://localhost:8000    | Aplicação Django principal   |
| MySQL      | localhost:3306           | Base de dados                |
| Tailwind   | N/A                      | Compilação automática de CSS |

## 🛠️ Comandos Úteis

### Gestão de Containers

```bash
# Iniciar serviços
docker-compose up

# Parar serviços
docker-compose down

# Parar e remover volumes (APAGA DADOS!)
docker-compose down -v

# Ver logs
docker-compose logs -f

# Ver logs de um serviço específico
docker-compose logs -f web
```

### Django Management Commands

```bash
# Executar manage.py commands
docker-compose exec web python manage.py <comando>

# Exemplos:
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput
docker-compose exec web python manage.py createsuperuser

# Sincronizar dados da API Paack
docker-compose exec web python manage.py shell
>>> from ordersmanager_paack.sync_service import SyncService
>>> SyncService().sync_all_data()
>>> exit()
```

### Acesso ao Shell

```bash
# Shell Django
docker-compose exec web python manage.py shell

# Shell do container
docker-compose exec web bash

# MySQL client
docker-compose exec db mysql -u leguas_user -p leguas_db
# Senha: leguas_password_dev
```

### Tailwind CSS

```bash
# Reiniciar o serviço Tailwind se necessário
docker-compose restart tailwind

# Ver logs do Tailwind
docker-compose logs -f tailwind
```

## 🔄 Atualizar Código

Quando modificar o código Python:

```bash
# Reiniciar apenas o serviço web
docker-compose restart web

# Se adicionou dependências ao requirements.txt
docker-compose up -d --build web
```

Quando modificar CSS/JS:
- O Tailwind está em modo watch e recompila automaticamente
- Sempre executar `collectstatic` após mudanças

## 🗄️ Base de Dados

### Acesso Direto

```bash
# Via Docker
docker-compose exec db mysql -u leguas_user -pleguas_password_dev leguas_db

# Via cliente MySQL na máquina host
mysql -h 127.0.0.1 -P 3306 -u leguas_user -pleguas_password_dev leguas_db
```

### Backup e Restore

```bash
# Backup
docker-compose exec db mysqldump -u leguas_user -pleguas_password_dev leguas_db > backup.sql

# Restore
docker-compose exec -T db mysql -u leguas_user -pleguas_password_dev leguas_db < backup.sql
```

### Resetar Base de Dados

```bash
# ATENÇÃO: Isto apaga todos os dados!
docker-compose down -v
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

## 🐛 Troubleshooting

### Container não inicia

```bash
# Ver logs detalhados
docker-compose logs web

# Verificar se as portas estão disponíveis
netstat -ano | findstr :8000
netstat -ano | findstr :3306
```

### Erro de conexão com MySQL

```bash
# Verificar se o MySQL está healthy
docker-compose ps

# Ver logs do MySQL
docker-compose logs db

# Aguardar o MySQL ficar pronto (pode demorar 30-60 segundos na primeira vez)
```

### Problemas com Tailwind

```bash
# Verificar se o Node.js está instalado no container
docker-compose exec tailwind node --version

# Reinstalar dependências do Tailwind
docker-compose exec web python manage.py tailwind install

# Reconstruir CSS
docker-compose exec web python manage.py tailwind build
```

### Arquivos estáticos não carregam

```bash
# Coletar novamente os estáticos
docker-compose exec web python manage.py collectstatic --noinput --clear

# Verificar permissões
docker-compose exec web ls -la /app/staticfiles
```

### Limpar tudo e recomeçar

```bash
# ATENÇÃO: Remove TODOS os containers, volumes e imagens do projeto
docker-compose down -v
docker system prune -a
docker-compose up --build
```

## 📝 Notas de Desenvolvimento

### Modo Debug

O Docker está configurado com `DEBUG=True` por padrão. Os logs são verbosos e o código recarrega automaticamente com `--reload` no Gunicorn.

### Hot Reload

- **Python**: Gunicorn reinicia automaticamente quando deteta mudanças
- **Tailwind**: Recompila automaticamente em modo watch
- **Templates**: Mudanças são visíveis imediatamente

### Volumes

Os seguintes diretórios são montados como volumes:
- Código da aplicação: montado em `/app`
- Arquivos estáticos: `static_volume`
- Arquivos de media: `media_volume`
- Dados MySQL: `mysql_data`

### Performance

Para melhor performance em desenvolvimento:
- Use volumes named em vez de bind mounts para `node_modules`
- Considere aumentar memória do Docker Desktop para 4GB+
- No Windows, prefira WSL2 backend

## 🚀 Produção

⚠️ **Este setup é para DESENVOLVIMENTO LOCAL apenas!**

Para produção, considere:
- Usar `DEBUG=False`
- Configurar HTTPS/SSL
- Usar passwords fortes e aleatórias
- Configurar backup automático da BD
- Usar serviço de MySQL gerenciado
- Adicionar Nginx como reverse proxy
- Configurar logs centralizados
- Adicionar monitoring (Prometheus, Grafana)

## 📚 Recursos

- [Documentação Docker](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Django em Docker](https://docs.docker.com/samples/django/)
