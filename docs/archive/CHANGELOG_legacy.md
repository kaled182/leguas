# 📝 Changelog - Projeto Léguas Franzinas

## [10/02/2026 - 22:05] - ✅ OMNICHANNEL 100% FUNCIONAL

### 🎉 MARCO: Comunicação Bidirecional WhatsApp ↔ Chatwoot Operacional

**Status:** Sistema completo funcionando em produção com 9 containers

---

## 🎯 Componentes Implementados

### **Chatwoot v2.x** - Central de Atendimento
- Container: `leguas_chatwoot_web` (porta 3000) ✅ Running
- Container: `leguas_chatwoot_worker` (Sidekiq) ✅ Running  
- PostgreSQL: `leguas_chatwoot_db` (pgvector/pgvector:pg15) ✅ Healthy
- Redis: `leguas_chatwoot_redis` ✅ Healthy
- **Account ID:** 1
- **Inbox ID:** 1 (WhatsApp Leguas - Channel::Api)
- **API Token:** w2w8N98Pv8yqazrHPyqAuwkR

### **WPPConnect Server** - Gateway WhatsApp
- Container: `leguas_wppconnect` (porta 21465) ✅ Running
- **Sessão:** leguas_wppconnect (conectada)
- **Telefone:** +351 915 211 836
- **Generated Token:** $2b$10$QaQSGFS8eSdOe.X9S5Lovu63lX0d24LuKdCHVRqNEyKyvbvXGNcLy
- **Secret Key:** THISISMYSECURETOKEN

### **WPPConnect-Chatwoot Bridge** - Integração Bidirecional
- Container: `leguas_wppconnect_bridge` (porta 3500) ✅ Running
- **Tecnologia:** Node.js 18 Alpine + Express + Axios + Winston
- **Código:** 574 linhas (index.js)
- **Polling:** Ativo a cada 5 segundos
- **LOG_LEVEL:** debug

### **Typebot** - Automação (Infraestrutura Pronta)
- Container: `leguas_typebot_builder` (porta 8081) ✅ Running
- Container: `leguas_typebot_viewer` (porta 8082) ✅ Running
- PostgreSQL: `leguas_typebot_db` ✅ Healthy
- **Status:** Aguardando configuração de bots

---

## 🔄 Fluxos Implementados

### ✅ Fluxo 1: Chatwoot → WhatsApp (Outbound)
**Performance:** 100% funcional, < 1s latência
```
Agente Chatwoot → Webhook Bridge → WPPConnect API → WhatsApp User
```

### ✅ Fluxo 2: WhatsApp → Chatwoot (Inbound)  
**Performance:** Funcional via polling, 2-5s latência
```
WhatsApp User → WPPConnect → Polling Bridge (5s) → Chatwoot API → Agente
```

**Método:** Polling implementado devido a webhooks WPPConnect não dispararem automaticamente
- Intervalo: 5 segundos
- Chats por ciclo: 5 máximo
- Mensagens por chat: 5 últimas
- Cache de IDs: Previne duplicação

---

## 🛠️ Problemas Críticos Resolvidos

### Issue #1: Formato de Resposta da API
**Problema:** `GET /all-messages-in-chat/{chatId}` retorna objeto `{status, response: []}` não array  
**Solução:** Acessar `messagesResponse.data.response`
```javascript
const messagesArray = messagesResponse.data?.response || messagesResponse.data;
```

### Issue #2: Source ID em Conversas
**Problema:** Erro 404 ao criar conversa com `source_id: phoneNumber`  
**Causa:** Contact_inbox já tinha source_id UUID diferente  
**Solução:** Buscar contact_inbox e usar source_id existente
```javascript
const contactInbox = contactData.contact_inboxes?.find(ci => ci.inbox.id == inboxId);
// Usar: contactInbox.source_id
```

### Issue #3: ConversationId como Objeto
**Problema:** `sendMessageToChatwoot(conversationId, message)` recebia objeto ao invés de ID  
**Solução:** Extrair ID do objeto de conversa
```javascript
const conversation = await getOrCreateConversation(contactId, phone);
await sendMessageToChatwoot(conversation.id, msg); // .id não conversation
```

### Issue #4: PostgreSQL sem pgvector
**Problema:** Chatwoot falhava - `extension "vector" is not available`  
**Solução:** Trocar imagem `postgres:15-alpine` → `pgvector/pgvector:pg15`

### Issue #5: Autenticação WPPConnect
**Problema:** TOKEN de .env não funcionava  
**Solução:** Gerar token via API
```bash
POST /api/leguas_wppconnect/THISISMYSECURETOKEN/generate-token
```

### Issue #6: Webhooks Não Disparam
**Problema:** WEBHOOK_GLOBAL_ENABLED=true mas webhooks nunca recebidos  
**Diagnóstico:** Teste manual funciona, automático não  
**Solução:** Implementado polling como alternativa robusta

