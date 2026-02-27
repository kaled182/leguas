# Integração Typebot no Sistema de Configurações

## Visão Geral

A configuração completa do Typebot foi integrada ao módulo **system_config** do Django, permitindo gerenciamento visual e centralizado de todas as configurações do Typebot através da interface web interna.

**Data de implementação:** 2026-02-26  
**Última atualização:** 2026-02-26 (adicionada autenticação via API Key)  
**Status:** ✅ Implementado e funcional

---

## 🔑 Autenticação: API Key vs Email/Senha

### ✅ API Key (Recomendado)
- **Mais segura**: Pode ser revogada sem alterar senha
- **Mais simples**: Um único campo para configurar
- **Específica**: Criada para integração, não expõe credenciais admin
- **Melhor prática**: Padrão da indústria para APIs

👉 **Ver guia completo**: [TYPEBOT_API_KEY_SETUP.md](TYPEBOT_API_KEY_SETUP.md)

### ⚠️ Email/Senha (Alternativa)
- Menos segura (expõe credenciais admin)
- Mais complexa de gerenciar
- Use apenas se API Key não estiver disponível

---

## O Que Foi Implementado

### 1. ✅ Modelo de Dados (`SystemConfiguration`)

Adicionados **21 novos campos** ao modelo `SystemConfiguration` em [system_config/models.py](system_config/models.py):

