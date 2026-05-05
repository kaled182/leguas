# ✅ Checklist de Configuração do Omnichannel

## 📋 Status da Implementação

### FASE 1: Infraestrutura Docker ✅

- [x] **1.1** Containers criados no docker-compose.yml
  - [x] chatwoot_db
  - [x] chatwoot_redis
  - [x] chatwoot_web
  - [x] chatwoot_worker
  - [x] typebot_db
  - [x] typebot_builder
  - [x] typebot_viewer
  - [x] wppconnect
  - [x] wppconnect_bridge

- [x] **1.2** Secrets gerados
  - [x] SECRET_KEY_BASE (64 caracteres hex)
  - [x] ENCRYPTION_SECRET (32 caracteres uppercase)

- [x] **1.3** Network configurada
  - [x] leguas_network existe
  - [x] Todos os containers conectados

- [x] **1.4** Volumes criados
  - [x] chatwoot_db_data
  - [x] chatwoot_redis_data
  - [x] typebot_db_data

### FASE 2: Inicialização ✅

- [x] **2.1** Iniciar containers
  ```bash
  docker compose up -d chatwoot_db chatwoot_redis chatwoot_web chatwoot_worker typebot_db typebot_builder typebot_viewer
  ```

- [x] **2.2** Verificar health checks
  ```bash
  docker compose ps
  ```
  - [x] chatwoot_db: healthy
  - [x] chatwoot_redis: healthy
  - [x] chatwoot_web: healthy
  - [x] chatwoot_worker: running
  - [x] typebot_db: healthy
  - [x] typebot_builder: running
  - [x] typebot_viewer: running
  - [x] wppconnect: running
  - [x] wppconnect_bridge: healthy

- [x] **2.3** Verificar logs sem erros críticos
  ```bash
  docker compose logs chatwoot_web | Select-String "error"
  docker compose logs typebot_builder | Select-String "error"
  ```

### FASE 3: Configuração Chatwoot ✅

- [x] **3.1** Acessar Chatwoot
  - URL: http://localhost:3000
  - [x] Página carrega sem erros

- [x] **3.2** Criar conta admin
  - [x] Nome: Admin Leguas
  - [x] Email: partners@leguasfranzinas.pt
  - [x] Senha: (configurada)
  - [x] Account criado com sucesso

- [x] **3.3** Copiar Account ID
  - [x] Navegar em Configurações → Account Settings
  - [x] Copiar Account ID
  - [x] Anotar para uso posterior

- [x] **3.4** Criar Inbox API
  - [x] Navegar em Configurações → Inboxes
  - [x] Clicar em "Add Inbox"
  - [x] Selecionar "API"
  - [x] Nome: "WhatsApp Leguas"
  - [x] Webhook URL: http://leguas_wppconnect_bridge:3500/webhook/chatwoot
  - [x] Criar Inbox

- [x] **3.5** Copiar credenciais
  - [x] Inbox ID: (copiado)
  - [x] API Token: w2w8N98Pv8yqazrHPyqAuwkR
  - [x] Anotar para configurar bridge

- [x] **3.6** Criar Automation Rule
  - [x] Navegar em Configurações → Automations
  - [x] Criar nova rule:
    - Evento: "Message Created"
    - Condições: "Message Type" is "incoming"
    - Ações: "Assign a team or agent" → Typebot
  - [x] Salvar automation

### FASE 4: Configuração Typebot ⚠️ (Parcial)

- [x] **4.1** Acessar Typebot Builder
  - URL: http://localhost:8081
  - [x] Página carrega sem erros

- [x] **4.2** Criar conta
  - [x] Email: admin@leguasfranzinas.pt
  - [x] Senha: (configurada)
  - [x] Conta criada com sucesso

- [x] **4.3** Criar workspace
  - [x] Nome: "Léguas Franzinas"
  - [x] Workspace criado

- [x] **4.4** Criar novo Typebot
  - [x] Nome: "Cadastro Motorista"
  - [x] Template: Blank
  - [x] Bot criado