---

## 📁 Estrutura de Código

### wppconnect-chatwoot-bridge/
```
index.js (574 linhas)
├── Funções Core:
│   ├── formatPhoneNumber()          # Normaliza +5563999925657 ↔ 5563999925657@c.us
│   ├── getContactById()             # Busca contato por ID
│   ├── getOrCreateContact()         # Gerencia contatos Chatwoot
│   ├── getOrCreateConversation()    # Gerencia conversas com source_id correto
│   ├── sendMessageToChatwoot()      # Envia mensagens para Chatwoot
│   └── pollWPPConnectMessages()     # Polling inteligente a cada 5s
│
├── Webhooks:
│   ├── POST /webhook/chatwoot       # Recebe mensagens outbound
│   └── POST /webhook/wppconnect     # Recebe mensagens inbound (manual)
│
└── Configuração:
    ├── LOG_LEVEL: debug
    ├── Polling: 5s após 10s boot
    ├── Cache: processedMessageIds (max 1000)
    └── Filtros: !isGroup, !fromMe, timestamp < 1h
```

### docker-compose.yml
```yaml
9 containers totais:
├── leguas_chatwoot_web       (3000)
├── leguas_chatwoot_worker
├── leguas_chatwoot_db        (5432) 
├── leguas_chatwoot_redis     (6379)
├── leguas_wppconnect         (21465)
├── leguas_wppconnect_bridge  (3500)
├── leguas_typebot_builder    (8081)
├── leguas_typebot_viewer     (8082)
└── leguas_typebot_db         (5433)
```

---

## 📊 Testes Realizados e Validados

### ✅ Teste 1: Envio Chatwoot → WhatsApp
- Mensagens instantâneas (< 1s)
- Formatação preservada
- Números internacionais (+55)

### ✅ Teste 2: Recebimento WhatsApp → Chatwoot  
- Detecção via polling (5s)
- Contatos criados automaticamente
- Conversas gerenciadas corretamente
- Conteúdo preservado

### ✅ Teste 3: Múltiplas Mensagens
- 5 mensagens rápidas processadas sem duplicação
- Cache de IDs funcionando

### ✅ Teste 4: Mensagens Antigas
- Mensagens > 1 hora corretamente ignoradas

---

## 🔧 Funcionalidades Implementadas

- ✅ **Receber mensagens WhatsApp → Chatwoot** (polling 5s)
- ✅ **Enviar mensagens Chatwoot → WhatsApp** (< 1s)
- ✅ **Criar contatos automaticamente** (via API search/create)
- ✅ **Gerenciar conversas** (source_id correto)
- ✅ **Cache de mensagens processadas** (evita duplicação)
- ✅ **Filtros inteligentes** (grupos, próprias, antigas)
- ✅ **Logging detalhado** (debug level)
- ✅ **Formatação de números** (+55 ↔ @c.us)
- ⏸️ **Typebot cadastro motoristas** (infraestrutura pronta)
- ⏸️ **Django register_driver_typebot** (endpoint pendente)

---

## 🔑 Credenciais e Endpoints
- **Chatwoot SECRET_KEY_BASE**: `947fc343...`
- **Typebot ENCRYPTION_SECRET**: `UDNRHCFU...`

### 📚 Documentação
- **Criado**: `docs/OMNICHANNEL_SETUP.md`
  - Guia completo de implementação
  - Configuração passo a passo
  - Fluxo de dados detalhado
  - Troubleshooting
  - Integração com sistema Léguas

### 🎓 Casos de Uso
1. **Cadastro Automatizado**: Motorista envia "Oi" no WhatsApp → Bot coleta dados → Salva no sistema
2. **Atendimento Humano**: Conversa transferida do bot para atendente quando necessário
3. **Histórico Unificado**: Todas conversas centralizadas no Chatwoot

### 📊 Recursos Necessários
- **+3 PostgreSQL**: chatwoot_db, typebot_db
- **+1 Redis**: chatwoot_redis  
- **+6 Containers**: chatwoot_web, chatwoot_worker, typebot_builder, typebot_viewer, wppconnect_bridge, (3 databases)
- **RAM estimada**: +2GB
- **Portas abertas**: 3000 (Chatwoot), 3500 (Bridge), 8081 (Typebot Builder), 8082 (Typebot Viewer)

---

## [10/02/2026] - Remoção Evolution API e Otimização WhatsApp

### 🗑️ Removido
- **Evolution API** (`leguas_whatsapp_evolution`) - Container não utilizado
- **PostgreSQL Evolution** (`leguas_whatsapp_postgres`) - Database dedicado não utilizado
- **Volumes órfãos**: `evolution_instances`, `evolution_store`, `evolution_postgres_data`
- **Portas liberadas**: 8021 (Evolution API), 5433 (PostgreSQL)

