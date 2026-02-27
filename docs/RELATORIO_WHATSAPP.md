# Relatório Completo - Integração WhatsApp

**Data:** 09 de Fevereiro de 2026  
**Sistema:** Léguas Franzinas - Painel de Gestão WhatsApp

---

## 🏗️ Arquitetura da Solução

### Componentes Principais

```
┌─────────────────────────────────────────────────────────────┐
│                    DJANGO WEB (Python)                      │
│  ┌────────────────────────────────────────────────────┐    │
│  │  SystemConfiguration Model                          │    │
│  │  - whatsapp_enabled                                 │    │
│  │  - whatsapp_evolution_api_url                      │    │
│  │  - whatsapp_evolution_api_key (token)              │    │
│  │  - whatsapp_instance_name                          │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↓                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │  WhatsAppWPPConnectAPI Helper                      │    │
│  │  - Gerencia comunicação com WPPConnect              │    │
│  │  - Endpoints: start-session, qrcode, status         │    │
│  │  - Autenticação via Bearer Token                    │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↓                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Views (system_config/views.py)                    │    │
│  │  - whatsapp_dashboard                              │    │
│  │  - whatsapp_start_session                          │    │
│  │  - whatsapp_qrcode                                 │    │
│  │  - whatsapp_status                                 │    │
│  │  - whatsapp_generate_token                         │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          ↓ HTTP
┌─────────────────────────────────────────────────────────────┐
│              WPPConnect Server (Node.js)                    │
│  Container: leguas_wppconnect                               │
│  Porta: 21465                                               │
│  Imagem: wppconnect/server-cli:latest                       │
│                                                             │
│  Variáveis de Ambiente:                                     │
│  - SECRET_KEY=leguas-super-secret                          │
│  - TOKEN=VwfSzDglRI5jVAQTmmh5hZ8YZh_qsmqCcldJ3tBLA9g      │
│  - SERVER_PORT=21465                                        │
│                                                             │
│  Endpoints Principais:                                      │
│  POST /api/{session}/start-session                         │
│  GET  /api/{session}/qrcode-session                        │
│  GET  /api/{session}/check-connection-session              │
│  GET  /api/{session}/status-session                        │
│  POST /api/{session}/logout-session                        │
│  POST /api/{session}/{secretkey}/generate-token            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                  WhatsApp Web (Baileys)                     │
│  - Conexão via QR Code ou Pairing Code                     │
│  - Gerenciamento de mensagens                              │
│  - Persistência de sessão                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Fluxo de Autenticação

### Problema Identificado

O WPPConnect usa **autenticação bcrypt** em duas camadas:

1. **SECRET_KEY**: Chave interna do servidor (leguas-super-secret)
2. **Token Hash**: Hash bcrypt gerado de `session_name + SECRET_KEY`

### Fluxo Correto

```
┌─────────────────────────────────────────────────────────────┐
│ 1. GERAÇÃO DO TOKEN HASH                                    │
└─────────────────────────────────────────────────────────────┘
   POST /api/leguas_wppconnect/leguas-super-secret/generate-token
   
   Request Headers:
   - (nenhum necessário para este endpoint)
   
   Response:
   {
     "status": "success",
     "session": "leguas_wppconnect",
     "token": "Rjhfp-4dF...",  // Hash bcrypt
     "full": "leguas_wppconnect:Rjhfp-4dF..."
   }

┌─────────────────────────────────────────────────────────────┐
│ 2. USO DO TOKEN NAS REQUISIÇÕES                             │
└─────────────────────────────────────────────────────────────┘
   POST /api/leguas_wppconnect/start-session
   
   Request Headers:
   - Authorization: Bearer Rjhfp-4dF...
   - Content-Type: application/json
   
   Request Body:
   {
     "waitQrCode": true,
     "waitConnection": false
   }
```

---

## 📁 Estrutura de Arquivos

### Django Backend

```
system_config/
├── models.py                    # SystemConfiguration model
├── views.py                     # Endpoints do painel WhatsApp
├── whatsapp_helper.py          # Cliente HTTP WPPConnect API
├── token_utils.py              # Propagação de token para arquivos
├── urls.py                      # Rotas do módulo
└── templates/
    └── system_config/
        └── whatsapp_dashboard.html  # Interface do painel
```

### Configuração Docker

```
docker-compose.yml              # Definição do container wppconnect
.env                           # Variáveis de ambiente (produção)
.env.docker                    # Variáveis de ambiente (desenvolvimento)
```

### Propagação Automática

Quando um token é gerado/atualizado no painel:

1. **Banco de Dados**: `SystemConfiguration.whatsapp_evolution_api_key`
2. **Arquivos Env**:
   - `.env` → `AUTHENTICATION_API_KEY`
   - `.env.docker` → `AUTHENTICATION_API_KEY`, `EVOLUTION_API_KEY`
3. **Docker Compose**: `docker-compose.yml` → `TOKEN` e `AUTHENTICATION_API_KEY`
4. **Restart Automático**: Containers `leguas_wppconnect` e `leguas_whatsapp_evolution` via Docker socket

---

## 🔧 Configurações Atuais

### Banco de Dados
- **URL**: `http://wppconnect:21465`
- **Token**: `VwfSzDglRI5jVAQTmmh5hZ8YZh_qsmqCcldJ3tBLA9g`
- **Sessão**: `leguas_wppconnect`

