# Como Configurar API Key do Typebot

## 📋 Visão Geral

A autenticação via **API Key** é a forma **recomendada** de integrar com Typebot, sendo mais simples e segura que email/senha.

## 🔑 Obtendo a API Key

### 1. Acesse o Typebot Builder
```
http://localhost:8081
```

### 2. Faça Login (primeira vez)
- Email: `admin@leguasfranzinas.pt`
- Password: (sua senha configurada)

### 3. Navegue para Settings
1. Clique no ícone de usuário (canto superior direito)
2. Clique em **"Settings"** ou **"Configurações"**
3. Vá para aba **"API Keys"** ou **"Chaves API"**

### 4. Gere Nova API Key
1. Clique em **"Create API Key"** ou **"Criar Chave API"**
2. Dê um nome: `Django Integration`
3. Clique em **"Create"**
4. **COPIE A CHAVE** (ela começa com `sk_...`)
   - ⚠️ **IMPORTANTE**: A chave só é mostrada UMA VEZ!

## ⚙️ Configurando no Sistema

### Opção 1: Via Interface Web (Recomendado)

1. Acesse: http://localhost:8000/system/
2. Expanda seção **"Typebot - Automação de Conversas"**
3. Localize o campo **"Typebot API Key"** (destaque verde)
4. Cole a chave copiada (formato: `sk_...`)
5. Clique em **"Guardar Configurações"**
6. Teste clicando em **"Testar Conexão"**

### Opção 2: Via Script Python

```python
from system_config.models import SystemConfiguration

config = SystemConfiguration.get_config()
config.typebot_api_key = "sk_sua_chave_aqui"
config.save()
print("✅ API Key configurada!")
```

### Opção 3: Via Terminal

```bash
docker compose exec -T web python manage.py shell <<EOF
from system_config.models import SystemConfiguration
config = SystemConfiguration.get_config()
config.typebot_api_key = "sk_sua_chave_aqui"
config.save()
print("✅ API Key configurada!")
EOF
```

## 🧪 Testando a Configuração

### Teste via Interface Web
1. Na seção Typebot, clique em **"Testar Conexão"**
2. Deve aparecer: ✅ "Typebot está acessível | Auth: api_key_configured"

### Teste via Script
```python
docker compose exec -T web python test_typebot_views.py
```

## 🔐 Vantagens da API Key

### ✅ API Key (Recomendado)
- ✅ Mais segura (pode ser revogada)
- ✅ Não expõe senha
- ✅ Fácil de rotacionar
- ✅ Específica para integração
- ✅ Pode ter permissões limitadas

### ⚠️ Email/Senha (Alternativa)
- ⚠️ Menos segura
- ⚠️ Expõe credenciais admin
- ⚠️ Difícil de revogar
- ⚠️ Acesso total ao sistema

## 📊 Como o Sistema Usa a API Key

Quando você configura a API Key, o sistema:

1. **Testa conexão**: Envia header `Authorization: Bearer sk_...` no health check
2. **Cria bots via API**: Usa API Key para autenticar requisições
3. **Gerencia workspaces**: Acessa recursos do Typebot de forma programática

## 🔄 Rotação de API Keys

Para maior segurança, rotacione periodicamente:

1. Gere nova API Key no Typebot
2. Atualize no sistema Django (http://localhost:8000/system/)
3. Teste a conexão
4. Revogue a API Key antiga no Typebot

## ⚠️ Segurança

### ✅ Boas Práticas
- ✅ Use API Key em vez de email/senha
- ✅ Mantenha a chave em segredo
- ✅ Rotacione regularmente (mensal/trimestral)
- ✅ Use HTTPS em produção
- ✅ Não commite a chave no Git

### ❌ Evite
- ❌ Compartilhar a chave
- ❌ Usar mesma chave em múltiplos ambientes
- ❌ Expor em logs ou mensagens de erro
- ❌ Hard-code no código fonte

## 🆘 Troubleshooting

### Problema: API Key não funciona
```
❌ Erro: Unauthorized
```

**Soluções:**
1. Verifique se a chave está correta (começa com `sk_`)
2. Confirme que a chave não foi revogada no Typebot
3. Teste gerando nova chave

### Problema: Não encontro onde gerar API Key
```
Menu "API Keys" não aparece
```

**Soluções:**
1. Atualize Typebot para versão mais recente
2. Acesse via URL direta: `http://localhost:8081/typebots/settings/account`
3. Use credenciais email/senha temporariamente

## 📚 Referências

- [Documentação Oficial Typebot - API](https://docs.typebot.io/api-reference)
- [Typebot Authentication](https://docs.typebot.io/self-hosting/configuration#authentication)

---

**Última atualização:** 2026-02-26  
**Versão:** 1.1  
**Autor:** Sistema Léguas Franzinas
