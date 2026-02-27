# Configuração do Fluxo Typebot - Cadastro de Motoristas

## Visão Geral

Este documento detalha como configurar o fluxo automatizado de cadastro de motoristas usando Typebot.

**URL Builder:** http://localhost:8081  
**URL Viewer:** http://localhost:8082  
**Objetivo:** Automatizar coleta de dados de motoristas via WhatsApp e enviar para Django

---

## Arquitetura do Fluxo

```
WhatsApp → Chatwoot → Typebot → Django API → Database
                          ↓
                    Validação e Processamento
```

---

## Passo a Passo: Criando o Fluxo (15 Blocos)

### 1. Criar Novo Bot

1. Acesse http://localhost:8081
2. Clique em **"Create a typebot"**
3. Nome: `Cadastro Motorista`
4. Selecione **"Start from scratch"**

---

### 2. Estrutura dos Blocos

#### **BLOCO 1: Mensagem de Boas-Vindas**
- **Tipo:** Text
- **Conteúdo:**
  ```
  Olá! 👋
  
  Bem-vindo ao processo de cadastro de motoristas da Léguas Franzinas.
  
  Vou guiá-lo através do processo de registro. São apenas alguns passos rápidos.
  
  Vamos começar?
  ```
- **Botões:**
  - ✅ Sim, vamos começar
  - ❌ Cancelar

---

#### **BLOCO 2: Confirmação de Início**
- **Tipo:** Condition
- **Condição:**
  - Se resposta = "Sim, vamos começar" → Continue
  - Se resposta = "Cancelar" → Bloco de cancelamento

---

#### **BLOCO 3: Solicitar NIF**
- **Tipo:** Text
- **Conteúdo:**
  ```
  Perfeito! Vamos começar.
  
  📝 Por favor, informe o seu NIF (Número de Identificação Fiscal):
  
  *Exemplo: 123456789*
  ```

---

#### **BLOCO 4: Capturar NIF**
- **Tipo:** Text Input
- **Nome da variável:** `nif`
- **Validação:**
  - Tipo: Number
  - Comprimento: Exatamente 9 dígitos
  - Mensagem de erro: "NIF inválido. Digite 9 dígitos numéricos."

---

#### **BLOCO 5: Confirmar NIF**
- **Tipo:** Text
- **Conteúdo:**
  ```
  NIF recebido: {{nif}}
  
  ✅ O NIF está correto?
  ```
- **Botões:**
  - ✅ Sim, está correto
  - ❌ Não, corrigir

---

#### **BLOCO 6: Solicitar Nome Completo**
- **Tipo:** Text
- **Conteúdo:**
  ```
  👤 Agora, por favor, informe o seu nome completo:
  ```

---

#### **BLOCO 7: Capturar Nome**
- **Tipo:** Text Input
- **Nome da variável:** `nome`
- **Validação:**
  - Tipo: Text
  - Mínimo: 3 caracteres
  - Mensagem de erro: "Por favor, digite seu nome completo."

---

#### **BLOCO 8: Solicitar Telefone**
- **Tipo:** Text
- **Conteúdo:**
  ```
  📱 Digite o seu número de telefone:
  
  *Exemplo: +351911111111*
  ```

---

#### **BLOCO 9: Capturar Telefone**
- **Tipo:** Phone Input
- **Nome da variável:** `telefone`
- **País padrão:** Portugal (+351)
- **Validação:**
  - Formato internacional
  - Mensagem de erro: "Número de telefone inválido."

---

#### **BLOCO 10: Solicitar Email**
- **Tipo:** Text
- **Conteúdo:**
  ```
  📧 Por último, informe o seu email:
  
  *Exemplo: motorista@example.com*
  ```

---

#### **BLOCO 11: Capturar Email**
- **Tipo:** Email Input
- **Nome da variável:** `email`
- **Validação:**
  - Formato de email válido
  - Mensagem de erro: "Email inválido."

---

#### **BLOCO 12: Resumo dos Dados**
- **Tipo:** Text
- **Conteúdo:**
  ```
  📋 **Resumo do seu cadastro:**
  
  • NIF: {{nif}}
  • Nome: {{nome}}
  • Telefone: {{telefone}}
  • Email: {{email}}
  
  Tudo está correto?
  ```
- **Botões:**
  - ✅ Sim, enviar cadastro
  - ❌ Não, recomeçar

---

#### **BLOCO 13: Condição de Confirmação**
- **Tipo:** Condition
- **Condição:**
  - Se resposta = "Sim, enviar cadastro" → Bloco 14 (Webhook)
  - Se resposta = "Não, recomeçar" → Retorna ao Bloco 3

---

#### **BLOCO 14: Enviar para Django (Webhook)**
- **Tipo:** Webhook / Make a HTTP Request
- **Configuração:**

```json
{
  "method": "POST",
  "url": "http://leguas_web:8000/driversapp/api/register-typebot/",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "nif": "{{nif}}",
    "nome": "{{nome}}",
    "telefone": "{{telefone}}",
    "email": "{{email}}"
  }
}
```

- **Salvar resposta em:** `api_response`
- **Timeout:** 10 segundos

---

#### **BLOCO 15: Mensagem de Confirmação**
- **Tipo:** Condition
- **Condição:** `api_response.success` = `true`

**Se SUCESSO:**
```
✅ **Cadastro realizado com sucesso!**

Obrigado, {{nome}}!

Seus dados foram recebidos e estão em análise.

📬 Você receberá um email em {{email}} com os próximos passos.

⏰ O processo de aprovação leva até 48 horas úteis.

Se tiver dúvidas, entre em contato conosco.

Até breve! 👋
```

