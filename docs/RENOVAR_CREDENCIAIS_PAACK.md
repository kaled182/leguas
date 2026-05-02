# Como Renovar Credenciais da Integração Paack

## 🔑 ACESSO RÁPIDO - Editar Credenciais Paack

### Opção 1: Via Interface Web (RECOMENDADO)

1. **Acesse o Dashboard de Integrações:**
   - URL: `http://localhost:8000/core/integrations/dashboard/`
   - Ou navegue: Menu lateral → **Parceiros** → **Dashboard Integrações**

2. **Encontre a integração Paack** na lista de "Integrações com Sincronização Atrasada"

3. **Clique em "Ver detalhes →"** ao lado da integração Paack

4. **Na página do parceiro Paack**, encontre a seção "Integrações"

5. **Clique no ícone de edição (lápis)** na integração Paack

6. **Preencha os novos dados:**
   - **Tipo de Autenticação**: Selecione "Paack/AppSheet (Custom)"
   - **API URL (AppSheet)**: `https://www.appsheet.com/api/template/44f40de7-ca6e-49a2-9179-9b1c38b34150/`
   - **Cookie Key**: Cole o novo cookie (começa com `.JEENEEATH-3P=...`)
   - **Sync Token (JWT)**: Cole o novo token JWT (começa com `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`)

7. **Clique em "Salvar Alterações"**

8. **Teste a sincronização:** Na página do parceiro, clique em "Sincronizar Agora" (botão azul)

---

### Opção 2: Via Django Shell (Avançado)

```bash
docker exec -it leguas_web python manage.py shell
```

```python
from core.models import PartnerIntegration

# Pegar integração Paack
integration = PartnerIntegration.objects.get(partner__name="Paack")

# Atualizar credenciais
integration.auth_config["api_url"] = "https://www.appsheet.com/api/template/44f40de7-ca6e-49a2-9179-9b1c38b34150/"
integration.auth_config["cookie_key"] = "NOVO_COOKIE_AQUI"
integration.auth_config["sync_token"] = "NOVO_TOKEN_JWT_AQUI"
integration.save()

print("✅ Credenciais atualizadas!")
```

---

## 📋 ONDE OBTER AS NOVAS CREDENCIAIS

### No AppSheet Portal:

1. Acesse: https://www.appsheet.com
2. Faça login com sua conta
3. Abra o aplicativo Paack
4. **Obter API URL:**
   - Vá em **Settings** → **Integrations** → **API**
   - Copie a "Template URL"

5. **Obter Cookie e Token:**
   - Abra **Developer Tools** (F12) no navegador
   - Vá na aba **Network**
   - Faça qualquer ação no app (ex: sync)
   - Procure por requisições para `appsheet.com/api/`
   - Clique na requisição → **Headers**
   - Copie:
     - `Cookie` (campo completo que começa com `.JEENEEATH-3P=...`)
     - `Authorization` (token JWT que começa com `eyJhbGci...`)

---

## ✅ VALIDAR SE FUNCIONOU

Após atualizar as credenciais:

### 1. Testar via Command Line:
```bash
docker exec -it leguas_web python manage.py sync_partner --partner=paack --verbose
```

**Resultado esperado:**
```
🚀 Iniciando sincronização: paack...
🌐 Conectando com API Paack...
📡 Enviando requisição POST...
📨 Resposta recebida - Status: 200
✅ JSON decodificado com sucesso
✅ Sincronização concluída!

📊 ESTATÍSTICAS:
   • Total processado: 123
   • Pedidos criados: 45
   • Pedidos atualizados: 78
```

### 2. Testar via Web:
1. Acesse: `http://localhost:8000/core/partners/1/` (página do Paack)
2. Clique em **"Sincronizar Agora"** (botão azul)
3. Aguarde a resposta (aparecerá mensagem de sucesso ou erro)
4. Verifique a seção "Últimas Sincronizações" - deve aparecer uma nova entrada com status "✅ Sucesso"

---

## 🔍 VERIFICAR VALIDADE DO TOKEN

Para verificar se o token JWT está expirado:

```bash
# Cole esse script em um arquivo (ex: check_token.py)
python
```

```python
import json
import base64
from datetime import datetime

# Cole seu token aqui
token = "SEU_TOKEN_JWT_AQUI"

# Decodificar
parts = token.split(".")
payload_base64 = parts[1]
padding = 4 - len(payload_base64) % 4
if padding != 4:
    payload_base64 += "=" * padding

payload = json.loads(base64.b64decode(payload_base64))

# Verificar expiraçãoexp = datetime.fromtimestamp(payload["exp"])
now = datetime.now()

print(f"Expira em: {exp}")
print(f"Agora: {now}")

if now > exp:
    print("\n❌ TOKEN EXPIRADO!")
    dias = (now - exp).days
    print(f"   Expirou há {dias} dias")
else:
    dias = (exp - now).days
    print(f"\n✅ TOKEN VÁLIDO (expira em {dias} dias)")
```

---

## 📝 TROUBLESHOOTING

### Erro: "401 Unauthorized"
**Causa**: Token expirado ou inválido  
**Solução**: Renovar credenciais no AppSheet

### Erro: "Tipo de integração não suportado"
**Causa**: `auth_type` não está definido como `"custom_paack"`  
**Solução**: 
1. Editar integração via web
2. Selecionar "Paack/AppSheet (Custom)" no dropdown
3. Salvar

### Erro: Template rendering (selectattr)
**Causa**: Bug corrigido no template  
**Solução**: Já corrigido! Reinicie o container:
```bash
docker restart leguas_web
```

### Sincronização não aparece no dashboard
**Causa**: Integração marcada como inativa  
**Solução**:
1. Editar integração
2. Marcar checkbox "Integração Ativa"
3. Salvar

---

## 🎯 RESUMO RÁPIDO

1. **Acesse**: http://localhost:8000/core/partners/1/
2. **Clique**: No ícone de edição (lápis) da integração Paack
3. **Selecione**: "Paack/AppSheet (Custom)" no tipo de autenticação
4. **Cole**: API URL, Cookie Key e Sync Token novos
5. **Salve** e **teste** a sincronização

✅ **PRONTO!** Sua integração Paack está renovada e funcional.

---

**Documentação atualizada em**: 01/03/2026  
**Sistema**: Leguas Delivery Management - Integração Multi-Partner
