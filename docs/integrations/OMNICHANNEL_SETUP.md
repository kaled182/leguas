# 🎯 Omnichannel - Guia de Implementação Completo
**Leguas Franzinas - Chatwoot + Typebot + WPPConnect**

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Instalação](#instalação)
- [Configuração Passo a Passo](#configuração-passo-a-passo)
- [Fluxo de Dados](#fluxo-de-dados)
- [Integração com Sistema Leguas](#integração-com-sistema-leguas)
- [Troubleshooting](#troubleshooting)

---

## 🔍 Visão Geral

Sistema completo de atendimento omnichannel que permite:
- ✅ Receber mensagens do WhatsApp no Chatwoot
- ✅ Automatizar cadastro de motoristas via Typebot
- ✅ Integrar dados coletados ao sistema Léguas
- ✅ Centralizar atendimento em uma única plataforma

### Componentes

| Componente | Função | Porta | Container |
|------------|--------|-------|-----------|
| **WPPConnect** | Conexão WhatsApp | 21465 | `leguas_wppconnect` |
| **Bridge** | Middleware WPP↔Chatwoot | 3500 | `leguas_wppconnect_bridge` |
| **Chatwoot** | Central de atendimento | 3000 | `leguas_chatwoot_web` |
| **Typebot Builder** | Criação de fluxos | 8081 | `leguas_typebot_builder` |
| **Typebot Viewer** | Execução de bots | 8082 | `leguas_typebot_viewer` |

---

## 🏗️ Arquitetura

```
┌─────────────────────┐
│   WhatsApp User     │
│   (Motorista)       │
└──────────┬──────────┘
           │ Envia: "Oi, quero me cadastrar"
           ▼
┌─────────────────────┐
│   WPPConnect        │
│   (Porta 21465)     │
└──────────┬──────────┘
           │ Webhook
           ▼
┌─────────────────────┐
│   Bridge            │◄─────┐
│   (Porta 3500)      │      │
└──────────┬──────────┘      │
           │ API REST         │
           ▼                  │
┌─────────────────────┐      │
│   Chatwoot          │      │
│   (Porta 3000)      │      │
│   ┌───────────────┐ │      │
│   │ Inbox API     │ │      │
│   │ (WhatsApp)    │ │      │
│   └───────┬───────┘ │      │
│           ▼         │      │
│   ┌───────────────┐ │      │
│   │ Automation    │ │      │
│   │ Rule          │ │      │
│   └───────┬───────┘ │      │
└───────────┼─────────┘      │
            │                │
            ▼                │
┌─────────────────────┐      │
│   Typebot           │      │
│   (Porta 8082)      │      │
│   ┌───────────────┐ │      │
│   │ 1. Boas Vindas│ │      │
│   │ 2. Pede NIF   │ │      │
│   │ 3. Valida NIF │ │      │
│   │ 4. Pede CNH   │ │      │
│   │ 5. Pede Docs  │ │      │
│   └───────┬───────┘ │      │
└───────────┼─────────┘      │
            │                │
            ▼                │
┌─────────────────────┐      │
│   Webhook           │      │
│   POST /api/        │      │
│   drivers/register  │      │
└──────────┬──────────┘      │
           │                 │
           ▼                 │
┌─────────────────────┐      │
│   Leguas Web        │      │
│   (Django)          │      │
│   ┌───────────────┐ │      │
│   │ Valida Dados  │ │      │
│   │ Salva no BD   │ │      │
│   │ Envia Email   │ │      │
│   └───────┬───────┘ │      │
└───────────┼─────────┘      │
            │                │
            │ Resposta       │
            └────────────────┘
            (via Chatwoot → WhatsApp)
```

---

## 🚀 Instalação

### Passo 1: Subir os Containers

```bash
cd d:\app.leguasfranzinas.pt\app.leguasfranzinas.pt

# Subir todos os serviços
docker compose up -d

# Verificar status
docker compose ps

# Acompanhar logs
docker compose logs -f chatwoot_web typebot_builder wppconnect_bridge
```

### Passo 2: Aguardar Inicialização

Os serviços levam alguns minutos para inicializar:

```bash
# Chatwoot (aguardar healthcheck)
docker logs leguas_chatwoot_web -f

# Typebot
docker logs leguas_typebot_builder -f

# Bridge
docker logs leguas_wppconnect_bridge -f
```

**Indicadores de sucesso:**
- Chatwoot: `Listening on http://0.0.0.0:3000`
- Typebot: `ready - started server on 0.0.0.0:3000`
- Bridge: `🚀 WPPConnect-Chatwoot Bridge started on port 3500`

---

## ⚙️ Configuração Passo a Passo

### FASE 1: Configurar Chatwoot

#### 1.1 Acessar Chatwoot
```
URL: http://localhost:3000
```

#### 1.2 Criar Conta Admin
1. Clique em **"Create new account"**
2. Preencha:
   - **Name**: Leguas Franzinas
   - **Email**: admin@leguasfranzinas.pt
   - **Password**: (escolha uma senha forte)

#### 1.3 Criar Inbox API (WhatsApp)
1. Vá em **Settings → Inboxes → Add Inbox**
2. Escolha **API**
3. Configure:
   - **Channel Name**: WhatsApp Leguas
   - **Webhook URL**: `http://leguas_wppconnect_bridge:3500/webhook/chatwoot`

4. **Copie o Inbox ID e API Token** (aparecerá na tela)

#### 1.4 Atualizar Bridge com Credenciais

Edite o docker-compose.yml:

```yaml
wppconnect_bridge:
  environment:
    - CHATWOOT_ACCOUNT_ID=1  # Normalmente é 1
    - CHATWOOT_INBOX_ID=1    # O ID que apareceu ao criar inbox
    - CHATWOOT_API_TOKEN=xxxxx  # O token gerado
```

Reinicie o bridge:
```bash
docker compose restart wppconnect_bridge
```

#### 1.5 Criar Regra de Automação

1. **Settings → Automations → Add Automation**
2. Configure:
   - **Name**: Encaminhar para Typebot
   - **Event**: Message Created
   - **Conditions**:
     - Inbox = WhatsApp Leguas
     - Message Type = incoming
   - **Actions**:
     - Assign Agent → Typebot Bot
     - Add Label → "bot-ativo"

### FASE 2: Configurar Typebot

#### 2.1 Acessar Typebot Builder
```
URL: http://localhost:8081
```

#### 2.2 Criar Conta
1. **Email**: admin@leguasfranzinas.pt
2. **Password**: (mesma do Chatwoot ou outra)

#### 2.3 Criar Workspace
- **Name**: Léguas Franzinas

#### 2.4 Criar Bot de Cadastro

1. **Create new typebot → Start from scratch**
2. **Name**: Cadastro Motorista

**Estrutura do Fluxo:**

```
┌─────────────────────────────────────────┐
│ START                                   │
│ ↓                                       │
│ [Mensagem] Boas-vindas                  │
│ "Olá! 👋 Bem-vindo ao cadastro..."      │
│ ↓                                       │
│ [Input] Pedir NIF                       │
│ "Por favor, digite seu NIF:"            │
│ Variável: {{nif}}                       │
│ ↓                                       │
│ [Condition] Validar NIF                 │
│ Se {{nif}} matches ^\d{9}$              │
│ ├─ Sim → Continuar                      │
│ └─ Não → "NIF inválido, tente novamente"│
│ ↓                                       │
│ [Input] Pedir Nome Completo             │
│ "Qual seu nome completo?"               │
│ Variável: {{nome}}                      │
│ ↓                                       │
│ [Input] Pedir Telefone                  │
│ "Qual seu telefone de contato?"         │
│ Variável: {{telefone}}                  │
│ ↓                                       │
│ [Input] Pedir Email                     │
│ "Qual seu email?"                       │
│ Variável: {{email}}                     │
│ ↓                                       │
│ [File Upload] Upload CNH                │
│ "Envie foto da CNH (frente)"            │
│ Variável: {{cnh_frente}}                │
│ ↓                                       │
│ [File Upload] Upload CNH Verso          │
│ "Envie foto da CNH (verso)"             │
│ Variável: {{cnh_verso}}                 │
│ ↓                                       │
│ [File Upload] Comprovante Residência    │
│ "Envie comprovante de residência"       │
│ Variável: {{comprovante}}               │
│ ↓                                       │
│ [Webhook] Enviar para Leguas            │
│ URL: http://leguas_web:8000/api/...     │
│ Method: POST                            │
│ Body: {                                 │
│   "nif": "{{nif}}",                     │
│   "nome": "{{nome}}",                   │
│   "telefone": "{{telefone}}",           │
│   "email": "{{email}}",                 │
│   "cnh_frente": "{{cnh_frente}}",       │
│   "cnh_verso": "{{cnh_verso}}",         │
│   "comprovante": "{{comprovante}}"      │
│ }                                       │
│ ↓                                       │
│ [Condition] Verificar resposta          │
│ Se {{webhook.status}} == "success"      │
│ ├─ Sim → "✅ Cadastro realizado!"       │
│ └─ Não → "❌ Erro: {{webhook.message}}" │
│ ↓                                       │
│ END                                     │
└─────────────────────────────────────────┘
```

#### 2.5 Configurar Integração Chatwoot

1. No Typebot Builder, vá em **Settings → Integrations**
2. Adicione **Chatwoot**:
   - **Chatwoot URL**: `http://leguas_chatwoot_web:3000`
   - **Account ID**: 1
   - **Inbox ID**: (o ID da inbox WhatsApp)
   - **API Token**: (token copiado anteriormente)

#### 2.6 Publicar Bot

1. Clique em **Publish**
2. Copie a **Public URL** (será algo como `http://localhost:8082/typebot/xxxxx`)

### FASE 3: Conectar WPPConnect ao Bridge

#### 3.1 Configurar Webhook no WPPConnect

O WPPConnect precisa enviar mensagens para o bridge. Edite o docker-compose.yml:

```yaml
wppconnect:
  environment:
    WEBHOOK_GLOBAL_ENABLED: "true"
    WEBHOOK_GLOBAL_URL: "http://leguas_wppconnect_bridge:3500/webhook/wppconnect"
    WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS: "true"
```

Reinicie:
```bash
docker compose restart wppconnect
```

#### 3.2 Testar Fluxo Completo

**Envie uma mensagem no WhatsApp:**
```
Oi
```

**O que deve acontecer:**
1. ✅ WPPConnect recebe a mensagem
2. ✅ Bridge encaminha para Chatwoot
3. ✅ Chatwoot cria conversa
4. ✅ Automação aciona Typebot
5. ✅ Typebot responde com boas-vindas

**Verificar logs:**
```bash
# Bridge
docker logs leguas_wppconnect_bridge -f

# Chatwoot
docker logs leguas_chatwoot_web --tail=50

# WPPConnect
docker logs leguas_wppconnect --tail=50
```

---

## 🔗 Integração com Sistema Leguas

### Criar Endpoint de Cadastro

Adicione em `drivers_app/views.py`:

```python
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import json
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def register_driver_typebot(request):
    """
    Endpoint para receber cadastros do Typebot.
    URL: /api/drivers/register-typebot/
    """
    try:
        # Parse JSON
        data = json.loads(request.body)
        
        logger.info(f"[Typebot] Cadastro recebido: {data.get('nome')}, NIF: {data.get('nif')}")
        
        # Validações
        required_fields = ['nif', 'nome', 'telefone', 'email']
        missing = [f for f in required_fields if not data.get(f)]
        
        if missing:
            return JsonResponse({
                'status': 'error',
                'message': f'Campos obrigatórios faltando: {", ".join(missing)}'
            }, status=400)
        
        # Verificar se NIF já existe
        from drivers_app.models import Driver
        if Driver.objects.filter(nif=data['nif']).exists():
            return JsonResponse({
                'status': 'error',
                'message': 'NIF já cadastrado no sistema'
            }, status=409)
        
        # Criar motorista
        driver = Driver.objects.create(
            nif=data['nif'],
            nome=data['nome'],
            telefone=data['telefone'],
            email=data['email'],
            status='pending',  # Pendente de aprovação
            origem_cadastro='typebot'
        )
        
        # Salvar documentos (se enviados)
        if data.get('cnh_frente'):
            driver.cnh_frente_url = data['cnh_frente']
        if data.get('cnh_verso'):
            driver.cnh_verso_url = data['cnh_verso']
        if data.get('comprovante'):
            driver.comprovante_url = data['comprovante']
        
        driver.save()
        
        # Enviar email de confirmação (opcional)
        # send_welcome_email(driver.email, driver.nome)
        
        logger.info(f"[Typebot] Motorista cadastrado com sucesso: ID {driver.id}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Cadastro realizado com sucesso! Aguarde aprovação.',
            'driver_id': driver.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'JSON inválido'
        }, status=400)
    
    except Exception as e:
        logger.error(f"[Typebot] Erro ao cadastrar: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro interno: {str(e)}'
        }, status=500)
```

### Adicionar Rota

Em `drivers_app/urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    # ... suas rotas existentes ...
    
    path('api/drivers/register-typebot/', views.register_driver_typebot, name='register_driver_typebot'),
]
```

### Reiniciar Django

```bash
docker compose restart web
```

### Configurar Webhook no Typebot

No bloco **Webhook** do Typebot:

```
URL: http://leguas_web:8000/api/drivers/register-typebot/
Method: POST
Headers:
  Content-Type: application/json
Body:
{
  "nif": "{{nif}}",
  "nome": "{{nome}}",
  "telefone": "{{telefone}}",
  "email": "{{email}}",
  "cnh_frente": "{{cnh_frente}}",
  "cnh_verso": "{{cnh_verso}}",
  "comprovante": "{{comprovante}}"
}
```

---

## 🔍 Troubleshooting

### Bridge não conecta ao Chatwoot

**Erro:**
```
Error in getOrCreateContact: 401 Unauthorized
```

**Solução:**
1. Verificar se `CHATWOOT_API_TOKEN` está correto
2. Verificar se Account ID e Inbox ID estão corretos
3. Testar credenciais:
```bash
curl -X GET http://localhost:3000/api/v1/accounts/1/inboxes \
  -H "api_access_token: SEU_TOKEN"
```

### Mensagens não chegam ao Chatwoot

**Verificar:**
1. Webhook configurado no WPPConnect:
```bash
docker exec leguas_wppconnect cat /usr/src/app/.env | grep WEBHOOK
```

2. Logs do bridge:
```bash
docker logs leguas_wppconnect_bridge -f
```

3. Testar bridge diretamente:
```bash
curl -X POST http://localhost:3500/webhook/wppconnect \
  -H "Content-Type: application/json" \
  -d '{
    "event": "onMessage",
    "data": {
      "from": "5511999999999@c.us",
      "body": "Teste",
      "fromMe": false,
      "isGroupMsg": false
    }
  }'
```

### Typebot não responde

**Verificar:**
1. Automação ativa no Chatwoot
2. Bot publicado no Typebot
3. Integração Chatwoot configurada
4. Logs do Typebot:
```bash
docker logs leguas_typebot_viewer -f
```

### Webhook não chega no Django

**Verificar:**
1. Endpoint acessível:
```bash
docker exec leguas_typebot_viewer curl http://leguas_web:8000/api/drivers/register-typebot/
```

2. Logs do Django:
```bash
docker logs leguas_web -f
```

3. CSRF desabilitado no endpoint (`@csrf_exempt`)

---

## 📊 Monitoramento

### Verificar Saúde dos Serviços

```bash
# Todos os serviços
docker compose ps

# Health checks
curl http://localhost:3500/health  # Bridge
curl http://localhost:3000/        # Chatwoot
curl http://localhost:8081/        # Typebot Builder
```

### Logs Importantes

```bash
# Bridge (fluxo completo)
docker logs leguas_wppconnect_bridge -f

# Chatwoot (conversas)
docker logs leguas_chatwoot_web --tail=100 -f

# Typebot (execução de bots)
docker logs leguas_typebot_viewer --tail=100 -f

# Django (cadastros)
docker logs leguas_web --tail=100 -f
```

---

## 🎯 Checklist de Deploy

- [ ] Todos containers rodando (`docker compose ps`)
- [ ] Chatwoot acessível em http://localhost:3000
- [ ] Typebot Builder acessível em http://localhost:8081
- [ ] Bridge healthy (`curl http://localhost:3500/health`)
- [ ] WPPConnect conectado ao WhatsApp
- [ ] Inbox API criada no Chatwoot
- [ ] API Token configurado no bridge
- [ ] Webhook WPPConnect → Bridge configurado
- [ ] Automação Chatwoot → Typebot ativa
- [ ] Bot Typebot publicado
- [ ] Integração Typebot ↔ Chatwoot configurada
- [ ] Endpoint Django criado e testado
- [ ] Webhook Typebot → Django configurado
- [ ] Teste end-to-end realizado (enviar "Oi" no WhatsApp)

---

## 📚 URLs de Acesso

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| Chatwoot | http://localhost:3000 | admin@leguasfranzinas.pt |
| Typebot Builder | http://localhost:8081 | admin@leguasfranzinas.pt |
| Typebot Viewer | http://localhost:8082 | (público) |
| Bridge API | http://localhost:3500/health | - |
| Django Admin | http://localhost:8000/admin | (existente) |

---

**Criado em:** 10 de Fevereiro de 2026  
**Versão:** 1.0  
**Equipe:** Léguas Franzinas
