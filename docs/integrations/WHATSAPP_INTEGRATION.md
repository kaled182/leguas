# Integração WhatsApp - WPPConnect Server

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Configuração](#configuração)
- [Fluxo de Autenticação](#fluxo-de-autenticação)
- [Funcionalidades](#funcionalidades)
- [Problemas Resolvidos](#problemas-resolvidos)
- [Estrutura de Arquivos](#estrutura-de-arquivos)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)

---

## 🔍 Visão Geral

Sistema de integração com WhatsApp através do **WPPConnect Server**, permitindo gerenciamento de sessão, envio de mensagens e monitoramento de status em tempo real.

### Componentes Principais

- **Backend**: Django com API REST
- **Frontend**: JavaScript vanilla com Tailwind CSS e Lucide icons
- **WhatsApp Server**: WPPConnect Server (Docker)
- **Persistência**: Armazenamento de tokens e configurações no banco de dados

---

## 🏗️ Arquitetura

```
┌─────────────────┐
│   Navegador     │
│  (Dashboard)    │
└────────┬────────┘
         │
         │ HTTP/AJAX (5s polling)
         ▼
┌─────────────────┐
│  Django Web     │
│  (views.py)     │
└────────┬────────┘
         │
         │ Python SDK
         ▼
┌─────────────────┐
│ WPPConnect API  │
│  (Helper Class) │
└────────┬────────┘
         │
         │ REST API (Timeout: 60-90s)
         ▼
┌─────────────────┐
│  WPPConnect     │
│  Server (Docker)│
│  Auto-close: 3m │
└─────────────────┘
```

> **Nota Histórica:** O sistema originalmente usava Evolution API, mas foi migrado para WPPConnect Server.
> Os nomes dos campos no modelo (`whatsapp_evolution_api_url`, `whatsapp_evolution_api_key`) são legado dessa migração.

---

## ⚙️ Configuração

### Docker Compose (docker-compose.yml)

```yaml
wppconnect:
  image: wppconnect/server-cli:latest
  container_name: leguas_wppconnect
  restart: unless-stopped
  ports:
    - "21465:21465"
  environment:
    SERVER_PORT: 21465
    SECRET_KEY: "THISISMYSECURETOKEN"
    TOKEN: "VwfSzDglRI5jVAQTmmh5hZ8YZh_qsmqCcldJ3tBLA9g"
    DEBUG: "false"
    DEL_INSTANCE: "false"
    AUTO_CLOSE_INTERVAL: "300000"  # ⚠️ CRÍTICO: 5 min (em ms)
    CONFIG_SESSION_PHONE_CLIENT: "Chrome"
    CONFIG_SESSION_PHONE_NAME: "Leguas"
    WEBHOOK_GLOBAL_ENABLED: "false"
    LOG_LEVEL: "ERROR"
    STORE_MESSAGES: "true"
    STORE_CONTACTS: "true"
    STORE_CHATS: "true"
```

**⚠️ Configuração Crítica:**
- `AUTO_CLOSE_INTERVAL: "300000"` - Tempo máximo que o WPPConnect aguarda autenticação após ler QR Code (5 minutos)
- Valor padrão (60s) era insuficiente e causava erro `qrReadError`

### Configuração Django (SystemConfiguration)

Campos no modelo:
- `whatsapp_enabled` - Habilita/desabilita serviço
- `whatsapp_evolution_api_url` - URL do WPPConnect (ex: `http://leguas_wppconnect:21465`)
- `whatsapp_instance_name` - Nome da instância/sessão (ex: `leguas_wppconnect`)
- `whatsapp_evolution_api_key` - Token de autenticação

### Helper API (system_config/whatsapp_helper.py)

```python
DEFAULT_TIMEOUT = 60  # Timeout padrão aumentado para 60s

class WhatsAppWPPConnectAPI:
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        # Timeout maior para operações de start/close de sessão
        timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
        if "start" in endpoint or "close" in endpoint or "logout" in endpoint:
            timeout = max(timeout, 90)  # 90 segundos para operações de sessão
```

**⚠️ Timeouts Configurados:**
- Requisições normais: **60 segundos**
- Operações de start/close/logout: **90 segundos**
- Auto-close WPPConnect: **180 segundos** (3 minutos - limite do servidor)

---

## 🔐 Fluxo de Autenticação

### 1. Inicialização da Página

```javascript
// Após 1 segundo do carregamento da página
setTimeout(async () => {
    // 1. Verifica status da sessão
    const data = await callEndpoint(endpoints.status, { method: 'GET' });
    
    // 2. Detecta se está desconectado
    const isConnected = data.session && (
        data.session.connected === true || 
        data.session.status === 'connected' ||
        data.session.status === 'isLogged'
    );
    
    // 3. Se desconectado, gera QR Code automaticamente
    if (!isConnected) {
        await startSession();  // Inicia sessão e obtém QR Code
    }
}, 1000);
```

### 2. Leitura do QR Code

**Backend (views.py):**
```python
def whatsapp_start_session(request):
    def _start(api: WhatsAppWPPConnectAPI):
        # wait_connection=False para evitar timeout
        # O polling frontend detectará quando conectar
        payload = api.create_instance(
            wait_qrcode=True,      # Aguarda QR Code ser gerado
            wait_connection=False, # NÃO aguarda conexão (evita timeout)
            webhook=""
        )
        return JsonResponse({
            "success": True,
            "qrcode": qrcode,
            "pairingCode": pairing,
            "raw": payload,
            "status": state,
        })
```

**Estados do WPPConnect:**
- `notLogged` → Aguardando leitura do QR Code
- `qrReadSuccess` → QR lido, aguardando confirmação no celular
- `inChat` → Conectando
- `isLogged` → ✅ **Totalmente conectado e autenticado**

### 3. Polling e Auto-Reload

```javascript
// Polling a cada 5 segundos
let lastStatus = null;
let consecutiveConnected = 0;

setInterval(async () => {
    const data = await callEndpoint(endpoints.status, { method: 'GET' });
    const currentStatus = data.session.status;
    const isFullyConnected = data.session.connected === true || 
                            currentStatus === 'isLogged';
    
    // Só recarrega após 2 verificações consecutivas (10s total)
    if (isFullyConnected && lastStatus !== 'isLogged') {
        consecutiveConnected++;
        if (consecutiveConnected >= 2) {
            setTimeout(() => window.location.reload(), 1500);
        }
    }
}, 5000);
```

**Motivo do delay de 2 verificações:**
- Evita recarregamentos prematuros durante estados transitórios
- Garante que a sessão está estável antes de atualizar interface

---

## 🎯 Funcionalidades

### 1. Dashboard WhatsApp (whatsapp_dashboard.html)

**Seção: Configurações do Serviço** (Colapsável)
- Gerenciar URL, instância e token
- Botão "Estado do serviço" (liga/desliga)
- Ícone dinâmico: `power` (ativo) / `power-off` (inativo)
- Animação de colapso com `maxHeight` CSS transition

**Seção: QR Code / Código de Pareamento** (Visibilidade Inteligente)
- **Oculta automaticamente** quando conectado
- **Mostra automaticamente** quando desconectado
- Geração automática ao carregar página se necessário
- Botões: "Iniciar sessão", "Atualizar QR"

**Seção: Informações da Sessão** (Visibilidade Inteligente)
- **Mostra automaticamente** quando conectado
- **Oculta automaticamente** quando desconectado
- Exibe: telefone conectado, status, dispositivo, plataforma

**Seção: Ações Rápidas**
- Atualizar status
- Desconectar sessão
- Fechar sessão (remove dados locais)

**Seção: Enviar Mensagem de Teste**
- Campo de número de destinatário
- Campo de mensagem
- Validação e envio

### 2. Funções JavaScript Principais

```javascript
// Renderiza status com badge colorido
renderStatus(session)
  ├─ Conectado: bg-emerald (verde)
  ├─ Conectando: bg-amber (amarelo) + spinner
  └─ Desconectado: bg-gray (cinza)

// Atualiza informações da sessão
updateSessionInfo(session)
  ├─ Mostra telefone, status, dispositivo
  └─ Controla visibilidade das seções

// Inicia sessão e obtém QR Code
startSession()
  ├─ POST /system/whatsapp/start/
  ├─ Renderiza QR Code
  └─ Tenta obter QR adicional se necessário

// Atualiza status manualmente
refreshStatus()
  └─ GET /system/whatsapp/status/

// Atualiza QR Code manualmente  
refreshQr()
  └─ GET /system/whatsapp/qrcode/

// Desconecta sessão
logoutSession()
  └─ POST /system/whatsapp/logout/

// Fecha sessão completamente
closeSession()
  └─ POST /system/whatsapp/close/

// Envia mensagem de teste
sendTestMessage()
  └─ POST /system/whatsapp/send-test/
```

### 3. Tratamento de Erros Melhorado

**Backend (_whatsapp_response):**
```python
def _whatsapp_response(callback):
    try:
        return callback(api)
    except requests.HTTPError as exc:
        status_code = exc.response.status_code
        error_msg = f"Erro HTTP {status_code} na API WPPConnect"
        try:
            error_detail = exc.response.json()
            error_msg += f": {error_detail}"
        except Exception:
            error_msg += f": {exc.response.text}"
        
        logger.warning("[WhatsApp] %s", error_msg)
        return JsonResponse({
            "success": False, 
            "message": error_msg, 
            "status_code": status_code
        }, status=status_code)  # Retorna código HTTP correto
```

**Frontend (callEndpoint):**
```javascript
async function callEndpoint(url, options) {
    console.log(`[WhatsApp] Chamando endpoint: ${url}`, options);
    const response = await fetch(url, ...);
    const data = await response.json();
    console.log(`[WhatsApp] Resposta de ${url}:`, {
        status: response.status, 
        ok: response.ok, 
        data
    });
    
    if (!response.ok || data.success === false) {
        const message = data?.message || 'Falha na operação.';
        console.error(`[WhatsApp] Erro em ${url}:`, {
            status: response.status, 
            message, 
            data
        });
        throw new Error(message);
    }
    return data;
}
```

---

## 🐛 Problemas Resolvidos

### Problema 1: "QR Code Lido mas Não Loga"

**Sintomas:**
- QR Code é lido no celular
- WPPConnect mostra `qrReadSuccess`
- Após 60 segundos: `Failed to authenticate`, `qrReadError`, `Auto Close Called`
- Sessão não persiste

**Causa Raiz:**
- WPPConnect tinha `AUTO_CLOSE_INTERVAL` padrão de 60 segundos
- Usuário precisava confirmar no celular, o que levava mais de 60 segundos
- WPPConnect fechava a página antes da autenticação completar

**Solução:**
1. **Aumentar AUTO_CLOSE_INTERVAL** para 300.000ms (5 minutos) no docker-compose.yml
2. **Usar wait_connection=False** no `create_instance()` para evitar timeout no Django
3. **Polling frontend** detecta quando status muda para `isLogged` e recarrega página

**Arquivo:** `docker-compose.yml`
```yaml
AUTO_CLOSE_INTERVAL: "300000"  # 5 minutos em milissegundos
```

**Arquivo:** `system_config/views.py`
```python
payload = api.create_instance(
    wait_qrcode=True,
    wait_connection=False,  # Evita timeout
    webhook=""
)
```

### Problema 2: "Timeout nas Requisições de Start"

**Sintomas:**
- Erro 500 ou timeout ao chamar `/system/whatsapp/start/`
- Django retorna erro após 30 segundos

**Causa Raiz:**
- Timeout padrão de 30 segundos era insuficiente
- WPPConnect pode demorar mais para gerar QR Code e iniciar navegador

**Solução:**
Aumentar timeouts de forma inteligente:

**Arquivo:** `system_config/whatsapp_helper.py`
```python
DEFAULT_TIMEOUT = 60  # De 30s → 60s

def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
    timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
    
    # Timeout ainda maior para operações críticas
    if "start" in endpoint or "close" in endpoint or "logout" in endpoint:
        timeout = max(timeout, 90)  # 90 segundos
    
    response = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
```

### Problema 3: "Erro 400 Bad Request Genérico"

**Sintomas:**
- Todos os erros da API WPPConnect retornavam status 400
- Difícil diagnosticar problema real (404, 500, etc.)

**Causa Raiz:**
- Função `_whatsapp_response` capturava todas exceções e retornava 400

**Solução:**
Diferenciar tipos de erro HTTP e retornar código correto:

**Arquivo:** `system_config/views.py`
```python
except requests.HTTPError as exc:  # Erros HTTP da API
    status_code = exc.response.status_code if exc.response else 500
    return JsonResponse({...}, status=status_code)  # Mantém código original

except Exception as exc:  # Outros erros
    return JsonResponse({...}, status=500)  # 500 para erros internos
```

### Problema 4: "Interface Não Atualiza Após Conexão"

**Sintomas:**
- QR Code lido e autenticado
- Página continua mostrando "Desconectado"
- Precisa recarregar manualmente (F5)

**Causa Raiz:**
- Polling detectava estados intermediários (`qrReadSuccess`, `inChat`)
- Recarregava página antes da autenticação completar
- Estados transitórios causavam reloads prematuros

**Solução:**
Verificação de estado mais rigorosa:

**Arquivo:** `system_config/templates/system_config/whatsapp_dashboard.html`
```javascript
let consecutiveConnected = 0;

setInterval(async () => {
    const isFullyConnected = session.connected === true || 
                            session.status === 'isLogged';
    
    if (isFullyConnected && lastStatus !== 'isLogged') {
        consecutiveConnected++;
        if (consecutiveConnected >= 2) {  // 2 × 5s = 10s de verificação
            setTimeout(() => window.location.reload(), 1500);
        }
    } else if (!isFullyConnected) {
        consecutiveConnected = 0;  // Reset se não conectado
    }
}, 5000);
```

**Estados Considerados "Totalmente Conectado":**
- ✅ `session.connected === true`
- ✅ `session.status === 'isLogged'`
- ❌ `qrReadSuccess` (ainda não autenticado)
- ❌ `inChat` (conectando)

### Problema 5: "QR Code Não Aparece Automaticamente"

**Sintomas:**
- Usuário acessa página
- Seção de QR Code vazia
- Precisa clicar em "Iniciar sessão" manualmente

**Causa Raiz:**
- Nenhuma lógica de auto-geração no carregamento da página

**Solução:**
Auto-geração inteligente na inicialização:

**Arquivo:** `system_config/templates/system_config/whatsapp_dashboard.html`
```javascript
setTimeout(async () => {
    const data = await callEndpoint(endpoints.status, { method: 'GET' });
    
    const isConnected = data.session && (
        data.session.connected === true || 
        data.session.status === 'connected' ||
        data.session.status === 'isLogged'
    );
    
    if (!isConnected) {
        await startSession();  // Gera QR automaticamente
    }
}, 1000);  // 1 segundo para DOM carregar
```

### Problema 6: "Seções Sempre Visíveis"

**Sintomas:**
- QR Code aparece mesmo quando conectado
- Informações da sessão aparecem quando desconectado
- Interface confusa

**Causa Raiz:**
- Visibilidade controlada apenas por template Django (`{% if is_connected %}`)
- Não atualizava dinamicamente após conexão

**Solução:**
Controle dinâmico via JavaScript:

**Arquivo:** `system_config/templates/system_config/whatsapp_dashboard.html`
```javascript
function renderStatus(session) {
    const connected = session && (
        session.connected === true || 
        session.status === 'connected' ||
        session.status === 'isLogged'
    );
    
    const qrCodeSection = document.getElementById('qrCodeSection');
    const sessionInfoCard = document.getElementById('sessionInfoCard');
    
    if (connected) {
        qrCodeSection?.classList.add('hidden');      // Oculta QR
        sessionInfoCard?.classList.remove('hidden'); // Mostra info
    } else {
        qrCodeSection?.classList.remove('hidden');   // Mostra QR
        sessionInfoCard?.classList.add('hidden');    // Oculta info
    }
}
```

---

## 📁 Estrutura de Arquivos

```
system_config/
├── views.py                          # Endpoints Django
│   ├── whatsapp_dashboard()          # GET - Renderiza dashboard
│   ├── whatsapp_start_session()      # POST - Inicia sessão + QR Code
│   ├── whatsapp_status()             # GET - Status da sessão
│   ├── whatsapp_qrcode()             # GET - Obtém QR Code
│   ├── whatsapp_logout()             # POST - Desconecta sessão
│   ├── whatsapp_close()              # POST - Fecha sessão
│   └── whatsapp_send_test()          # POST - Envia mensagem teste
│
├── whatsapp_helper.py                # SDK Python WPPConnect
│   ├── WhatsAppWPPConnectAPI         # Classe principal
│   │   ├── from_config()             # Factory method
│   │   ├── _ensure_token_hash()      # Gera token bcrypt
│   │   ├── _request()                # HTTP client com timeouts
│   │   ├── create_instance()         # Inicia sessão
│   │   ├── get_qrcode()              # Obtém QR Code
│   │   ├── get_connection_state()    # Status de conexão
│   │   ├── get_session_info()        # Info da sessão
│   │   ├── logout()                  # Desconecta
│   │   ├── close_session()           # Fecha sessão
│   │   └── send_text()               # Envia mensagem
│   └── format_phone_number()         # Formata número para WA
│
├── urls.py                           # URLs do sistema
│   └── path('whatsapp/', ...)        # Rotas WhatsApp
│
├── models.py                         # Modelos Django
│   └── SystemConfiguration           # Config persistente
│       ├── whatsapp_enabled
│       ├── whatsapp_evolution_api_url
│       ├── whatsapp_instance_name
│       └── whatsapp_evolution_api_key
│
└── templates/system_config/
    └── whatsapp_dashboard.html       # Interface principal
        ├── Seção: Configurações      # Gerenciar settings
        ├── Seção: QR Code            # Autenticação
        ├── Seção: Informações        # Status da sessão
        ├── Seção: Ações Rápidas      # Botões de controle
        └── Seção: Enviar Teste       # Testar envio

docker-compose.yml                     # Configuração Docker
└── wppconnect:                        # Container WPPConnect
    └── environment:
        └── AUTO_CLOSE_INTERVAL: "300000"  # ⚠️ CRÍTICO
```

---

## 🌐 API Endpoints

### GET `/system/whatsapp/`
**Dashboard Principal**
- Renderiza interface web
- Verifica configuração
- Obtém status inicial da sessão

**Response:** HTML

---

### POST `/system/whatsapp/start/`
**Iniciar Sessão e Obter QR Code**

**Request:**
```json
{}  // Corpo vazio
```

**Response (Sucesso):**
```json
{
  "success": true,
  "qrcode": "data:image/png;base64,iVBORw0KGgoAAAANS...",
  "pairingCode": "ABCD-1234",
  "raw": { /* resposta completa do WPPConnect */ },
  "status": {
    "connected": false,
    "status": "notLogged",
    "message": "Waiting for QRCode Scan"
  }
}
```

**Response (Erro - Configuração Incompleta):**
```json
{
  "success": false,
  "message": "URL do WPPConnect não configurada"
}
```

**Status Codes:**
- `200` - Sucesso
- `400` - Configuração inválida
- `500` - Erro no WPPConnect Server

---

### GET `/system/whatsapp/status/`
**Obter Status da Sessão**

**Response (Conectado):**
```json
{
  "success": true,
  "session": {
    "connected": true,
    "status": "isLogged",
    "message": "Connected",
    "phone": "5511999999999",
    "device": {
      "manufacturer": "Apple",
      "model": "iPhone 13",
      "os": "iOS 16.5"
    },
    "battery": 85
  }
}
```

**Response (Desconectado):**
```json
{
  "success": true,
  "session": {
    "connected": false,
    "status": "notLogged",
    "message": "Session not initialized"
  }
}
```

**Possíveis Status:**
- `notLogged` - Não autenticado
- `qrReadSuccess` - QR lido, aguardando confirmação
- `inChat` - Conectando
- `isLogged` - ✅ Autenticado e conectado
- `CONNECTED` - ✅ Conectado (sinônimo)

---

### GET `/system/whatsapp/qrcode/`
**Obter QR Code Atual**

**Response:**
```json
{
  "success": true,
  "qrcode": "data:image/png;base64,iVBORw0KGgoAAAANS...",
  "pairingCode": "WXYZ-5678",
  "raw": { /* resposta do WPPConnect */ }
}
```

**Uso:** Atualizar QR Code se expirou (QR Code expira após ~40 segundos)

---

### POST `/system/whatsapp/logout/`
**Desconectar Sessão**

**Request:**
```json
{}  // Corpo vazio
```

**Response:**
```json
{
  "success": true,
  "response": {
    "message": "Successfully logged out"
  }
}
```

**Efeito:** 
- Remove autenticação do WhatsApp
- Mantém dados locais da sessão
- Requer novo QR Code para reconectar

---

### POST `/system/whatsapp/close/`
**Fechar Sessão Completamente**

**Request:**
```json
{}  // Corpo vazio
```

**Response:**
```json
{
  "success": true,
  "response": {
    "message": "Session closed"
  }
}
```

**Efeito:**
- Remove autenticação
- **Deleta dados locais** da sessão
- Nova sessão será criada ao reconectar

---

### POST `/system/whatsapp/send-test/`
**Enviar Mensagem de Teste**

**Request:**
```json
{
  "phone": "5511999999999",
  "message": "Teste WhatsApp WPPConnect"
}
```

**Response (Sucesso):**
```json
{
  "success": true,
  "messageId": "true_5511999999999@c.us_3EB0...",
  "response": { /* resposta do WPPConnect */ }
}
```

**Response (Erro):**
```json
{
  "success": false,
  "message": "Número de telefone inválido"
}
```

**Validações:**
- Número deve ter 10-15 dígitos
- Sessão deve estar conectada

---

## 🔧 Troubleshooting

### Container WPPConnect Unhealthy

**Sintoma:**
```bash
docker compose ps
# leguas_wppconnect ... Up 37 minutes (unhealthy)
```

**Diagnóstico:**
```bash
docker logs leguas_wppconnect --tail=50
```

**Possíveis Causas:**
1. Porta 21465 já em uso
2. Memória insuficiente (WPPConnect usa Chrome headless)
3. Permissões incorretas em volumes

**Solução:**
```bash
# Verificar porta
netstat -ano | findstr "21465"

# Recriar container
docker compose down wppconnect
docker compose up -d wppconnect

# Verificar logs em tempo real
docker logs -f leguas_wppconnect
```

---

### QR Code Não Aparece

**Diagnóstico:**
1. Abrir console do navegador (F12)
2. Procurar por erros `[WhatsApp]`
3. Verificar network tab para ver resposta de `/start/`

**Possíveis Causas:**
- WPPConnect não iniciado
- URL incorreta em `SystemConfiguration`
- Token inválido
- CSRF token ausente

**Solução:**
```javascript
// Console do navegador
fetch('/system/whatsapp/status/', {
    headers: {
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
    }
}).then(r => r.json()).then(console.log)
```

---

### Sessão Desconecta Sozinha

**Diagnóstico:**
```bash
docker logs leguas_wppconnect | grep -i "auto close\|logout\|disconnect"
```

**Possíveis Causas:**
1. `AUTO_CLOSE_INTERVAL` muito baixo
2. WPPConnect reiniciando
3. Memória insuficiente

**Solução:**
```yaml
# docker-compose.yml
AUTO_CLOSE_INTERVAL: "600000"  # Aumentar para 10 minutos
```

```bash
docker compose restart wppconnect
```

---

### Erro "Failed to Authenticate"

**Logs:**
```
warn: [leguas_wppconnect:client] Failed to authenticate
info: qrReadError
error: Auto Close Called
```

**Causa:** Tempo entre leitura do QR e confirmação no celular > AUTO_CLOSE_INTERVAL

**Solução:** Verificar se `AUTO_CLOSE_INTERVAL` está configurado (padrão é apenas 60s)

```bash
# Verificar variável de ambiente
docker exec leguas_wppconnect env | grep AUTO_CLOSE

# Se não aparecer, adicionar no docker-compose.yml:
AUTO_CLOSE_INTERVAL: "300000"

# Recriar container
docker compose up -d --force-recreate wppconnect
```

---

### Timeout nas Requisições

**Erro:**
```
ReadTimeout: HTTPConnectionPool(host='leguas_wppconnect', port=21465): 
Read timed out. (read timeout=30)
```

**Causa:** Timeout muito baixo para operações demoradas

**Verificar:**
```python
# system_config/whatsapp_helper.py
DEFAULT_TIMEOUT = 60  # Deve ser 60 ou maior

def _request(self, method, endpoint, **kwargs):
    if "start" in endpoint:
        timeout = max(timeout, 90)  # Deve ter esta lógica
```

---

### Polling Muito Frequente

**Sintoma:** Logs com muitas requisições `/status/`

**Solução:** Ajustar intervalo de polling

```javascript
// whatsapp_dashboard.html
setInterval(async () => {
    // ...polling logic...
}, 10000);  // Aumentar para 10 segundos (ou mais)
```

**Recomendado:**
- Desenvolvimento: 5000ms (5 segundos)
- Produção: 10000ms (10 segundos)

---

### Logs de Debug Excessivos

**Solução:** Mudar `console.log` para `console.debug`

```javascript
// whatsapp_dashboard.html
console.debug('[WhatsApp] Atualizando status...');  // Em vez de console.log
```

No navegador, desabilitar logs debug no DevTools.

---

## 📊 Monitoramento

### Logs Importantes

**WPPConnect:**
```bash
# Status de conexão
docker logs leguas_wppconnect | grep -i "connected\|islogged"

# Erros de autenticação
docker logs leguas_wppconnect | grep -i "failed\|error"

# Auto-close
docker logs leguas_wppconnect | grep -i "auto close"
```

**Django:**
```bash
docker logs leguas_web | grep -i "whatsapp"
```

### Métricas de Saúde

**Indicadores Positivos:**
- WPPConnect: `Connected`, `isLogged`, `Current state: MAIN (NORMAL)`
- Django: Sem erros `[WhatsApp]` nos logs
- Frontend: Console mostra "SESSÃO TOTALMENTE CONECTADA"

**Indicadores Negativos:**
- WPPConnect: `notLogged`, `qrReadError`, `Failed to authenticate`, `Auto Close Called`
- Django: `Erro HTTP 400/404/500 na API WPPConnect`
- Frontend: Reloads infinitos, seção QR sempre visível

---

## 🚀 Melhorias Futuras

### Implementações Sugeridas

1. **Webhook do WPPConnect**
   - Receber notificações de eventos em tempo real
   - Reduzir necessidade de polling
   - Atualizar interface via WebSocket/SSE

2. **Reconnect Automático**
   - Detectar desconexão e tentar reconectar automaticamente
   - Limitar tentativas para evitar loops infinitos

3. **Multiple Instances**
   - Suportar múltiplas sessões WhatsApp
   - Interface para gerenciar várias instâncias

4. **Message Queue**
   - Fila de mensagens para envio em lote
   - Retry automático em caso de falha

5. **Analytics Dashboard**
   - Métricas de mensagens enviadas/recebidas
   - Uptime da conexão
   - Histórico de reconexões

6. **Backup de Sessão**
   - Exportar dados da sessão periodicamente
   - Restaurar sessão após reinício do container

---

## 📝 Checklist de Deploy

- [ ] Configurar `AUTO_CLOSE_INTERVAL` no docker-compose.yml
- [ ] Verificar `DEFAULT_TIMEOUT` >= 60s em whatsapp_helper.py
- [ ] Configurar variáveis de ambiente no SystemConfiguration
- [ ] Testar fluxo completo de autenticação
- [ ] Verificar logs do WPPConnect após conexão
- [ ] Confirmar que polling não sobrecarrega servidor
- [ ] Testar envio de mensagem
- [ ] Documentar configurações customizadas
- [ ] Configurar monitoramento de uptime
- [ ] Planejar estratégia de backup

---

## 📚 Referências

- [WPPConnect Server Docs](https://wppconnect-team.github.io/wppconnect-server/)
- [WPPConnect API Reference](https://wppconnect.io/)
- [Django Documentation](https://docs.djangoproject.com/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Lucide Icons](https://lucide.dev/)

---

**Última Atualização:** 10 de Fevereiro de 2026  
**Versão:** 1.0  
**Autor:** Equipe Léguas Franzinas