### 📊 Impacto
- **Recursos liberados**: ~500MB RAM, 1 CPU core
- **Containers ativos**: 5 → 3 (redução de 40%)
- **Complexidade reduzida**: Arquitetura mais simples e clara

### ✅ Sistema Atual
**WhatsApp Integration:**
- **Provider**: WPPConnect Server
- **Container**: `leguas_wppconnect`
- **Porta**: 21465
- **Status**: Ativo e funcional
- **Features**: Auto-geração QR Code, polling 5s, auto-reload ao conectar

### 📌 Nota Histórica
O sistema foi migrado de Evolution API para WPPConnect Server. Os nomes dos campos no modelo Django (`whatsapp_evolution_api_url`, `whatsapp_evolution_api_key`) são nomenclatura legada que permanece por compatibilidade com código existente.

**Motivo da migração:**
- WPPConnect Server mais estável
- Melhor documentação e suporte
- Menor consumo de recursos (não requer PostgreSQL dedicado)
- Integração mais simples

---

## [10/02/2026] - Implementação WhatsApp Dashboard Completo

### ✨ Adicionado
- **Dashboard WhatsApp** com interface moderna e responsiva
- **Auto-geração de QR Code** ao carregar página se desconectado
- **Polling automático** a cada 5 segundos para detectar conexão
- **Auto-reload inteligente** quando sessão conecta (após 2 verificações consecutivas)
- **Seções colapsáveis** para configurações
- **Visibilidade dinâmica** de seções (QR Code vs Informações da Sessão)
- **Tratamento de erros melhorado** com logs detalhados no console

### 🔧 Configurado
- **AUTO_CLOSE_INTERVAL**: 300000ms (5 minutos) no WPPConnect
  - Resolve problema de timeout durante autenticação
  - Permite tempo suficiente para confirmar no celular
- **DEFAULT_TIMEOUT**: 60s (requisições normais)
- **Timeout especial**: 90s para operações de start/close/logout
- **Polling interval**: 5000ms (5 segundos)

### 🐛 Corrigido
- **Problema**: QR Code lido mas sessão não persistia
  - **Causa**: Auto-close de 60s era muito curto
  - **Solução**: Aumentado para 300s + polling inteligente

- **Problema**: Timeout em requisições de start
  - **Causa**: 30s insuficiente para WPPConnect
  - **Solução**: Timeouts dinâmicos 60s-90s

- **Problema**: Erros 400 genéricos
  - **Causa**: Todos erros HTTP retornavam 400
  - **Solução**: Retorna código HTTP original da API

- **Problema**: Interface não atualiza após conexão
  - **Causa**: Reload prematuro em estados intermediários
  - **Solução**: Verificação rigorosa (status === 'isLogged')

- **Problema**: QR Code não aparece automaticamente
  - **Causa**: Sem auto-geração
  - **Solução**: setTimeout 1s após load da página

- **Problema**: Seções sempre visíveis
  - **Causa**: Controle apenas no template Django
  - **Solução**: Controle dinâmico via JavaScript

### 📚 Documentação
- **Criado**: `docs/WHATSAPP_INTEGRATION.md`
  - Arquitetura completa
  - Configuração detalhada
  - Fluxo de autenticação
  - API endpoints
  - Troubleshooting guide
  - 6 problemas documentados com soluções

---

## Containers Ativos (Após Otimização)

| Container | Serviço | Porta | Status |
|-----------|---------|-------|--------|
| `leguas_mysql` | MySQL 8.0 | 3307 | Healthy |
| `leguas_redis` | Redis 7 | 6379 | Healthy |
| `leguas_web` | Django App | 8000 | Running |
| `leguas_tailwind` | Tailwind CSS | - | Building |
| `leguas_wppconnect` | WhatsApp | 21465 | Running |

**Total**: 5 containers (antes: 7)

---

## Próximas Melhorias Sugeridas

### WhatsApp
- [ ] Implementar webhooks do WPPConnect para eventos em tempo real
- [ ] Adicionar reconnect automático em caso de desconexão
- [ ] Suporte a múltiplas instâncias WhatsApp
- [ ] Message queue para envio em lote
- [ ] Analytics dashboard (mensagens enviadas/recebidas, uptime)
- [ ] Backup automático de sessão

### Geral
- [ ] Remover referências a "evolution" no código (renomear campos)
- [ ] Adicionar monitoramento de health dos containers
- [ ] Implementar CI/CD pipeline
- [ ] Documentar processo de deploy
- [ ] Adicionar testes automatizados

---

**Mantido por**: Equipe Léguas Franzinas  
**Última atualização**: 10 de Fevereiro de 2026