**Se ERRO:**
```
❌ **Ops! Algo deu errado.**

{{api_response.error}}

Por favor, tente novamente ou entre em contato com nosso suporte.

Deseja tentar novamente?
```
- **Botões:**
  - 🔄 Sim, tentar novamente → Volta ao Bloco 3
  - 📞 Falar com atendente → Transferir para humano

---

## 3. Configurações Avançadas

### 3.1 Variáveis do Typebot

Certifique-se de criar essas variáveis no Typebot:

| Variável | Tipo | Descrição |
|----------|------|-----------|
| `nif` | Text | NIF do motorista (9 dígitos) |
| `nome` | Text | Nome completo |
| `telefone` | Text | Telefone com código do país |
| `email` | Text | Email válido |
| `api_response` | Object | Resposta do Django API |

### 3.2 Timeout e Retry

- **Webhook timeout:** 10 segundos
- **Retry on failure:** 3 tentativas
- **Delay entre retries:** 2 segundos

---

## 4. Integração com Chatwoot

### 4.1 Configurar Handoff para Typebot

1. Acesse Chatwoot → Settings → Automation
2. Crie nova automação:
   - **Nome:** "Iniciar cadastro motorista"
   - **Evento:** "Message Created"
   - **Condições:**
     ```
     Message contains "cadastro motorista"
     OR Message contains "quero me cadastrar"
     OR Message contains "trabalhar como motorista"
     ```
   - **Ação:** "Assign to team/agent" → Selecione Typebot

### 4.2 Configurar Handoff de Volta para Humano

No Bloco 15 (caso de erro), adicionar ação:
- **Tipo:** Set Variable
- **Nome:** `handoff_to_human`
- **Valor:** `true`

---

## 5. Testes

### 5.1 Teste Manual no Builder

1. Acesse http://localhost:8081
2. Abra o bot criado
3. Clique em **"Test"** (ícone de play)
4. Percorra todo o fluxo preenchendo dados válidos
5. Verifique se webhook é chamado corretamente

### 5.2 Teste via WhatsApp

1. Envie mensagem no WhatsApp: "quero me cadastrar"
2. Typebot deve iniciar automaticamente
3. Complete o fluxo com dados de teste:
   - NIF: 987654321
   - Nome: Teste Typebot
   - Telefone: +351922222222
   - Email: teste.typebot@example.com

4. Verifique no Django Admin se motorista foi criado:
   ```
   http://localhost:8000/admin/ordersmanager_paack/driver/
   ```

### 5.3 Teste de Validações

Teste cenários de erro:

| Cenário | Entrada | Resultado Esperado |
|---------|---------|-------------------|
| NIF inválido | 12345 | Erro: "NIF inválido. Deve conter exatamente 9 dígitos." |
| NIF duplicado | 123456789 | Erro: "Este NIF já está registrado no sistema." |
| Email inválido | teste@invalido | Erro: "Email inválido." |
| Campos vazios | (vazio) | Erro: "Campos obrigatórios faltando" |

---

## 6. Publicação

### 6.1 Publicar Bot

1. No Typebot Builder, clique em **"Publish"**
2. Copie o **Bot ID** gerado
3. Configure no Chatwoot:
   - Settings → Integrations → Typebot
   - Cole o Bot ID
   - Salve

### 6.2 Monitoramento

Acompanhe logs do Typebot:
```powershell
docker compose logs typebot_viewer -f --tail 50
```

Verifique conversas no Chatwoot:
```
http://localhost:3000/app/accounts/1/conversations
```

---

## 7. Troubleshooting

### Problema: Webhook não está sendo chamado

**Solução:**
1. Verifique se Django está rodando:
   ```powershell
   docker compose ps web
   ```

2. Teste endpoint manualmente:
   ```powershell
   $body = '{"nif":"111111111","nome":"Teste","telefone":"+351911111111","email":"teste@test.com"}'
   Invoke-RestMethod -Uri 'http://localhost:8000/driversapp/api/register-typebot/' `
     -Method POST `
     -ContentType 'application/json; charset=utf-8' `
     -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
   ```

3. Verifique logs Django:
   ```powershell
   docker compose logs web --tail 50
   ```

### Problema: Typebot não inicia no Chatwoot

**Solução:**
1. Verifique se automação está ativa no Chatwoot
2. Teste keyword: envie "cadastro motorista" no WhatsApp
3. Verifique logs:
   ```powershell
   docker compose logs chatwoot_web --tail 50
   ```

### Problema: Dados não chegam ao Django

**Solução:**
1. Verifique formato JSON no Bloco 14
2. Confirme que variáveis estão sendo preenchidas corretamente
3. Use Developer Tools do Typebot para inspecionar valores
4. Verifique se `Content-Type: application/json; charset=utf-8`

---

## 8. Melhorias Futuras

- [ ] Upload de documentos (Carta de Condução, Comprovante)
- [ ] Integração com sistema de aprovação automatizado
- [ ] Notificações por email via SendGrid
- [ ] Validação de NIF em API externa
- [ ] Agendamento de entrevista automatizado

---

## Referências

- [Documentação Typebot](https://docs.typebot.io/)
- [Chatwoot Automation](https://www.chatwoot.com/docs/user-guide/automation)
- [Django Rest Framework](https://www.django-rest-framework.org/)

---

**Última atualização:** 2025-02-26  
**Versão:** 1.0  
**Autor:** Sistema Léguas Franzinas
