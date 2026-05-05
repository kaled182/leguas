# Guia de Troubleshooting - Sistema Omnichannel

## Visão Geral

Este documento consolida todos os problemas encontrados durante a implementação do sistema omnichannel (Chatwoot + WPPConnect + Typebot + Django) e suas soluções comprovadas.

**Data de criação:** 2025-02-26  
**Versão:** 1.0  
**Status:** Baseado em implementação 100% funcional

---

## Índice

1. [Problemas de Infraestrutura](#1-problemas-de-infraestrutura)
2. [Problemas de Messaging - Bridge](#2-problemas-de-messaging---bridge)
3. [Problemas de Media Transfer](#3-problemas-de-media-transfer)
4. [Problemas de Webhook](#4-problemas-de-webhook)
5. [Problemas de Django API](#5-problemas-de-django-api)
6. [Problemas de Typebot](#6-problemas-de-typebot)
7. [Comandos Úteis](#7-comandos-úteis)

---

## 1. Problemas de Infraestrutura

### 1.1 Chatwoot Container em Loop de Restart

**Sintoma:**
```
Container leguas_chatwoot_web constantly restarting
Status: Restarting (1) X seconds ago
```

**Causa:**
Arquivo PID (`/app/tmp/pids/server.pid`) não foi removido após shutdown inesperado.

**Solução:**
```powershell
docker compose stop chatwoot_web
docker compose rm -f chatwoot_web
docker compose up -d chatwoot_web
```

**Prevenção:**
Sempre use `docker compose stop` antes de `docker compose down` para graceful shutdown.

---

### 1.2 Container Não Carrega Código Atualizado

**Sintoma:**
```
Editei código mas container ainda executa versão antiga
```

**Causa:**
Projeto WPPConnect Bridge **NÃO usa volumes**. Código é copiado para imagem durante build.

**Solução:**
```powershell
# Build sem cache
docker compose build --no-cache wppconnect_bridge

# Parar e remover container antigo
docker stop leguas_wppconnect_bridge
docker rm leguas_wppconnect_bridge

# Subir com nova imagem
docker compose up -d wppconnect_bridge

# Iniciar container
docker start leguas_wppconnect_bridge
```

**IMPORTANTE:** `docker compose restart` NÃO aplica mudanças de código! Sempre recrie o container.

---

### 1.3 Rede Docker Não Resolve Nomes de Container

**Sintoma:**
```
Error: getaddrinfo ENOTFOUND leguas_chatwoot_web
```

**Causa:**
Containers não estão na mesma rede Docker.

**Solução:**
```powershell
# Verificar rede de cada container
docker inspect leguas_wppconnect_bridge | Select-String "NetworkMode"
docker inspect leguas_chatwoot_web | Select-String "NetworkMode"

# Ambos devem estar em: leguas_network
```

**Configuração correta no docker-compose.yml:**
```yaml
networks:
  default:
    name: leguas_network
```

---

## 2. Problemas de Messaging - Bridge

### 2.1 Mensagens Duplicadas

**Sintoma:**
```
Mesma mensagem chega 2 vezes no WhatsApp
Mesmo ID, mesmo timestamp
```

**Causa:**
Chatwoot dispara **2 webhooks** para cada mensagem:
- `message_created`
- `message_updated`

**Solução:**
Implementar cache de deduplicação com TTL:

```javascript
// Variáveis globais
const processedOutgoingMessages = new Set();
const CACHE_TTL_MS = 10000; // 10 segundos

// No handler de webhook
const messageId = req.body.id || req.body.message?.id;

if (processedOutgoingMessages.has(messageId)) {
  logger.info('❌ Duplicate message BLOCKED', { messageId });
  return res.json({ status: 'duplicate_ignored', messageId });
}

processedOutgoingMessages.add(messageId);

setTimeout(() => {
  processedOutgoingMessages.delete(messageId);
}, CACHE_TTL_MS);
```

**Arquivo:** `wppconnect-chatwoot-bridge/index.js`, linhas 1127-1148

---

### 2.2 Espaços em Branco Extras no Final de Mensagens

**Sintoma:**
```
Mensagens no WhatsApp aparecem com espaços extras embaixo do texto


```

**Causa:**
Chatwoot envia conteúdo com `\n\n\n` no final.

**Solução:**
```javascript
const rawContent = req.body.content ?? req.body.message?.content ?? '';
const content = rawContent.replace(/\n+$/, ''); // Remove trailing newlines
```

**Arquivo:** `wppconnect-chatwoot-bridge/index.js`, linhas 1109-1111

---

### 2.3 Bridge Não Recebe Webhook do Chatwoot

**Sintoma:**
```
Mensagens enviadas no Chatwoot não chegam no WhatsApp
Logs não mostram "Webhook received"
```

**Causa:**
Webhook **NÃO é criado automaticamente** ao criar Inbox no Chatwoot.

**Diagnóstico:**
```powershell
$headers = @{ 'api_access_token' = 'w2w8N98Pv8yqazrHPyqAuwkR' }
Invoke-RestMethod -Uri 'http://localhost:3000/api/v1/accounts/1/webhooks' -Headers $headers
```

**Solução:**
Criar webhook manualmente via API:

```powershell
$headers = @{ 'api_access_token' = 'w2w8N98Pv8yqazrHPyqAuwkR' }
$body = @{
    url = 'http://leguas_wppconnect_bridge:3500/webhook/chatwoot'
    subscriptions = @('message_created', 'message_updated', 'conversation_created', 'conversation_updated')
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri 'http://localhost:3000/api/v1/accounts/1/webhooks' `
  -Method POST `
  -Headers $headers `
  -ContentType 'application/json' `
  -Body $body
```

**Verificação:**
```powershell
# Logs do bridge devem mostrar
docker compose logs wppconnect_bridge --tail 20 | Select-String "Webhook received"
```

---

## 3. Problemas de Media Transfer

### 3.1 Não Consegue Receber Imagens/Documentos do WhatsApp

**Sintomas:**
```
Imagens chegam mas não aparecem no Chatwoot
Thumbnails aparecem mas não imagem completa
Documentos aparecem como "image/jpeg" incorretamente
```

**Causa:** Múltiplos bugs no código original:

#### Bug 1: conversationId hardcoded
```javascript
// ERRADO
conversationId: 1

// CORRETO (linha 1279)
conversationId: conversationRecord.conversation_id
```

#### Bug 2: MAX_DEPTH muito baixo
```javascript
// ERRADO
MAX_DEPTH = 1

// CORRETO (linha 161)
const MAX_DEPTH = 3;
const MAX_STRING_LENGTH = 200;
```

#### Bug 3: Attachments não declarado
```javascript
// ERRADO
const payload = { content };

// CORRETO (linhas 1232-1233)
let payload = { content };
const attachments = [];
```

#### Bug 4: Content-type fixo para imagens
```javascript
// ERRADO
'content-type': 'image/jpeg'

// CORRETO (linha 455)
'content-type': mimeType // Dinâmico baseado no arquivo
```

#### Bug 5: Qualidade baixa (thumbnail)
```javascript
// ERRADO
const media = await client.then((client) => 
  client.decryptFile(message)
);

// CORRETO (linhas 425-458)
async function downloadMediaFromWPP(message, client) {
  const mediaData = await client.downloadMedia(message.id);
  
  return {
    buffer: Buffer.from(mediaData.data, 'base64'),
    mimetype: mediaData.mimetype || 'application/octet-stream',
    filename: mediaData.filename || `media_${Date.now()}`
  };
}
```

#### Bug 6: Todos arquivos detectados como imagem
```javascript
// ERRADO
const isDocument = false; // Sempre imagem

// CORRETO (linhas 507-575)
function buildAttachmentFromWPPMessage(downloadResult, message) {
  const isPDF = downloadResult.mimetype === 'application/pdf';
  const isDoc = /word|document|excel|sheet/.test(downloadResult.mimetype);
  const isDocument = isPDF || isDoc || !downloadResult.mimetype.startsWith('image/');
  
  return {
    file_url: `data:${downloadResult.mimetype};base64,${base64}`,
    file_type: isDocument ? 'file' : 'image'
  };
}
```

#### Bug 7: Pattern matching inválido
```javascript
// ERRADO
if (msg.type === 'image|video|audio|ptt|document')

// CORRETO (linha 1205)
if (['image', 'video', 'audio', 'ptt', 'document'].includes(msg.type))
```

**Arquivo:** `wppconnect-chatwoot-bridge/index.js`

---

### 3.2 Não Consegue Enviar Imagens/Documentos para WhatsApp

**Sintomas:**
```
Imagens enviadas do Chatwoot não chegam no WhatsApp
Erro: "empty_file" nos logs
Webhook não dispara para mensagens com anexo apenas
```

**Causa:** Múltiplos problemas:

#### Problema 1: Chatwoot Webhook Limitation

**Descoberta crítica:** Chatwoot **NÃO dispara webhook** `message_created` para mensagens contendo **APENAS anexo** (sem texto).

**Solução:** Implementar polling da API do Chatwoot

```javascript
let lastCheckedOutgoingId = 0;

async function pollChatwootOutgoingMessages() {
  try {
    const conversationId = 11; // TODO: tornar dinâmico
    
    const response = await axios.get(
      `${config.chatwoot.url}/api/v1/accounts/${accountId}/conversations/${conversationId}/messages`,
      { headers: { 'api_access_token': apiToken } }
    );
    
    const outgoingMessages = response.data.payload
      .filter(msg => msg.message_type === 1 && msg.id > lastCheckedOutgoingId)
      .sort((a, b) => a.id - b.id);
    
    for (const message of outgoingMessages) {
      lastCheckedOutgoingId = message.id;
      
      // Evita duplicação com webhook
      if (processedOutgoingMessages.has(message.id)) continue;
      
      if (!message.attachments || message.attachments.length === 0) continue;
      
      processedOutgoingMessages.add(message.id);
      setTimeout(() => processedOutgoingMessages.delete(message.id), CACHE_TTL_MS);
      
      // Processar anexos
      await sendAttachmentsToWPP(wppNumber, message.attachments, message.content || '');
    }
  } catch (error) {
    logger.error('Error polling Chatwoot outgoing messages', { error: error.message });
  }
}

// Polling a cada 3 segundos
setInterval(pollChatwootOutgoingMessages, 3000);
```

**Arquivo:** `wppconnect-chatwoot-bridge/index.js`, linhas 1500-1620

---

#### Problema 2: URL Localhost em Docker

**Sintoma:**
```
Error downloading attachment: connect ECONNREFUSED 127.0.0.1:3000
```

**Causa:**
Chatwoot Active Storage gera URLs com `http://localhost:3000` ao invés de nome do container.

**Solução:**
```javascript
async function downloadChatwootAttachment(url) {
  let resolvedUrl = url;
  
  // Replace localhost com nome do container Docker
  resolvedUrl = resolvedUrl.replace('http://localhost:3000', config.chatwoot.url);
  resolvedUrl = resolvedUrl.replace('https://localhost:3000', config.chatwoot.url);
  
  const response = await axios.get(resolvedUrl, {
    responseType: 'arraybuffer',
    timeout: 60000
  });
  
  return {
    buffer: Buffer.from(response.data),
    mimeType: response.headers['content-type']
  };
}
```

**Arquivo:** `wppconnect-chatwoot-bridge/index.js`, linhas 631-669

---

#### Problema 3: WPPConnect Requer Data URI

**Sintoma:**
```
Downloaded attachment buffer {"bufferLength":48830}
Encoded to base64 {"base64Length":65108}
ERROR: Error sending attachment {"error":{"code":"empty_file"}}
```

**Causa:**
WPPConnect API requer formato **data URI** (`data:image/jpeg;base64,...`) e não base64 puro.

**Solução:**
```javascript
// Após fazer download e codificar base64
const base64Content = downloadResult.buffer.toString('base64');
const mimeType = downloadResult.mimeType;

// Adicionar prefixo data URI
const base64WithPrefix = `data:${mimeType};base64,${base64Content}`;

const payload = { phone, filename };

if (isVoiceNote) {
  payload.base64Ptt = base64WithPrefix;
} else {
  payload.base64 = base64WithPrefix;
}

await axios.post(
  `${config.wppconnect.url}/api/${config.wppconnect.session}/send-file-base64`,
  payload,
  { timeout: 60000 }
);
```

**Arquivo:** `wppconnect-chatwoot-bridge/index.js`, linhas 758-773

**IMPORTANTE:** Este foi o fix final que resolveu o envio de anexos!

---

### 3.3 Resumo: Status Final de Media Transfer

| Funcionalidade | Status | Latência | Observações |
|---------------|--------|----------|-------------|
| ✅ Receber texto | 100% | 2s | Via polling WPPConnect |
| ✅ Receber imagens | 100% | 2s | Full quality, não thumbnail |
| ✅ Receber documentos | 100% | 2s | PDFs, DOCs completos |
| ✅ Enviar texto | 100% | <1s | Via webhook Chatwoot |
| ✅ Enviar imagens | 100% | ~3s | Via polling (webhook limitation) |
| ✅ Enviar documentos | 100% | ~3s | Via polling (webhook limitation) |

---

## 4. Problemas de Webhook

### 4.1 Como Verificar se Webhook Está Configurado

```powershell
$headers = @{ 'api_access_token' = 'w2w8N98Pv8yqazrHPyqAuwkR' }
$webhooks = Invoke-RestMethod -Uri 'http://localhost:3000/api/v1/accounts/1/webhooks' -Headers $headers
$webhooks | ConvertTo-Json -Depth 5
```

**Saída esperada:**
```json
{
  "id": 1,
  "url": "http://leguas_wppconnect_bridge:3500/webhook/chatwoot",
  "subscriptions": [
    "message_created",
    "message_updated",
    "conversation_created",
    "conversation_updated"
  ]
}
```

---

### 4.2 Webhook Não Dispara

**Diagnóstico:**
```powershell
# Verificar logs do bridge
docker compose logs wppconnect_bridge -f --tail 50 | Select-String "Webhook"

# Enviar mensagem teste no Chatwoot
# Deve aparecer: "Webhook received from Chatwoot"
```

**Possíveis causas:**
1. Webhook não criado (ver seção 2.3)
2. URL do webhook incorreta
3. Bridge não está rodando
4. Firewall bloqueando porta 3500

**Solução:**
```powershell
# 1. Verificar se bridge está rodando
docker compose ps wppconnect_bridge

# 2. Testar endpoint diretamente
Invoke-WebRequest -Uri 'http://localhost:3500/health' -Method GET

# 3. Recriar webhook
# (ver comandos na seção 2.3)
```

---

### 4.3 Webhook Limitation: Attachment-Only Messages

**IMPORTANTE:** Esta é uma limitação do Chatwoot, não um bug!

**Comportamento:**
- Mensagem com **texto**: Webhook `message_created` dispara ✅
- Mensagem com **apenas anexo**: Webhook NÃO dispara ❌

**Evidência:**
```powershell
# Buscar mensagens na API
$messages = Invoke-RestMethod -Uri 'http://localhost:3000/api/v1/accounts/1/conversations/11/messages' -Headers $headers

# Mensagem 305 (texto): encontrada no log do webhook
# Mensagem 306 (imagem): NÃO encontrada no log do webhook
```

**Solução:**
Implementar polling (ver seção 3.2, Problema 1).

---

## 5. Problemas de Django API

### 5.1 Endpoint 404 Not Found

**Sintoma:**
```
POST http://localhost:8000/drivers/api/register-typebot/
Response: 404 Page Not Found
```

**Causa:**
URL incorreta. A app está montada em `/driversapp/` não `/drivers/`.

**Solução:**
URL correta: `http://localhost:8000/driversapp/api/register-typebot/`

**Verificar rotas:**
```python
# my_project/urls.py
path('driversapp/', include('drivers_app.urls')),

# drivers_app/urls.py
path('api/register-typebot/', views.register_driver_typebot, name='register_driver_typebot'),
```

---

### 5.2 Erro de Encoding UTF-8

**Sintoma:**
```
{"success": false, "error": "'utf-8' codec can't decode byte 0xe3 in position 29"}
```

**Causa:**
PowerShell envia JSON com encoding incorreto.

**Solução:**
```powershell
# ERRADO
$body = '{"nome":"João"}';
Invoke-RestMethod -Body $body

# CORRETO
$body = '{"nome":"Joao"}'; # Sem acentos OU
Invoke-RestMethod -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

---

### 5.3 Mudanças no Código Não Aplicadas

**Sintoma:**
```
Editei views.py mas erro persiste
```

**Causa:**
Django não recarrega automaticamente em produção.

**Solução:**
```powershell
docker compose restart web
```

**Para desenvolvimento:**
```powershell
# Modo debug com auto-reload
docker compose up web
```

---

## 6. Problemas de Typebot

### 6.1 Typebot Não Inicia no Chatwoot

**Sintoma:**
```
Cliente envia mensagem mas bot não responde
Conversa fica sem atribuição
```

**Diagnóstico:**
```powershell
# Verificar se Typebot está rodando
docker compose ps typebot_builder typebot_viewer

# Verificar logs
docker compose logs typebot_viewer --tail 50
```

**Possíveis causas e soluções:**

#### Causa 1: Automação não configurada

**Solução:**
1. Acesse Chatwoot → Settings → Automation
2. Crie automação:
   - Evento: "Message Created"
   - Condição: `Message contains "cadastro motorista"`
   - Ação: "Assign to team/agent" → Typebot

#### Causa 2: Bot não publicado

**Solução:**
1. Acesse http://localhost:8081
2. Abra o bot
3. Clique em **"Publish"**
4. Copie Bot ID
5. Configure no Chatwoot

#### Causa 3: Integração não configurada

**Solução:**
1. Chatwoot → Settings → Integrations → Typebot
2. Configure:
   - Base URL: `http://leguas_typebot_viewer:8082`
   - Bot ID: (copiado do Typebot)

---

### 6.2 Webhook do Typebot Falha ao Chamar Django

**Sintoma:**
```
Bot coleta dados mas não envia para Django
Timeout ou erro 500
```

**Diagnóstico:**
```powershell
# Logs do Typebot
docker compose logs typebot_viewer --tail 50 | Select-String "error|ERROR|timeout"

# Logs do Django
docker compose logs web --tail 50 | Select-String "register-typebot"
```

**Possíveis causas:**

#### Causa 1: URL do webhook incorreta

**ERRADO:**
```
http://localhost:8000/driversapp/api/register-typebot/
```

**CORRETO (dentro do Docker):**
```
http://leguas_web:8000/driversapp/api/register-typebot/
```

#### Causa 2: Timeout muito baixo

**Solução:**
No bloco webhook do Typebot:
- Timeout: 10 segundos (mínimo)
- Retry: 3 tentativas

#### Causa 3: JSON Body malformado

**Correto:**
```json
{
  "nif": "{{nif}}",
  "nome": "{{nome}}",
  "telefone": "{{telefone}}",
  "email": "{{email}}"
}
```

**Verificar:** Variáveis estão sendo preenchidas corretamente (sem `{{}}` vazios).

---

### 6.3 Testar Webhook Manualmente

```powershell
# Teste dentro do container Typebot
docker exec -it leguas_typebot_viewer sh

# Dentro do container:
apk add curl

curl -X POST http://leguas_web:8000/driversapp/api/register-typebot/ \
  -H "Content-Type: application/json" \
  -d '{"nif":"111111111","nome":"Teste","telefone":"+351911111111","email":"teste@test.com"}'

# Deve retornar:
# {"success":true,"driver_id":"111111111","message":"Cadastro recebido com sucesso!"}
```

---

## 7. Comandos Úteis

### 7.1 Verificar Status de Containers

```powershell
# Status de todos os containers
docker compose ps

# Status formatado
docker compose ps --format json | ConvertFrom-Json | Select-Object Name, State, Status | Format-Table

# Verificar saúde (health)
docker compose ps | Select-String "healthy|unhealthy"
```

---

### 7.2 Logs

```powershell
# Logs em tempo real
docker compose logs -f wppconnect_bridge

# Últimas 50 linhas
docker compose logs wppconnect_bridge --tail 50

# Últimos 30 minutos
docker compose logs wppconnect_bridge --since 30m

# Filtrar por palavra-chave
docker compose logs wppconnect_bridge --tail 100 | Select-String "ERROR|error"

# Múltiplos containers
docker compose logs chatwoot_web wppconnect_bridge --tail 50 -f
```

---

### 7.3 Rebuild e Deploy

```powershell
# Rebuild bridge (sem cache)
docker compose build --no-cache wppconnect_bridge

# Parar e remover
docker stop leguas_wppconnect_bridge
docker rm leguas_wppconnect_bridge

# Subir novamente
docker compose up -d wppconnect_bridge
docker start leguas_wppconnect_bridge

# Verificar logs
Start-Sleep -Seconds 5
docker compose logs wppconnect_bridge --tail 30
```

---

### 7.4 Testes de API

#### Chatwoot Webhooks
```powershell
$headers = @{ 'api_access_token' = 'w2w8N98Pv8yqazrHPyqAuwkR' }

# Listar webhooks
Invoke-RestMethod -Uri 'http://localhost:3000/api/v1/accounts/1/webhooks' -Headers $headers

# Listar mensagens de conversa
Invoke-RestMethod -Uri 'http://localhost:3000/api/v1/accounts/1/conversations/11/messages' -Headers $headers
```

#### Django Endpoint
```powershell
$body = '{"nif":"123456789","nome":"Teste","telefone":"+351911111111","email":"teste@test.com"}'

Invoke-RestMethod `
  -Uri 'http://localhost:8000/driversapp/api/register-typebot/' `
  -Method POST `
  -ContentType 'application/json; charset=utf-8' `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

---

### 7.5 Acessar Bash/Shell de Container

```powershell
# Bridge (Node.js - Alpine)
docker exec -it leguas_wppconnect_bridge sh

# Django
docker exec -it leguas_web bash

# Chatwoot
docker exec -it leguas_chatwoot_web bash

# Typebot
docker exec -it leguas_typebot_viewer sh
```

---

### 7.6 Verificar Rede Docker

```powershell
# Inspecionar rede
docker network inspect leguas_network

# Listar IPs de containers
docker network inspect leguas_network | Select-String "Name|IPv4Address"

# Testar conectividade entre containers
docker exec leguas_wppconnect_bridge wget -O- http://leguas_chatwoot_web:3000
```

---

### 7.7 Limpar Sistema Docker

```powershell
# Remover containers parados
docker container prune -f

# Remover imagens não usadas
docker image prune -a -f

# Remover volumes órfãos
docker volume prune -f

# Limpar tudo (CUIDADO!)
docker system prune -a --volumes -f
```

---

## 8. Checklist de Debugging

Quando algo não funciona, siga esta ordem:

### ✅ Passo 1: Verificar Containers
```powershell
docker compose ps
# Todos devem estar "Up" ou "healthy"
```

### ✅ Passo 2: Verificar Logs
```powershell
docker compose logs [container_name] --tail 50
# Procurar por "ERROR", "error", "Exception"
```

### ✅ Passo 3: Verificar Rede
```powershell
docker network inspect leguas_network
# Todos os containers devem estar listados
```

### ✅ Passo 4: Testar Conectividade
```powershell
# Dentro de um container
docker exec -it leguas_wppconnect_bridge sh
wget -O- http://leguas_chatwoot_web:3000
```

### ✅ Passo 5: Verificar Configurações
```powershell
# Chatwoot: Webhooks criados?
# Typebot: Bot publicado?
# Django: Endpoint responde?
```

### ✅ Passo 6: Rebuild se Necessário
```powershell
# Se mudou código:
docker compose build --no-cache [service]
docker stop [container]
docker rm [container]
docker compose up -d [service]
```

---

## 9. Arquitetura de Soluções

### 9.1 Fluxo de Mensagens: WhatsApp → Chatwoot

```
WhatsApp
  ↓
WPPConnect Server (Port 21465)
  ↓
Bridge: Polling /api/leguas_wppconnect/getAllMessagesInChat (2s)
  ↓
Download Media: /api/leguas_wppconnect/downloadMedia
  ↓
Upload to Chatwoot: POST /api/v1/accounts/1/conversations/{id}/messages
  ↓
Chatwoot (mensagem aparece)
```

**Latência:** ~2 segundos

---

### 9.2 Fluxo de Mensagens: Chatwoot → WhatsApp (Texto)

```
Chatwoot (agente envia mensagem)
  ↓
Webhook: message_created → http://leguas_wppconnect_bridge:3500/webhook/chatwoot
  ↓
Bridge: Deduplica (cache)
  ↓
Bridge: Limpa trailing newlines
  ↓
WPPConnect: POST /api/leguas_wppconnect/send-message
  ↓
WhatsApp (mensagem aparece)
```

**Latência:** <1 segundo

---

### 9.3 Fluxo de Mensagens: Chatwoot → WhatsApp (Anexos)

```
Chatwoot (agente envia imagem)
  ↓
⚠️ WEBHOOK NÃO DISPARA (Chatwoot limitation)
  ↓
Bridge: Polling GET /api/v1/accounts/1/conversations/{id}/messages (3s)
  ↓
Bridge: Detecta mensagem nova com anexo (message_type=1, attachments>0)
  ↓
Bridge: Deduplica (mesmo cache do webhook)
  ↓
Download: GET {attachment_url} (com URL replacement localhost→container)
  ↓
Encode: Buffer → Base64
  ↓
Add Data URI Prefix: "data:image/jpeg;base64,{base64}"
  ↓
WPPConnect: POST /api/leguas_wppconnect/send-file-base64
  ↓
WhatsApp (imagem aparece)
```

**Latência:** ~3 segundos

---

## 10. Lições Aprendidas

### 10.1 Docker
- ✅ Sempre use nomes de container em URLs, nunca `localhost`
- ✅ Rebuild com `--no-cache` e recrie container (não apenas restart)
- ✅ Verifique rede: todos devem estar em `leguas_network`

### 10.2 Chatwoot
- ✅ Inbox ≠ Webhook. Webhook precisa ser criado manualmente via API
- ✅ Chatwoot dispara múltiplos eventos (deduplicação necessária)
- ⚠️ Webhook NÃO dispara para mensagens com apenas anexo (use polling)
- ✅ Active Storage usa `localhost` em URLs (substituir por container name)

### 10.3 WPPConnect
- ✅ API exige data URI format: `data:image/jpeg;base64,...`
- ✅ Use `downloadMedia()` não `decryptFile()` para full quality
- ✅ Polling de mensagens a cada 2s é aceitável

### 10.4 Bridge
- ✅ Implementar deduplicação com Set + TTL (10s)
- ✅ Remover trailing newlines do conteúdo
- ✅ Polling é necessário quando webhooks não cobrem todos os casos
- ✅ Logging extensivo é crucial para debugging

### 10.5 Django
- ✅ Sempre use encoding UTF-8 explícito em testes PowerShell
- ✅ Restart container após mudanças em código Python
- ✅ Valide NIF com regex `^\d{9}$`

### 10.6 Typebot
- ✅ Use URLs internas Docker (leguas_web:8000) em webhooks
- ✅ Timeout mínimo 10s para chamadas API
- ✅ Teste bot antes de publicar
- ✅ Configure automação no Chatwoot para trigger

---

## 11. Referências

- [Chatwoot API Documentation](https://www.chatwoot.com/developers/api/)
- [WPPConnect Documentation](https://wppconnect.io/docs/)
- [Typebot Documentation](https://docs.typebot.io/)
- [Docker Compose Networking](https://docs.docker.com/compose/networking/)

---

**Mantido por:** Sistema Léguas Franzinas  
**Última atualização:** 2025-02-26  
**Status:** Produção - 100% Funcional
