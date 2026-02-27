# WPPConnect ↔ Chatwoot Bridge

Middleware que conecta WPPConnect ao Chatwoot, permitindo receber e enviar mensagens do WhatsApp através da central de atendimento.

## 🎯 Funcionalidades

- ✅ Recebe mensagens do WPPConnect via webhook
- ✅ Cria/atualiza contatos no Chatwoot automaticamente
- ✅ Cria/gerencia conversas no Chatwoot
- ✅ Envia respostas do Chatwoot de volta ao WhatsApp
- ✅ Logs detalhados para debugging
- ✅ Health check endpoint

## 🚀 Como Usar

### 1. Configurar Variáveis de Ambiente

Copie `.env.example` para `.env` e configure:

```env
# WPPConnect
WPPCONNECT_URL=http://leguas_wppconnect:21465
WPPCONNECT_SESSION=leguas_wppconnect
WPPCONNECT_TOKEN=seu_token_aqui

# Chatwoot
CHATWOOT_URL=http://leguas_chatwoot_web:3000
CHATWOOT_ACCOUNT_ID=1
CHATWOOT_INBOX_ID=1
CHATWOOT_API_TOKEN=seu_token_aqui

# Server
PORT=3500
LOG_LEVEL=info
```

### 2. Executar (Docker)

Já está configurado no `docker-compose.yml` principal:

```bash
docker compose up -d wppconnect_bridge
```

### 3. Executar (Local - Desenvolvimento)

```bash
npm install
npm start

# Ou com nodemon
npm run dev
```

## 📡 Endpoints

### GET /health
Health check do serviço.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-02-10T19:00:00.000Z",
  "config": {
    "wppconnect": true,
    "chatwoot": true
  }
}
```

### POST /webhook/wppconnect
Recebe mensagens do WPPConnect.

**Request Body:**
```json
{
  "event": "onMessage",
  "data": {
    "from": "5511999999999@c.us",
    "body": "Olá!",
    "fromMe": false,
    "isGroupMsg": false,
    "notifyName": "João Silva"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "contactId": 123,
  "conversationId": 456
}
```

### POST /webhook/chatwoot
Recebe respostas do Chatwoot para enviar ao WhatsApp.

**Request Body:**
```json
{
  "event": "message_created",
  "message_type": "outgoing",
  "conversation": {
    "meta": {
      "sender": {
        "phone_number": "+5511999999999"
      }
    }
  },
  "content": "Obrigado pelo contato!"
}
```

**Response:**
```json
{
  "status": "success",
  "wppconnect_response": { ... }
}
```

## 🔧 Configuração no Chatwoot

1. **Criar Inbox API:**
   - Settings → Inboxes → Add Inbox → API
   - Webhook URL: `http://leguas_wppconnect_bridge:3500/webhook/chatwoot`

2. **Copiar credenciais:**
   - Account ID (geralmente 1)
   - Inbox ID (aparece após criar)
   - API Token (gerar em Profile Settings → Access Token)

3. **Atualizar `.env` do bridge** com as credenciais

## 🔧 Configuração no WPPConnect

Adicionar webhook no `docker-compose.yml`:

```yaml
wppconnect:
  environment:
    WEBHOOK_GLOBAL_ENABLED: "true"
    WEBHOOK_GLOBAL_URL: "http://leguas_wppconnect_bridge:3500/webhook/wppconnect"
    WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS: "true"
```

## 📊 Logs

O bridge usa Winston para logs estruturados:

```bash
# Docker
docker logs leguas_wppconnect_bridge -f

# Logs locais
npm start
```

**Exemplo de log:**
```
[2026-02-10T19:00:00.000Z] INFO: Webhook received from WPPConnect {"event":"onMessage","from":"5511999999999@c.us"}
[2026-02-10T19:00:01.000Z] INFO: Contact found {"phoneNumber":"+5511999999999","contactId":123}
[2026-02-10T19:00:02.000Z] INFO: Message sent to Chatwoot {"conversationId":456,"messageId":789}
```

## 🐛 Troubleshooting

### Mensagens não chegam ao Chatwoot

1. Verificar se webhook está configurado no WPPConnect
2. Testar endpoint manualmente:
```bash
curl -X POST http://localhost:3500/webhook/wppconnect \
  -H "Content-Type: application/json" \
  -d '{"event":"onMessage","data":{"from":"5511999999999@c.us","body":"Teste"}}'
```

### Respostas não chegam ao WhatsApp

1. Verificar credenciais WPPConnect no `.env`
2. Testar conexão:
```bash
curl http://localhost:21465/api/leguas_wppconnect/check-connection-session \
  -H "Authorization: Bearer SEU_TOKEN"
```

### Erro 401 no Chatwoot

1. Verificar API Token
2. Testar credenciais:
```bash
curl http://localhost:3000/api/v1/accounts/1/inboxes \
  -H "api_access_token: SEU_TOKEN"
```

## 📚 Dependências

- **express** - Framework web
- **axios** - Cliente HTTP
- **winston** - Logging
- **dotenv** - Variáveis de ambiente

## 📄 Licença

MIT - Léguas Franzinas