- [ ] **4.5** Design do fluxo (PENDENTE)
  - [ ] **Bloco 1:** Text - Mensagem de boas-vindas
    - "Olá! Vou te ajudar no cadastro como motorista."
  
  - [ ] **Bloco 2:** Text - Solicitar NIF
    - "Por favor, me informe seu NIF (apenas números):"
  
  - [ ] **Bloco 3:** Input - Capturar NIF
    - Tipo: Number
    - Variável: nif
    - Validação: 9 dígitos
  
  - [ ] **Bloco 4:** Text - Solicitar Nome
    - "Ótimo! Agora me diga seu nome completo:"
  
  - [ ] **Bloco 5:** Input - Capturar Nome
    - Tipo: Text
    - Variável: nome
  
  - [ ] **Bloco 6:** Text - Solicitar Telefone
    - "Qual seu telefone? (com código do país)"
  
  - [ ] **Bloco 7:** Input - Capturar Telefone
    - Tipo: Phone
    - Variável: telefone
  
  - [ ] **Bloco 8:** Text - Solicitar Email
    - "E seu email?"
  
  - [ ] **Bloco 9:** Input - Capturar Email
    - Tipo: Email
    - Variável: email
  
  - [ ] **Bloco 10:** Text - Solicitar Documentos
    - "Agora preciso de alguns documentos (envie fotos ou PDFs):"
    - "1. Carta de Condução"
  
  - [ ] **Bloco 11:** File Upload - Carta de Condução
    - Variável: carta_conducao
    - Tipos aceitos: image/*, application/pdf
  
  - [ ] **Bloco 12:** Text - Solicitar Comprovante
    - "2. Comprovante de Residência"
  
  - [ ] **Bloco 13:** File Upload - Comprovante
    - Variável: comprovante_residencia
    - Tipos aceitos: image/*, application/pdf
  
  - [ ] **Bloco 14:** Webhook - Enviar para Django
    - URL: http://leguas_web:8000/drivers/api/register-typebot/
    - Método: POST
    - Body:
      ```json
      {
        "nif": "{{nif}}",
        "nome": "{{nome}}",
        "telefone": "{{telefone}}",
        "email": "{{email}}",
        "carta_conducao_url": "{{carta_conducao}}",
        "comprovante_residencia_url": "{{comprovante_residencia}}"
      }
      ```
    - Salvar resposta em: webhook_response
  
  - [ ] **Bloco 15:** Condition - Verificar sucesso
    - Se webhook_response.success == true:
      - Text: "✅ Cadastro realizado com sucesso! Em breve entraremos em contato."
    - Se não:
      - Text: "❌ Erro no cadastro: {{webhook_response.error}}"

- [ ] **4.6** Configurar integração Chatwoot (PENDENTE)
  - [ ] Clicar em Settings → Integrations
  - [ ] Adicionar Chatwoot:
    - Base URL: http://leguas_chatwoot_web:3000
    - Account ID: (do passo 3.3)
    - Inbox ID: (do passo 3.5)
    - API Token: (do passo 3.5)
  - [ ] Testar conexão (deve retornar sucesso)

- [ ] **4.7** Publicar bot (PENDENTE)
  - [ ] Clicar em "Publish"
  - [ ] Confirmar publicação
  - [ ] URL do bot gerada

### FASE 5: Configuração WPPConnect Bridge ✅

- [x] **5.1** Atualizar docker-compose.yml
  - [x] Editar seção wppconnect_bridge
  - [x] Adicionar variáveis:
    ```yaml
    CHATWOOT_API_TOKEN: "w2w8N98Pv8yqazrHPyqAuwkR"
    CHATWOOT_ACCOUNT_ID: "(configurado)"
    CHATWOOT_INBOX_ID: "(configurado)"
    ```
  - [x] Salvar arquivo

- [x] **5.2** Reiniciar bridge
  ```bash
  docker compose up -d wppconnect_bridge
  ```

- [x] **5.3** Verificar logs do bridge
  ```bash
  docker compose logs -f wppconnect_bridge
  ```
  - [x] Bridge iniciou sem erros
  - [x] Configuração validada
  - [x] Health check OK

- [x] **5.4** Testar health endpoint
  ```bash
  curl http://localhost:3500/health
  ```
  - [x] Resposta: {"status": "ok", ...}

### FASE 6: Configuração WPPConnect ✅

- [x] **6.1** Editar docker-compose.yml (seção wppconnect)
  ```yaml
  WEBHOOK_GLOBAL_ENABLED: "true"
  WEBHOOK_GLOBAL_URL: "http://leguas_wppconnect_bridge:3500/webhook/wppconnect"
  WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS: "true"
  ```

- [x] **6.2** Reiniciar WPPConnect
  ```bash
  docker compose restart leguas_wppconnect
  ```

- [x] **6.3** Verificar webhook configurado
  ```bash
  docker compose logs leguas_wppconnect | Select-String "webhook"
  ```
  - [x] Webhook URL registrada

- [x] **6.4** WhatsApp conectado
  - [x] QR Code escaneado
  - [x] Sessão ativa: leguas_wppconnect
  - [x] Telefone: +351 915 211 836

### FASE 7: Implementação Django ✅

- [x] **7.1** Criar view register_driver_typebot
  - Arquivo: drivers_app/views.py
  - [x] Importações adicionadas (json, csrf_exempt, require_http_methods)
  - [x] View criada
  - [x] Validações implementadas:
    - [x] NIF obrigatório (9 dígitos)
    - [x] Nome obrigatório
    - [x] Telefone obrigatório
    - [x] Email obrigatório (com validação de formato)
    - [x] NIF único (não duplicado)
  - [x] Criação de Driver com status='pending'
  - [x] Resposta JSON {success: true/false, error: ...}

- [x] **7.2** Adicionar rota
  - Arquivo: drivers_app/urls.py
  - [x] Rota adicionada:
    ```python
    path('api/register-typebot/', views.register_driver_typebot, name='register_driver_typebot')
    ```

- [x] **7.3** Testar endpoint manualmente ✅
  ```powershell
  $body = '{"nif":"123456789","nome":"Joao da Silva Typebot","telefone":"+351911111111","email":"joao.typebot@test.com"}'
  Invoke-RestMethod -Uri 'http://localhost:8000/driversapp/api/register-typebot/' `
    -Method POST `
    -ContentType 'application/json; charset=utf-8' `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
  ```
  - [x] Resposta: {"success": true, "driver_id": "123456789"}
  - [x] Driver criado no banco de dados
  - [x] Validação de NIF duplicado testada ✅
  - [x] Validação de campos faltando testada ✅
  - [x] Validação de NIF inválido testada ✅

- [x] **7.4** Reiniciar container web ✅
  ```powershell
  docker compose restart web
  ```

### FASE 8: Testes End-to-End ⚠️ (Parcial)

- [x] **8.1** Teste de conectividade básica
  - [x] WPPConnect está conectado ao WhatsApp
  - [x] Chatwoot acessível em localhost:3000
  - [x] Typebot acessível em localhost:8081
  - [x] Bridge health check OK

- [x] **8.2** Teste de fluxo de mensagens
  - [x] Enviar "Oi" para número WhatsApp
  - [x] Mensagem aparece no Chatwoot (latência: 2s)
  - [x] Responder do Chatwoot
  - [x] Resposta chega no WhatsApp (latência: < 1s)
  - [x] Taxa de sucesso: 100%
  - [x] Zero duplicação de mensagens
  - [x] Enviar/receber imagens: ✅ Funcionando
  - [x] Enviar/receber documentos (PDF, DOC): ✅ Funcionando
  - [x] Qualidade de mídia preservada

- [ ] **8.3** Teste de cadastro completo (PENDENTE)
  - [ ] Iniciar conversa com "Oi"
  - [ ] Responder com NIF válido
  - [ ] Responder com nome
  - [ ] Responder com telefone
  - [ ] Responder com email
  - [ ] Enviar foto da carta de condução
  - [ ] Enviar comprovante de residência
  - [ ] Receber confirmação de sucesso
  - [ ] Verificar motorista criado no Django admin

- [ ] **8.4** Teste de validação (PENDENTE)
  - [ ] Tentar cadastrar NIF duplicado
  - [ ] Receber mensagem de erro apropriada
  - [ ] Tentar enviar NIF inválido (menos de 9 dígitos)
  - [ ] Receber validação do Typebot

- [ ] **8.5** Teste de fallback humano (PENDENTE)
  - [ ] Enviar mensagem fora do fluxo do bot
  - [ ] Mensagem aparecer no Chatwoot sem resposta automática
  - [ ] Agente humano poder responder manualmente

### FASE 9: Monitoramento ⚠️ (Parcial)

- [x] **9.1** Configurar logs
  ```bash
  # Ver logs de todos os serviços
  docker compose logs -f chatwoot_web typebot_builder wppconnect_bridge
  ```

- [x] **9.2** Verificar métricas
  ```bash
  # Ver uso de recursos
  docker stats
  ```

- [ ] **9.3** Configurar alertas (PENDENTE - Opcional)
  - [ ] Uptime monitoring para Chatwoot
  - [ ] Uptime monitoring para Typebot
  - [ ] Health check do bridge

### FASE 10: Documentação Final ⚠️ (Parcial)

- [x] **10.1** Atualizar README
  - [x] Adicionar seção sobre Omnichannel
  - [x] Incluir URLs de acesso
  - [x] Documentar credenciais (sem senhas!)

- [ ] **10.2** Criar guia de troubleshooting (PENDENTE)
  - [ ] Problemas comuns e soluções
  - [ ] Comandos úteis de debug
  - [ ] Contatos para suporte

- [ ] **10.3** Treinar equipe (PENDENTE)
  - [ ] Como usar o Chatwoot
  - [ ] Como criar/editar fluxos no Typebot
  - [ ] Como visualizar motoristas cadastrados

---

## 📊 Progresso Geral

```
✅ Infraestrutura:   [████████████████████] 4/4   (100%)
✅ Inicialização:    [████████████████████] 3/3   (100%)
✅ Chatwoot:         [████████████████████] 6/6   (100%)
⚠️  Typebot:          [████████████░░░░░░░░] 4/7   ( 57%)
✅ Bridge:           [████████████████████] 4/4   (100%)
✅ WPPConnect:       [████████████████████] 4/4   (100%)
⚠️  Django:           [██████████████░░░░░░] 2/4   ( 50%)
⚠️  Testes:           [████████░░░░░░░░░░░░] 2/5   ( 40%)
⚠️  Monitoramento:    [██████████████░░░░░░] 2/3   ( 67%)
⚠️  Documentação:     [███████░░░░░░░░░░░░░] 1/3   ( 33%)

TOTAL: 32/42 (76%)
```

### 🎯 Status por Categoria

| Categoria | Status | Conclusão |
|-----------|--------|-----------|
| 🟢 Infraestrutura & Conexões | **COMPLETO** | 100% |
| 🟢 Comunicação Bidirecional (Texto + Mídia) | **✅ FUNCIONANDO 100%** | 100% |
| 🟡 Automação (Typebot) | **PENDENTE** | 57% |
| 🟡 Endpoint Django | **IMPLEMENTADO - NÃO TESTADO** | 50% |
| 🟡 Testes E2E | **PARCIAL** | 40% |
| 🟡 Documentação | **PARCIAL** | 60% |

TOTAL: 0/42 (0%)
```

---

## 🎯 Próximos Passos Prioritários

### 1️⃣ ALTA PRIORIDADE - Typebot (Fase 4.5 - 4.7)
- Criar fluxo completo de cadastro de motoristas
- Configurar blocos de captura de dados (NIF, nome, telefone, email)
- Implementar upload de documentos (carta de condução, comprovante)
- Configurar webhook para Django
- Integrar com Chatwoot
- Publicar bot

### 2️⃣ MÉDIA PRIORIDADE - Testes Django (Fase 7.3 - 7.4)
- Testar endpoint `/drivers/api/register-typebot/`
- Validar criação de motoristas no banco
- Verificar validações (NIF duplicado, campos obrigatórios)
- Reiniciar container web

### 3️⃣ MÉDIA PRIORIDADE - Testes E2E (Fase 8.3 - 8.5)
- Testar fluxo completo de cadastro via WhatsApp
- Validar recebimento de mensagens de erro
- Testar fallback para atendimento humano

### 4️⃣ BAIXA PRIORIDADE - Documentação (Fase 10.2 - 10.3)
- Criar guia de troubleshooting
- Treinar equipe no uso do sistema

---

## 🚀 Início Rápido

Execute o script automatizado:

```powershell
.\scripts\setup-omnichannel.ps1
```

Ou siga manualmente as fases acima, marcando cada item conforme concluído.

---

## 📞 Suporte

- **Documentação completa:** [OMNICHANNEL_SETUP.md](OMNICHANNEL_SETUP.md)
- **Resumo Executivo:** [RESUMO_OMNICHANNEL.md](RESUMO_OMNICHANNEL.md)
- **Logs:** `docker compose logs -f [serviço]`
- **Health checks:** `docker compose ps`
- **Restart:** `docker compose restart [serviço]`

---

**Última atualização:** 25/02/2026  
**Versão do Checklist:** 2.0  
**Progresso Total:** 76% (32/42 tarefas concluídas)

