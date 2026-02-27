# 🔑 Credenciais de Acesso - Sistema Leguas Franzinas

**⚠️ DOCUMENTO CONFIDENCIAL - AMBIENTE DE DESENVOLVIMENTO**

---

## 🌐 Sistema Principal Django

- **URL:** http://localhost:8000
- **Admin URL:** http://localhost:8000/admin/
- **Usuário:** admin@leguas.pt
- **Senha:** admin
- **Status:** ✅ Operacional

---

## 💬 Chatwoot (Central de Atendimento)

- **URL:** http://localhost:3000
- **Email:** partners@leguasfranzinas.pt
- **Senha:** (usar senha existente)
- **API Token:** w2w8N98Pv8yqazrHPyqAuwkR
- **Account ID:** (verificar em Configurações)
- **Inbox ID:** (verificar em Configurações)
- **Status:** ✅ Operacional

---

## 📱 WPPConnect (Gateway WhatsApp)

- **URL:** http://localhost:21465
- **Sessão:** leguas_wppconnect
- **Telefone:** +351 915 211 836
- **Secret Key:** (gerar via API se necessário)
- **Status:** ✅ Operacional

---

## 🤖 Typebot (Automação)

- **Builder URL:** http://localhost:8081
- **Viewer URL:** http://localhost:8082
- **Email:** admin@leguasfranzinas.pt
- **Senha:** (usar senha existente)
- **Workspace:** Léguas Franzinas
- **Status:** ✅ Operacional

---

## 🔗 WPPConnect Bridge

- **URL:** http://localhost:3500
- **Health Check:** http://localhost:3500/health
- **Webhook Chatwoot:** http://localhost:3500/webhook/chatwoot
- **Webhook WPPConnect:** http://localhost:3500/webhook/wppconnect
- **Status:** ✅ Operacional

---

## 🗄️ Banco de Dados MySQL

- **Host:** localhost
- **Porta:** 3307 (externa) / 3306 (interna)
- **Database:** leguas_db
- **Usuário:** leguas_user
- **Senha:** leguas_password_dev
- **Root Password:** root_password_dev
- **Status:** ✅ Operacional

### Comando de Acesso:
```bash
docker exec leguas_mysql mysql -u leguas_user -pleguas_password_dev leguas_db
```

---

## 📦 Redis (Cache)

- **Host:** localhost
- **Porta:** 6379
- **Status:** ✅ Operacional

---

## 🔐 Secrets e Chaves

### Django
- **SECRET_KEY:** (verificar em .env.docker)
- **FERNET_KEY:** (para criptografia de campos sensíveis)

### Chatwoot
- **SECRET_KEY_BASE:** (64 caracteres hex)
- **ENCRYPTION_SECRET:** (32 caracteres uppercase)

---

## 📊 URLs de Acesso Rápido

| Serviço | URL | Descrição |
|---------|-----|-----------|
| Django Admin | http://localhost:8000/admin/ | Administração do sistema |
| Chatwoot | http://localhost:3000 | Central de atendimento |
| Typebot Builder | http://localhost:8081 | Criação de bots |
| Typebot Viewer | http://localhost:8082 | Visualização de bots |
| WPPConnect | http://localhost:21465 | Gateway WhatsApp |
| Bridge Health | http://localhost:3500/health | Status do bridge |

---

## 🚨 Importante

1. **Estas credenciais são para AMBIENTE DE DESENVOLVIMENTO apenas**
2. **NUNCA compartilhe estas credenciais publicamente**
3. **Em produção, use credenciais diferentes e seguras**
4. **Altere todas as senhas antes de colocar em produção**
5. **Use variáveis de ambiente para senhas em produção**

---

## 🔄 Como Resetar Senha do Django Admin

```bash
docker exec -it leguas_web python manage.py changepassword admin@leguas.pt
```

Ou via shell do Django:
```bash
docker exec leguas_web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); user = User.objects.get(email='admin@leguas.pt'); user.set_password('nova_senha'); user.save(); print('Senha alterada com sucesso.')"
```

---

**Última atualização:** 25/02/2026  
**Ambiente:** Desenvolvimento  
**Versão:** 1.0