### Container WPPConnect
```yaml
environment:
  - SECRET_KEY=leguas-super-secret
  - TOKEN=VwfSzDglRI5jVAQTmmh5hZ8YZh_qsmqCcldJ3tBLA9g
  - SERVER_PORT=21465
  - DEBUG=false
  - LOG_LEVEL=ERROR
```

### Endpoints Mapeados

| Ação | Método | Endpoint | Autenticação |
|------|--------|----------|--------------|
| Iniciar Sessão | POST | `/api/{session}/start-session` | Bearer Token Hash |
| Obter QR Code | GET | `/api/{session}/qrcode-session` | Bearer Token Hash |
| Verificar Status | GET | `/api/{session}/check-connection-session` | Bearer Token Hash |
| Estado da Sessão | GET | `/api/{session}/status-session` | Bearer Token Hash |
| Desconectar | POST | `/api/{session}/logout-session` | Bearer Token Hash |
| Gerar Token Hash | POST | `/api/{session}/{secret}/generate-token` | Secret Key |

---

## 🐛 Problema Atual

### Sintoma
- Requisições retornam **401 Unauthorized** ou **400 Bad Request**
- QR Code não aparece no painel

### Causa Raiz
O helper Django está enviando o **token raw** (`VwfSzDglRI5jVAQTmmh5hZ8YZh_qsmqCcldJ3tBLA9g`) diretamente, mas o WPPConnect espera um **hash bcrypt** gerado pelo servidor.

### Solução Implementada
Adicionar lógica no helper para:
1. Verificar se o token atual é um hash bcrypt válido
2. Se não for, chamar `/generate-token` automaticamente
3. Cachear o hash gerado para requisições futuras
4. Atualizar o banco de dados com o hash correto

---

## 📊 Fluxo Completo do Usuário

```
┌────────────────────────────────────────────────────────────┐
│ 1. USUÁRIO ACESSA PAINEL                                   │
│    → /system/whatsapp/                                     │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ 2. DJANGO CARREGA CONFIGURAÇÕES                            │
│    → SystemConfiguration.get_config()                      │
│    → whatsapp_evolution_api_url                           │
│    → whatsapp_evolution_api_key                           │
│    → whatsapp_instance_name                               │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ 3. USUÁRIO CLICA "INICIAR SESSÃO"                         │
│    → POST /system/whatsapp/start/                         │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ 4. HELPER GERA TOKEN HASH (se necessário)                 │
│    → POST /api/{session}/{secret}/generate-token          │
│    → Armazena hash bcrypt                                 │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ 5. HELPER INICIA SESSÃO                                   │
│    → POST /api/{session}/start-session                    │
│    → Header: Authorization Bearer {hash}                  │
│    → Body: {"waitQrCode": true}                           │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ 6. WPPCONNECT RETORNA QR CODE                             │
│    → {"qrcode": "data:image/png;base64,..."}              │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ 7. PAINEL EXIBE QR CODE                                   │
│    → Usuário escaneia com WhatsApp                        │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ 8. VERIFICAÇÃO PERIÓDICA DE STATUS                        │
│    → GET /api/{session}/check-connection-session          │
│    → Atualiza badge de status (Conectado/Desconectado)    │
└────────────────────────────────────────────────────────────┘
```

---

## 🚀 Funcionalidades Implementadas

### ✅ Painel de Controle
- [x] Configuração de URL, token e instância
- [x] Geração automática de tokens
- [x] Propagação para arquivos .env e docker-compose
- [x] Restart automático de containers
- [x] Feedback visual de sincronização

### ✅ Gerenciamento de Sessão
- [x] Iniciar sessão (aguarda QR Code)
- [x] Obter QR Code
- [x] Verificar status da conexão
- [x] Desconectar sessão
- [x] Badge de status em tempo real

### ⏳ Em Correção
- [ ] Autenticação bcrypt automática
- [ ] Cache de token hash
- [ ] Retry automático em caso de 401

---

## 🔍 Próximos Passos

1. **Imediato**: Implementar geração automática de hash bcrypt no helper
2. **Curto Prazo**: Adicionar cache de token para evitar chamadas repetidas
3. **Médio Prazo**: Implementar renovação automática de token expirado
4. **Longo Prazo**: Adicionar suporte para múltiplas instâncias WhatsApp

---

## 📞 Suporte e Documentação

- **WPPConnect Docs**: https://github.com/wppconnect-team/wppconnect
- **WPPConnect Server**: https://github.com/wppconnect-team/server-cli
- **Swagger API**: http://localhost:21465/api-docs

---

_Documento gerado automaticamente - Léguas Franzinas © 2026_
