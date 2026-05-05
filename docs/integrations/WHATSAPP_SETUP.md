# 📱 WhatsApp Evolution API - Guia de Configuração

## 🚀 O que foi adicionado

✅ **Evolution API** - Sistema completo de WhatsApp com autenticação por QR Code
✅ **PostgreSQL** - Base de dados dedicada para Evolution API
✅ **Redis Integration** - Cache compartilhado com Django
✅ **Network Bridge** - Comunicação entre todos os serviços

---

## 🐳 Serviços Docker Adicionados

### 1. Evolution API (WhatsApp)
- **Container:** `leguas_whatsapp_evolution`
- **Porta:** `8021` (http://localhost:8021)
- **Imagem:** `atendai/evolution-api:latest`
- **Autenticação:** QR Code
- **API Key:** Configurável via variável de ambiente

### 2. PostgreSQL 15
- **Container:** `leguas_whatsapp_postgres`
- **Porta:** `5433`
- **Database:** `evolution_db`
- **User:** `evolution_user`
- **Password:** `evolution_pass`

---

## ⚙️ Configuração Inicial

### 1. Configurar API Key

Edite o arquivo `.env.docker` e adicione:

```bash
# WhatsApp Evolution API
EVOLUTION_API_KEY=sua-chave-secreta-aqui-minimo-32-caracteres
```

**Gerar uma chave segura:**
```bash
# Linux/Mac
openssl rand -hex 32

# Windows PowerShell
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})
```

### 2. Iniciar os serviços

```bash
# Parar serviços atuais (se estiverem rodando)
docker-compose down

# Iniciar todos os serviços (incluindo WhatsApp)
docker-compose up -d

# Verificar se os serviços estão rodando
docker-compose ps
```

**Resultado esperado:**
```
NAME                       STATUS
leguas_mysql               Up (healthy)
leguas_redis               Up (healthy)
leguas_web                 Up
leguas_tailwind            Up
leguas_whatsapp_evolution  Up (healthy)
leguas_whatsapp_postgres   Up (healthy)
```

### 3. Verificar logs

```bash
# Logs do Evolution API
docker-compose logs -f evolution-api

# Logs do PostgreSQL
docker-compose logs -f evolution_db
```

---

## 📲 Como Conectar WhatsApp (QR Code)

### Método 1: Via API REST

#### 1. Criar uma instância

```bash
curl -X POST http://localhost:8021/instance/create \
  -H "apikey: sua-chave-secreta-aqui-minimo-32-caracteres" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "leguas_instance",
    "qrcode": true,
    "integration": "WHATSAPP-BAILEYS"
  }'
```

**Resposta:**
```json
{
  "instance": {
    "instanceName": "leguas_instance",
    "status": "created"
  },
  "hash": {
    "apikey": "sua-api-key-da-instancia"
  },
  "qrcode": {
    "code": "data:image/png;base64,iVBORw0KG...",
    "base64": "iVBORw0KG..."
  }
}
```

#### 2. Obter QR Code

```bash
curl -X GET http://localhost:8021/instance/connect/leguas_instance \
  -H "apikey: sua-chave-secreta-aqui-minimo-32-caracteres"
```

**Resposta:**
```json
{
  "code": "2@xYz...",
  "base64": "data:image/png;base64,iVBORw0KG...",
  "count": 1
}
```

#### 3. Escanear QR Code

1. Abra o WhatsApp no celular
2. Vá em **Configurações** > **Aparelhos conectados**
3. Clique em **Conectar um aparelho**
4. Escaneie o QR Code retornado pela API

#### 4. Verificar status da conexão

```bash
curl -X GET http://localhost:8021/instance/connectionState/leguas_instance \
  -H "apikey: sua-chave-secreta-aqui-minimo-32-caracteres"
```

**Resposta quando conectado:**
```json
{
  "instance": "leguas_instance",
  "state": "open"
}
```

---

### Método 2: Via Interface Web (Swagger)

1. Acesse: **http://localhost:8021/manager**
2. Use a API Key configurada para autenticar
3. Use os endpoints:
   - `POST /instance/create` - Criar instância
   - `GET /instance/connect/{instanceName}` - Obter QR Code
   - `GET /instance/connectionState/{instanceName}` - Verificar status

---

## 🔌 Integração com Django

### 1. Configurar no System Config

Acesse: **http://localhost:8000/system/**

Na seção **WhatsApp**:
- ✅ Habilitar WhatsApp: **Sim**
- 🔗 Evolution API URL: `http://evolution-api:8080`
- 🔑 Evolution API Key: `sua-chave-secreta-aqui-minimo-32-caracteres`
- 📱 Instance Name: `leguas_instance`

### 2. Testar conexão no Django

```python
from system_config.models import SystemConfiguration

# Obter configuração
config = SystemConfiguration.get_config()

# Verificar se WhatsApp está habilitado
if config.whatsapp_enabled:
    print(f"WhatsApp URL: {config.whatsapp_evolution_api_url}")
    print(f"API Key: {config.whatsapp_evolution_api_key}")
    print(f"Instance: {config.whatsapp_instance_name}")
```

### 3. Enviar mensagem teste

```python
import requests

config = SystemConfiguration.get_config()

url = f"{config.whatsapp_evolution_api_url}/message/sendText/{config.whatsapp_instance_name}"
headers = {
    "apikey": config.whatsapp_evolution_api_key,
    "Content-Type": "application/json"
}
data = {
    "number": "5511999999999",  # Número com DDI+DDD
    "text": "Olá! Esta é uma mensagem de teste do Léguas Franzinas!"
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

---

## 📚 Principais Endpoints da API

### Instâncias

```bash
# Criar instância
POST /instance/create

# Conectar (obter QR Code)
GET /instance/connect/{instanceName}

# Desconectar
DELETE /instance/logout/{instanceName}

# Deletar instância
DELETE /instance/delete/{instanceName}

# Listar instâncias
GET /instance/fetchInstances

# Status da conexão
GET /instance/connectionState/{instanceName}
```

### Mensagens

```bash
# Enviar texto
POST /message/sendText/{instanceName}

# Enviar imagem
POST /message/sendMedia/{instanceName}

# Enviar áudio
POST /message/sendWhatsAppAudio/{instanceName}

# Enviar documento
POST /message/sendMedia/{instanceName}

# Enviar localização
POST /message/sendLocation/{instanceName}

# Enviar contato
POST /message/sendContact/{instanceName}
```

### Grupos

```bash
# Criar grupo
POST /group/create/{instanceName}

# Atualizar foto do grupo
POST /group/updateGroupPicture/{instanceName}

# Adicionar participante
POST /group/updateParticipant/{instanceName}

# Promover a admin
POST /group/updateParticipant/{instanceName}

# Sair do grupo
POST /group/leaveGroup/{instanceName}
```

### Webhooks

```bash
# Configurar webhook
POST /webhook/set/{instanceName}

# Obter webhook
GET /webhook/find/{instanceName}
```

---

## 🔒 Segurança

### API Key

A API Key é **obrigatória** para todos os endpoints. Configure uma chave forte:

```bash
# .env.docker
EVOLUTION_API_KEY=A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6
```

### Tipos de Autenticação

A Evolution API suporta:
1. **apikey** (padrão) - Chave única para toda a API
2. **jwt** - Tokens JWT por instância
3. **none** - ⚠️ Não recomendado para produção

### Rede Docker

Todos os serviços estão na rede `leguas_network`:
- ✅ Django pode acessar: `http://evolution-api:8080`
- ✅ Evolution API pode acessar: `http://web:8000`
- ✅ Ambos compartilham Redis: `redis://redis:6379`

---

## 📊 Armazenamento de Dados

### PostgreSQL

A Evolution API usa PostgreSQL para armazenar:
- ✅ Instâncias criadas
- ✅ Mensagens enviadas/recebidas
- ✅ Contatos
- ✅ Chats
- ✅ Sessões ativas

### Redis

Usado para:
- ✅ Cache de sessões
- ✅ Fila de mensagens
- ✅ Estado de conexão

### Volumes Docker

```yaml
volumes:
  evolution_instances:    # Sessões do WhatsApp
  evolution_store:        # Armazenamento local
  evolution_postgres_data: # Base de dados
```

---

## 🛠️ Comandos Úteis

### Ver logs em tempo real

```bash
# Todos os serviços
docker-compose logs -f

# Apenas Evolution API
docker-compose logs -f evolution-api

# Apenas PostgreSQL
docker-compose logs -f evolution_db
```

### Reiniciar serviços

```bash
# Reiniciar Evolution API
docker-compose restart evolution-api

# Reiniciar PostgreSQL
docker-compose restart evolution_db

# Reiniciar todos
docker-compose restart
```

### Backup da base de dados

```bash
# Backup PostgreSQL
docker-compose exec evolution_db pg_dump -U evolution_user evolution_db > evolution_backup.sql

# Restaurar backup
cat evolution_backup.sql | docker-compose exec -T evolution_db psql -U evolution_user evolution_db
```

### Limpar e reiniciar

```bash
# Parar e remover containers
docker-compose down

# Remover volumes (⚠️ apaga dados!)
docker-compose down -v

# Reiniciar do zero
docker-compose up -d
```

---

## 🐛 Troubleshooting

### QR Code não aparece

```bash
# Verificar se a instância foi criada
curl -X GET http://localhost:8021/instance/fetchInstances \
  -H "apikey: sua-api-key"

# Reconectar instância
curl -X GET http://localhost:8021/instance/connect/leguas_instance \
  -H "apikey: sua-api-key"
```

### Conexão perdida

```bash
# Verificar status
curl -X GET http://localhost:8021/instance/connectionState/leguas_instance \
  -H "apikey: sua-api-key"

# Fazer logout e reconectar
curl -X DELETE http://localhost:8021/instance/logout/leguas_instance \
  -H "apikey: sua-api-key"

curl -X GET http://localhost:8021/instance/connect/leguas_instance \
  -H "apikey: sua-api-key"
```

### Erro de API Key inválida

Verifique se a API Key no `.env.docker` corresponde à usada nas requisições:

```bash
# Ver variáveis de ambiente do container
docker-compose exec evolution-api env | grep EVOLUTION_API_KEY
```

### PostgreSQL não inicia

```bash
# Ver logs
docker-compose logs evolution_db

# Verificar healthcheck
docker-compose ps evolution_db

# Reiniciar
docker-compose restart evolution_db
```

---

## 📖 Documentação Oficial

- **Evolution API:** https://doc.evolution-api.com/
- **GitHub:** https://github.com/EvolutionAPI/evolution-api
- **Swagger UI:** http://localhost:8021/manager (após iniciar)

---

## ✅ Checklist de Configuração

- [ ] Gerar API Key segura
- [ ] Adicionar API Key ao `.env.docker`
- [ ] Iniciar serviços: `docker-compose up -d`
- [ ] Verificar healthcheck: `docker-compose ps`
- [ ] Criar instância via API
- [ ] Obter QR Code
- [ ] Escanear QR Code no WhatsApp
- [ ] Verificar conexão: state = "open"
- [ ] Configurar no Django (System Config)
- [ ] Testar envio de mensagem
- [ ] Configurar webhooks (opcional)
- [ ] Fazer backup da configuração

---

## 🎯 Exemplo Completo de Uso

```bash
# 1. Definir variáveis
export API_KEY="sua-chave-secreta-aqui-minimo-32-caracteres"
export BASE_URL="http://localhost:8021"
export INSTANCE="leguas_instance"

# 2. Criar instância
curl -X POST $BASE_URL/instance/create \
  -H "apikey: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"instanceName\": \"$INSTANCE\",
    \"qrcode\": true
  }"

# 3. Obter QR Code
curl -X GET $BASE_URL/instance/connect/$INSTANCE \
  -H "apikey: $API_KEY"

# 4. Aguardar scan do QR Code (15-30 segundos)

# 5. Verificar conexão
curl -X GET $BASE_URL/instance/connectionState/$INSTANCE \
  -H "apikey: $API_KEY"

# 6. Enviar mensagem teste
curl -X POST $BASE_URL/message/sendText/$INSTANCE \
  -H "apikey: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "number": "5511999999999",
    "text": "Olá do Léguas Franzinas! 🚚"
  }'
```

---

**🎉 WhatsApp Evolution API configurado e pronto para uso!**
