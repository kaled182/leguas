# 🚀 Início Rápido - Omnichannel

## ✅ Status Atual

**Infraestrutura**: ✅ Todos os containers rodando!

```
✓ Chatwoot Database (PostgreSQL com pgvector)
✓ Chatwoot Redis
✓ Chatwoot Web Application
✓ Chatwoot Sidekiq Worker
✓ Typebot Database (PostgreSQL)
✓ Typebot Builder
✓ Typebot Viewer
```

---

## 🌐 URLs de Acesso

### Chatwoot - Central de Atendimento
**URL**: http://localhost:3000

**Primeiro Acesso**:
1. Acesse a URL
2. Clique em "Criar conta"
3. Preencha os dados:
   - **Nome**: Seu nome
   - **Email**: admin@leguasfranzinas.pt (ou outro)
   - **Senha**: Escolha uma senha segura
4. Clique em "Criar"

---

### Typebot Builder - Criar Fluxos de Bot
**URL**: http://localhost:8081

**Primeiro Acesso**:
1. Acesse a URL
2. Clique em "Sign Up"
3. Preencha:
   - **Email**: admin@leguasfranzinas.pt
   - **Senha**: Escolha uma senha segura
4. Verifique seu email (se necessário)
5. Crie um workspace: "Léguas Franzinas"

---

### Typebot Viewer - Executar Bots
**URL**: http://localhost:8082

Esta interface é usada automaticamente pelos bots publicados. Não precisa acessar diretamente.

---

## 📋 Próximas Etapas

### 1. Configurar Chatwoot (5 minutos)

1. **Acesse**: http://localhost:3000
2. **Login** com as credenciais que você criou
3. **Navegue**: Configurações → Inboxes
4. **Criar Inbox API**:
   - Clique em "+ Add Inbox"
   - Selecione "API"
   - Nome: "WhatsApp Leguas"
   - Clique em "Create"
5. **Copiar credenciais**:
   - **Inbox ID**: Anote este número (ex: 1, 2, 3...)
   - **Account ID**: Vá em Settings → Account Settings, copie o Account ID
   - **API Token**: Vá em Settings → Personal Access Tokens, crie um token

### 2. Configurar WPPConnect Bridge (2 minutos)

Edite o arquivo [docker-compose.yml](../docker-compose.yml):

```yaml
wppconnect_bridge:
  # ... outras configurações ...
  environment:
    - WPPCONNECT_URL=http://leguas_wppconnect:21465
    - WPPCONNECT_TOKEN=seu_token_wppconnect
    - CHATWOOT_URL=http://leguas_chatwoot_web:3000
    - CHATWOOT_API_TOKEN=SEU_TOKEN_AQUI     # ← Cole aqui
    - CHATWOOT_ACCOUNT_ID=SEU_ACCOUNT_ID     # ← Cole aqui
    - CHATWOOT_INBOX_ID=SEU_INBOX_ID         # ← Cole aqui
```

Depois reinicie:
```bash
docker compose up -d wppconnect_bridge
```

### 3. Configurar Typebot (10 minutos)

1. **Acesse**: http://localhost:8081
2. **Login** com suas credenciais
3. **Criar Bot**:
   - Clique em "+ Create a typebot"
   - Nome: "Cadastro Motorista"
   - Template: "Blank"

4. **Design do Fluxo** (consulte [OMNICHANNEL_CHECKLIST.md](OMNICHANNEL_CHECKLIST.md) para detalhes completos):
   - Adicione blocos de texto e input
   - Colete: NIF, nome, telefone, email
   - Upload de documentos: Carta de Condução, Comprovante de Residência
   - Webhook para Django

5. **Integração Chatwoot**:
   - Settings → Integrations → Add Chatwoot
   - Base URL: `http://leguas_chatwoot_web:3000`
   - Account ID: (copiado na etapa 1)
   - Inbox ID: (copiado na etapa 1)
   - API Token: (copiado na etapa 1)
   - Testar conexão

6. **Publicar**: Clique em "Publish"

### 4. Configurar Automação no Chatwoot (3 minutos)

1. **Acesse**: http://localhost:3000
2. **Navegue**: Settings → Automations
3. **Criar Regra**:
   - Nome: "Direcionar para Typebot"
   - Evento: "Message Created"
   - Condições: "Message Type" is "incoming"
   - Ações: "Assign a team or agent" → Typebot
4. **Salvar**

### 5. Configurar Webhook no WPPConnect (2 minutos)

Edite [docker-compose.yml](../docker-compose.yml) na seção `wppconnect`:

```yaml
wppconnect:
  # ... outras configurações ...
  environment:
    - WEBHOOK_GLOBAL_ENABLED=true
    - WEBHOOK_GLOBAL_URL=http://leguas_wppconnect_bridge:3500/webhook/wppconnect
    - WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=true
```

Reinicie:
```bash
docker compose restart leguas_wppconnect
```

### 6. Implementar Endpoint Django (15 minutos)

Crie o endpoint em `drivers_app/views.py`:

```python
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

@csrf_exempt
@require_http_methods(["POST"])
def register_driver_typebot(request):
    try:
        data = json.loads(request.body)
        
        # Validações
        nif = data.get('nif')
        nome = data.get('nome')
        telefone = data.get('telefone')
        email = data.get('email')
        
        if not all([nif, nome, telefone, email]):
            return JsonResponse({
                'success': False,
                'error': 'Todos os campos são obrigatórios'
            }, status=400)
        
        # Verificar NIF duplicado
        from .models import Driver
        if Driver.objects.filter(nif=nif).exists():
            return JsonResponse({
                'success': False,
                'error': 'NIF já cadastrado'
            }, status=400)
        
        # Criar motorista
        driver = Driver.objects.create(
            nif=nif,
            nome=nome,
            telefone=telefone,
            email=email,
            status='pending',
            carta_conducao_url=data.get('carta_conducao_url', ''),
            comprovante_residencia_url=data.get('comprovante_residencia_url', '')
        )
        
        return JsonResponse({
            'success': True,
            'driver_id': driver.id,
            'message': 'Motorista cadastrado com sucesso'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
```

Adicione a rota em `drivers_app/urls.py`:

```python
urlpatterns = [
    # ... outras rotas ...
    path('api/register-typebot/', views.register_driver_typebot, name='register_driver_typebot'),
]
```

Reinicie o Django:
```bash
docker compose restart leguas_web
```

---

## 🧪 Testar o Sistema

### Teste Básico de Conectividade

```powershell
# 1. Verificar containers
docker compose ps

# 2. Testar Chatwoot
curl http://localhost:3000

# 3. Testar Typebot Builder
curl http://localhost:8081

# 4. Testar Bridge (após configurar)
curl http://localhost:3500/health
```

### Teste End-to-End

1. **Enviar mensagem** no WhatsApp: "Oi"
2. **Verificar** se aparece no Chatwoot
3. **Verificar** se Typebot responde automaticamente
4. **Completar** o fluxo de cadastro:
   - Informar NIF
   - Informar nome
   - Informar telefone
   - Informar email
   - Enviar foto da carta de condução
   - Enviar comprovante de residência
5. **Verificar** confirmação de sucesso
6. **Acessar** Django Admin: http://localhost:8000/admin
7. **Verificar** motorista criado

---

## 📊 Monitoramento

### Verificar Logs

```powershell
# Todos os serviços do omnichannel
docker compose logs -f chatwoot_web typebot_builder wppconnect_bridge

# Apenas Chatwoot
docker compose logs -f chatwoot_web

# Apenas Typebot
docker compose logs -f typebot_builder

# Apenas Bridge
docker compose logs -f wppconnect_bridge
```

### Verificar Uso de Recursos

```powershell
docker stats
```

### Verificar Health Checks

```powershell
docker compose ps
```

---

## 🔧 Comandos Úteis

### Reiniciar Serviços

```powershell
# Todos os serviços do omnichannel
docker compose restart chatwoot_web chatwoot_worker typebot_builder typebot_viewer wppconnect_bridge

# Apenas um serviço
docker compose restart chatwoot_web
```

### Parar Serviços

```powershell
# Parar todos
docker compose stop chatwoot_web chatwoot_worker chatwoot_db chatwoot_redis typebot_builder typebot_viewer typebot_db wppconnect_bridge

# Parar apenas um
docker compose stop chatwoot_web
```

### Iniciar Serviços

```powershell
# Iniciar todos
docker compose up -d chatwoot_db chatwoot_redis chatwoot_web chatwoot_worker typebot_db typebot_builder typebot_viewer

# Com o bridge (após configurar)
docker compose up -d wppconnect_bridge
```

### Acessar Console Rails (Chatwoot)

```powershell
docker compose exec chatwoot_web bundle exec rails console
```

### Executar Migrations (Chatwoot)

```powershell
docker compose run --rm chatwoot_web bundle exec rails db:migrate
```

---

## 🐛 Troubleshooting

### Chatwoot não carrega

```powershell
# Verificar logs
docker compose logs chatwoot_web --tail 50

# Verificar database
docker compose exec chatwoot_db psql -U chatwoot_user -d chatwoot -c "\dt"

# Re-executar migrations
docker compose run --rm chatwoot_web bundle exec rails db:migrate
```

### Typebot não conecta ao Chatwoot

1. Verifique os logs: `docker compose logs typebot_builder`
2. Verifique se o Account ID, Inbox ID e API Token estão corretos
3. Teste a conexão no Typebot: Settings → Integrations → Chatwoot → Test Connection

### Bridge não recebe mensagens

```powershell
# Verificar logs
docker compose logs wppconnect_bridge

# Verificar webhook no WPPConnect
docker compose logs leguas_wppconnect | Select-String "webhook"

# Testar health endpoint
curl http://localhost:3500/health
```

### Mensagens não chegam ao WhatsApp

1. Verifique se o WPPConnect está conectado
2. Verifique os logs do bridge: `docker compose logs wppconnect_bridge`
3. Verifique o webhook do Chatwoot na Inbox: deve apontar para `http://leguas_wppconnect_bridge:3500/webhook/chatwoot`

---

## 📚 Documentação Completa

- **Setup Detalhado**: [OMNICHANNEL_SETUP.md](OMNICHANNEL_SETUP.md)
- **Checklist de Configuração**: [OMNICHANNEL_CHECKLIST.md](OMNICHANNEL_CHECKLIST.md)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
- **Bridge**: [wppconnect-chatwoot-bridge/README.md](../wppconnect-chatwoot-bridge/README.md)

---

## ⚡ Script Automatizado

Execute o script de setup:

```powershell
.\scripts\setup-omnichannel.ps1
```

Este script:
- ✅ Verifica Docker
- ✅ Inicia containers
- ✅ Verifica health checks
- ✅ Exibe URLs de acesso
- ✅ Lista próximos passos
- ✅ Opção para ver logs em tempo real

---

**Última atualização**: 10/02/2026

🎉 **Parabéns! Seu sistema de omnichannel está pronto!**