#### Campos Principais
- `typebot_enabled` - Boolean para ativar/desativar Typebot
- `typebot_builder_url` - URL do Typebot Builder (padrão: http://localhost:8081)
- `typebot_viewer_url` - URL do Typebot Viewer (padrão: http://localhost:8082)
- `typebot_api_key` - **🔑 API Key do Typebot (RECOMENDADO)**
- `typebot_admin_email` - Email do administrador (alternativa)
- `typebot_admin_password` - Senha do administrador (alternativa)

#### Segurança
- `typebot_encryption_secret` - Chave de criptografia (64 caracteres hex)
- `typebot_disable_signup` - Desabilitar registro público
- `typebot_default_workspace_plan` - Plano padrão (free/starter/pro/unlimited)

#### Integração Database
- `typebot_database_url` - URL PostgreSQL completa

#### Storage S3 (Opcional)
- `typebot_s3_endpoint`
- `typebot_s3_bucket`
- `typebot_s3_access_key`
- `typebot_s3_secret_key`

#### SMTP (Opcional)
- `typebot_smtp_host`
- `typebot_smtp_port`
- `typebot_smtp_username`
- `typebot_smtp_password`
- `typebot_smtp_from`

#### OAuth Google (Opcional)
- `typebot_google_client_id`
- `typebot_google_client_secret`

**Todos os campos sensíveis usam `EncryptedCharField`** para armazenamento seguro.

---

### 2. ✅ Views e Lógica de Negócio

#### View Principal
- `save_config()` - Atualizada para processar todos os campos do Typebot

#### Views Específicas do Typebot

##### `typebot_test_connection` (POST)
- **URL:** `/system/typebot/test-connection/`
- **Função:** Testa conectividade com Typebot Builder
- **Retorna:**
  ```json
  {
    "success": true,
    "builder_url": "http://localhost:8081",
    "viewer_url": "http://localhost:8082",
    "status": "online",
    "auth_status": "authenticated|not_configured|auth_failed",
    "message": "Typebot está acessível e funcionando corretamente"
  }
  ```
- **Validações:**
  - Verifica se Typebot está habilitado
  - Testa endpoint `/api/health`
  - **Se API Key configurada**: Envia header `Authorization: Bearer sk_...`
  - **Se credenciais configuradas**: Tenta autenticação via `/api/auth/signin`
  - Retorna status de autenticação: `api_key_configured|authenticated|not_configured|auth_failed`

##### `typebot_auto_login` (GET)
- **URL:** `/system/typebot/auto-login/`
- **Função:** Redireciona para Typebot Builder com login automático
- **Comportamento:**
  - Se credenciais configuradas: Tenta autenticar via API
  - Se sucesso: Redireciona com sessão ativa
  - Se falha: Redireciona para tela de login normal
  - Se sem credenciais: Redireciona diretamente

##### `typebot_generate_encryption_secret` (POST)
- **URL:** `/system/typebot/generate-secret/`
- **Função:** Gera novo encryption secret (token hex de 32 bytes = 64 caracteres)
- **Retorna:**
  ```json
  {
    "success": true,
    "secret": "a1b2c3d4e5f6...",
    "message": "Novo encryption secret gerado com sucesso"
  }
  ```

---

### 3. ✅ Interface Web Visual

Seção completa adicionada em [system_config/templates/system_config/config.html](system_config/templates/system_config/config.html):

#### Componentes da Interface

##### Header com Status e Ações
```html
- Ícone e título "Typebot - Automação de Conversas"
- Status da conexão (atualizado dinamicamente)
- Botão "Testar Conexão" (chama API via AJAX)
- Botão "Abrir Typebot" (link para auto-login)
```

##### Toggle de Ativação
```html
- Checkbox "Habilitar Typebot"
- Visual destacado com descrição
```

##### URLs de Acesso
```html
- Typebot Builder URL (com placeholder e descrição)
- Typebot Viewer URL (com placeholder e descrição)
```

##### Credenciais Admin
```html
- Email Admin
- Password Admin (campo password com indicação "Opcional")
- Tooltip explicando login automático
```

##### Configurações de Segurança
```html
- Encryption Secret (campo password)
- Botão "Gerar" (AJAX para criar novo secret)
- Checkbox "Desabilitar registro público (recomendado)"
```

##### Database PostgreSQL
```html
- Database URL (campo text com font monospace)
- Placeholder com exemplo de formato
```

##### Seções Opcionais (com <details>)

**S3 Storage:**
- Grid 2 colunas com 4 campos
- Endpoint, Bucket, Access Key, Secret Key

**SMTP para Emails:**
- Grid 2 colunas com 5 campos
- Host, Port, Username, Password, From

**Google OAuth:**
- 2 campos: Client ID e Client Secret
- Descrição: "Permite login com Google no Typebot"

##### Workspace Plan
```html
- Dropdown com opções: free, starter, pro, unlimited
- Descrição do propósito
```

##### Link para Documentação
```html
- Link para https://docs.typebot.io/self-hosting/configuration
- Incentiva consultar configurações avançadas
```

#### JavaScript Interativo

##### `testTypebotConnection()`
```javascript
- Desabilita botão durante teste
- Mostra loader animado
- Chama API POST /system/typebot/test-connection/
- Atualiza status visual (verde/vermelho)
- Exibe mensagens de sucesso/erro
- Mostra detalhes de autenticação
```

##### `generateTypebotSecret()`
```javascript
- Chama API POST /system/typebot/generate-secret/
- Preenche campo automaticamente
- Mostra temporariamente o valor gerado
- Animation ring pulsando
- Mensagem de sucesso temporária
- Volta para password após 3s
```

---

### 4. ✅ Rotas (URLs)

Adicionadas em [system_config/urls.py](system_config/urls.py):

```python
# Typebot
path('typebot/test-connection/', views.typebot_test_connection, name='typebot_test_connection'),
path('typebot/auto-login/', views.typebot_auto_login, name='typebot_auto_login'),
path('typebot/generate-secret/', views.typebot_generate_encryption_secret, name='typebot_generate_secret'),
```

---

### 5. ✅ Migrations

**Migration criada:** `system_config/migrations/0002_systemconfiguration_typebot_admin_email_and_more.py`

**Campos adicionados:** 20 campos relacionados ao Typebot

**Status:** ✅ Aplicada ao banco de dados

---

## Como Usar

### 1. Acessar Configurações

```
http://localhost:8000/system/
```

### 2. Expandir Seção "Typebot - Automação de Conversas"

A seção aparece aberta por padrão (`<details open>`).

### 3. Configurar URLs

```
Builder URL: http://localhost:8081
Viewer URL: http://localhost:8082
```

ou URLs de produção:

```
Builder URL: https://typebot.leguasfranzinas.pt
Viewer URL: https://chat.leguasfranzinas.pt
```

### 4. Configurar Credenciais Admin (Opcional)

```
Email: admin@leguasfranzinas.pt
Password: sua_senha_aqui
```

**Benefício:** Permite login automático ao clicar "Abrir Typebot"

### 5. Gerar Encryption Secret

1. Clicar no botão **"Gerar"** ao lado do campo Encryption Secret
2. Um secret de 64 caracteres será gerado automaticamente
3. O secret aparecerá temporariamente no campo

### 6. Configurar Database (Obrigatório)

```
postgresql://typebot_user:password@leguas_typebot_db:5432/typebot_db
```

### 7. Configurações Opcionais

- **S3:** Se quiser armazenar uploads em S3
- **SMTP:** Se quiser enviar emails via Typebot
- **Google OAuth:** Se quiser permitir login com Google

### 8. Ativar Typebot

Marcar checkbox **"Habilitar Typebot"**

### 9. Guardar Configurações

Clicar em **"Guardar Configurações"** no final da página.

### 10. Testar Conexão

Clicar em **"Testar Conexão"**

**Resultados possíveis:**
- ✅ Verde: "Typebot está acessível | Login OK"
- ⚠️ Amarelo: "Typebot está acessível | Credenciais não configuradas"
- ❌ Vermelho: "Não foi possível conectar ao Typebot Builder"

### 11. Abrir Typebot

Clicar em **"Abrir Typebot"**

- Se credenciais configuradas: Login automático
- Senão: Redireciona para tela de login

---

## Integração com Docker

### Variáveis de Ambiente do Typebot

As configurações armazenadas no Django podem ser exportadas como variáveis de ambiente para o container Typebot:

```yaml
# docker-compose.yml
typebot_builder:
  environment:
    - ENCRYPTION_SECRET=${TYPEBOT_ENCRYPTION_SECRET}
    - DATABASE_URL=${TYPEBOT_DATABASE_URL}
    - NEXTAUTH_URL=http://localhost:8081
    - NEXT_PUBLIC_VIEWER_URL=http://localhost:8082
    - ADMIN_EMAIL=${TYPEBOT_ADMIN_EMAIL}
    # ... outras variáveis
```

### Script de Sincronização (Futuro)

Pode-se criar um management command para sincronizar:

```python
# management/commands/sync_typebot_env.py
python manage.py sync_typebot_env
```

Isso geraria um arquivo `.env.typebot` com todas as configurações.

---

## Segurança

### Campos Criptografados

Todos os campos sensíveis usam `EncryptedCharField`:
- Senhas
- API Keys
- Secrets
- Database URLs
- Tokens OAuth

### Auditoria

Todas as mudanças são registradas em `ConfigurationAudit`:
- Usuário que fez a mudança
- Timestamp
- IP Address
- Campos alterados

### CSRF Protection

Todas as views POST usam:
```python
@login_required
@require_http_methods(["POST"])
```

E templates incluem `{% csrf_token %}`.

---

## Testes

### Teste Manual Completo

1. **Configurar campos básicos**
   - Builder URL, Viewer URL
   - Admin email/password
   - Database URL

2. **Gerar Secret**
   - Clicar "Gerar"
   - Verificar que aparece valor hex de 64 caracteres

3. **Guardar configurações**

4. **Testar conexão**
   - Deve retornar status online
   - Verificar se autenticação funcionou

5. **Abrir Typebot**
   - Deve redirecionar e fazer login (se credenciais corretas)

6. **Verificar auditoria**
   - Admin → Configuration Audit
   - Deve ter registro da alteração

### Teste de API

```powershell
# Teste de conexão
Invoke-RestMethod -Uri 'http://localhost:8000/system/typebot/test-connection/' `
  -Method POST `
  -Headers @{ 'X-CSRFToken' = 'seu_token' } `
  -WebSession $session

# Gerar secret
Invoke-RestMethod -Uri 'http://localhost:8000/system/typebot/generate-secret/' `
  -Method POST `
  -Headers @{ 'X-CSRFToken' = 'seu_token' } `
  -WebSession $session
```

---

## Troubleshooting

### Problema: "Typebot não está habilitado"

**Solução:** Marcar checkbox "Habilitar Typebot" e guardar.

### Problema: "Não foi possível conectar ao Typebot Builder"

**Diagnóstico:**
1. Verificar se container está rodando:
   ```powershell
   docker compose ps typebot_builder
   ```

2. Verificar URL configurada
   - Deve ser `http://localhost:8081` para acesso local
   - Ou `http://leguas_typebot_builder:8081` se dentro do Docker

3. Testar manualmente:
   ```powershell
   Invoke-WebRequest -Uri 'http://localhost:8081/api/health'
   ```

### Problema: "Login automático não funciona"

**Possíveis causas:**
- Credenciais incorretas
- Typebot API mudou formato
- CORS bloqueando requisição

**Solução:**
- Verificar credenciais no Typebot Admin
- Consultar logs do Django:
  ```powershell
  docker compose logs web --tail 50 | Select-String "typebot"
  ```

### Problema: Campos não aparecem salvos

**Solução:**
1. Verificar se migrations foram aplicadas:
   ```powershell
   docker compose exec web python manage.py showmigrations system_config
   ```

2. Aplicar migrations:
   ```powershell
   docker compose exec web python manage.py migrate system_config
   ```

---

## Próximos Passos

### Melhorias Futuras

- [ ] **Auto-sync com .env:** Command para gerar `.env.typebot` automaticamente
- [ ] **Dashboard de Status:** Card visual mostrando status do Typebot em tempo real
- [ ] **Testes Automatizados:** Pytest para todas as views
- [ ] **Webhook Management:** Interface para gerenciar webhooks do Typebot
- [ ] **Bot Templates:** Importar/exportar templates de bots
- [ ] **Analytics:** Estatísticas de uso dos bots
- [ ] **Multi-Workspace:** Suporte para múltiplos workspaces Typebot

### Integração com Chatwoot

Próximo passo: Conectar Typebot com Chatwoot configurado

```
Chatwoot → Automation → Trigger Typebot
                ↓
         Typebot executa flow
                ↓
         Django API processa
                ↓
      Dados salvos no sistema
```

---

## Referências

- [Documentação Oficial Typebot](https://docs.typebot.io/)
- [Typebot Self-Hosting Configuration](https://docs.typebot.io/self-hosting/configuration)
- [Typebot API Reference](https://docs.typebot.io/api)
- [Django EncryptedFields](https://django-cryptography.readthedocs.io/)

---

**Implementado por:** Sistema Léguas Franzinas  
**Data:** 2026-02-26  
**Versão:** 1.0  
**Status:** ✅ Operacional
