# 📱 Guia Completo: Configurar e Usar WhatsApp Evolution API

## 🚀 PASSO 1: Gerar API Key Segura

Primeiro, você precisa gerar uma chave segura para proteger sua API:

### No PowerShell (Windows):
```powershell
# Gerar chave aleatória de 32 caracteres
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})
```

**Exemplo de chave gerada:**
```
A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1
```

⚠️ **IMPORTANTE**: Guarde esta chave! Você vai usar em 3 lugares.

---

## 🔧 PASSO 2: Configurar API Key no Docker

Edite o arquivo `.env.docker` e adicione:

```bash
# WhatsApp Evolution API
EVOLUTION_API_KEY=A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1
```

**Substitua** `A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1` pela chave que você gerou!

### Reiniciar serviço para aplicar:
```powershell
docker-compose restart evolution-api
```

---

## 🌐 PASSO 3: Acessar Evolution Manager

### Abra no navegador:
```
http://localhost:8021/manager/login
```

### Preencha os campos:

1. **Server URL**: `http://localhost:8021`
2. **API Key Global**: `A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1`
   *(use a mesma chave que você configurou no .env.docker)*

3. Clique em **Login**

✅ Você será redirecionado para o painel de gerenciamento!

---

## 📱 PASSO 4: Criar Instância do WhatsApp

Agora você vai criar uma instância para conectar seu WhatsApp:

### Opção A: Via Interface Web (Mais Fácil)

1. No Evolution Manager, clique em **"+ New Instance"**
2. Preencha:
   - **Instance Name**: `leguas-instance`
   - **Integration**: Selecione **WHATSAPP-BAILEYS**
   - **QRCode**: Marque como **Enabled**
3. Clique em **Create**

### Opção B: Via API (PowerShell)

```powershell
$headers = @{
    "apikey" = "A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1"
    "Content-Type" = "application/json"
}

$body = @{
    instanceName = "leguas-instance"
    qrcode = $true
    integration = "WHATSAPP-BAILEYS"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8021/instance/create" -Method Post -Headers $headers -Body $body
```

---

## 📲 PASSO 5: Conectar WhatsApp via QR Code

### 1. Obter QR Code

#### Via Interface Web:
- No Evolution Manager, clique na instância `leguas-instance`
- Clique em **"Connect"**
- O QR Code aparecerá na tela

#### Via API:
```powershell
$headers = @{
    "apikey" = "A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1"
}

$response = Invoke-RestMethod -Uri "http://localhost:8021/instance/connect/leguas-instance" -Method Get -Headers $headers

# O QR Code está em $response.base64
Write-Host "QR Code gerado! Copie o base64 e cole em: https://www.base64-image.de/"
```

### 2. Escanear QR Code no Celular

1. Abra o **WhatsApp** no celular
2. Vá em **⚙️ Configurações**
3. Clique em **📱 Aparelhos Conectados**
4. Clique em **➕ Conectar um aparelho**
5. **Escaneie o QR Code** que apareceu

### 3. Verificar Conexão

Após escanear, aguarde 5-10 segundos e verifique:

```powershell
$headers = @{
    "apikey" = "A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1"
}

Invoke-RestMethod -Uri "http://localhost:8021/instance/connectionState/leguas-instance" -Method Get -Headers $headers
```

**Resposta esperada:**
```json
{
  "instance": "leguas-instance",
  "state": "open"
}
```

✅ Se `state = "open"`, está **CONECTADO**!

---

## ⚙️ PASSO 6: Configurar no Django (System Config)

Agora você vai configurar a integração no sistema Django:

### 1. Acesse o System Config:
```
http://localhost:8000/system/
```

### 2. Role até a seção **WhatsApp (Evolution API)**

### 3. Preencha os campos:

| Campo | Valor |
|-------|-------|
| **☑️ Ativar WhatsApp** | ✅ Marcar |
| **Evolution API URL** | `http://evolution-api:8080` |
| **Evolution API Key** | `A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1` |
| **Nome da Instância** | `leguas-instance` |

⚠️ **ATENÇÃO**: 
- Use `http://evolution-api:8080` (nome do serviço Docker)
- **NÃO** use `http://localhost:8021` (isso é só para seu navegador)

### 4. Clique em **Guardar Configurações**

---

## 💬 PASSO 7: Enviar Primeira Mensagem de Teste

Agora vamos testar enviando uma mensagem!

### Método 1: Via PowerShell

```powershell
$headers = @{
    "apikey" = "A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1"
    "Content-Type" = "application/json"
}

$body = @{
    number = "5511999999999"  # SUBSTITUA pelo número com DDI+DDD
    text = "Olá! Esta é uma mensagem de teste do Léguas Franzinas! 🚚"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8021/message/sendText/leguas-instance" -Method Post -Headers $headers -Body $body
```

### Método 2: Via Django Shell

```powershell
docker-compose exec web python manage.py shell
```

Dentro do shell Python:
```python
from system_config.whatsapp_helper import WhatsAppEvolutionAPI

# Carregar da configuração
whatsapp = WhatsAppEvolutionAPI.from_config()

# Verificar se está conectado
if whatsapp.is_connected():
    # Enviar mensagem
    response = whatsapp.send_text(
        number="5511999999999",  # SUBSTITUA
        text="Olá do Django! 🚚"
    )
    print(f"✅ Mensagem enviada: {response}")
else:
    print("❌ WhatsApp não conectado")
```

---

## 📋 FORMATO DE NÚMEROS

O número DEVE estar no formato internacional:

**Formato**: `55` (DDI Brasil) + `11` (DDD) + `999999999` (número)

**Exemplos:**
- São Paulo: `5511999999999`
- Rio de Janeiro: `5521999999999`
- Curitiba: `5541999999999`

⚠️ **SEM espaços, parênteses, traços ou +**

---

## 🎯 RECURSOS AVANÇADOS

### 1. Enviar Imagem

```python
whatsapp.send_image(
    number="5511999999999",
    image_url="https://exemplo.com/imagem.jpg",
    caption="Aqui está a imagem solicitada!"
)
```

### 2. Enviar Localização

```python
whatsapp.send_location(
    number="5511999999999",
    latitude=-23.5505,
    longitude=-46.6333,
    name="São Paulo",
    address="Av. Paulista, 1578"
)
```

### 3. Enviar Documento

```python
whatsapp.send_document(
    number="5511999999999",
    document_url="https://exemplo.com/relatorio.pdf",
    filename="relatorio_mensal.pdf"
)
```

### 4. Criar Grupo

```python
whatsapp.create_group(
    group_name="Equipe Léguas",
    participants=["5511999999999", "5521888888888"]
)
```

---

## 🔍 TROUBLESHOOTING

### Problema: QR Code não aparece

**Solução:**
```powershell
# Deletar e recriar instância
docker-compose exec web python manage.py shell
```

```python
from system_config.whatsapp_helper import WhatsAppEvolutionAPI

whatsapp = WhatsAppEvolutionAPI.from_config()
whatsapp.delete_instance()
whatsapp.create_instance()
qr = whatsapp.get_qrcode()
print(qr)
```

### Problema: Conexão perdida

**Solução:**
```powershell
# Fazer logout e reconectar
$headers = @{"apikey" = "A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1"}

# Logout
Invoke-RestMethod -Uri "http://localhost:8021/instance/logout/leguas-instance" -Method Delete -Headers $headers

# Esperar 5 segundos
Start-Sleep -Seconds 5

# Conectar novamente (novo QR Code)
Invoke-RestMethod -Uri "http://localhost:8021/instance/connect/leguas-instance" -Method Get -Headers $headers
```

### Problema: Erro 401 Unauthorized

**Causa**: API Key incorreta

**Solução**: Verifique se a API Key nos 3 lugares é a mesma:
1. `.env.docker`
2. Evolution Manager (login)
3. System Config (Django)

### Problema: Mensagem não envia

**Verificar:**
```powershell
# 1. Verificar conexão
$headers = @{"apikey" = "A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1"}
Invoke-RestMethod -Uri "http://localhost:8021/instance/connectionState/leguas-instance" -Method Get -Headers $headers

# 2. Verificar instâncias
Invoke-RestMethod -Uri "http://localhost:8021/instance/fetchInstances" -Method Get -Headers $headers
```

---

## 📊 COMANDOS ÚTEIS

### Ver logs do WhatsApp
```powershell
docker-compose logs -f evolution-api
```

### Reiniciar serviço WhatsApp
```powershell
docker-compose restart evolution-api
```

### Ver todas as instâncias
```powershell
$headers = @{"apikey" = "A7B9C2D4E6F8G1H3I5J7K9L2M4N6O8P1"}
Invoke-RestMethod -Uri "http://localhost:8021/instance/fetchInstances" -Method Get -Headers $headers
```

### Backup da base de dados do WhatsApp
```powershell
docker-compose exec evolution_db pg_dump -U evolution_user evolution_db > whatsapp_backup.sql
```

---

## ✅ CHECKLIST COMPLETO

- [ ] Gerar API Key segura
- [ ] Adicionar API Key ao `.env.docker`
- [ ] Reiniciar Evolution API
- [ ] Acessar Evolution Manager (http://localhost:8021/manager/login)
- [ ] Fazer login com Server URL e API Key
- [ ] Criar instância `leguas-instance`
- [ ] Conectar via QR Code no WhatsApp do celular
- [ ] Verificar que `state = "open"`
- [ ] Configurar no Django System Config
- [ ] Testar envio de mensagem
- [ ] Mensagem recebida ✅

---

## 🎓 RESUMO RÁPIDO

**1. Gere a API Key:**
```powershell
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})
```

**2. Configure no `.env.docker`:**
```
EVOLUTION_API_KEY=sua-chave-aqui
```

**3. Acesse Evolution Manager:**
- URL: http://localhost:8021/manager/login
- Server URL: `http://localhost:8021`
- API Key: sua chave

**4. Crie instância e conecte QR Code**

**5. Configure no Django:**
- URL: http://localhost:8000/system/
- Evolution API URL: `http://evolution-api:8080`
- API Key: sua chave
- Instance: `leguas-instance`

**6. Envie mensagem de teste! 🎉**

---

## 📞 SUPORTE

Para mais informações:
- **Documentação Evolution API**: https://doc.evolution-api.com/
- **Swagger UI**: http://localhost:8021/manager (após login)
- **Código Helper**: `system_config/whatsapp_helper.py`

**Pronto para usar! 🚀**
