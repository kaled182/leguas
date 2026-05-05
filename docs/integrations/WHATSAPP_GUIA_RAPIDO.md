# 🚀 Guia Rápido: WhatsApp Evolution API - Léguas Franzinas

## ✅ Serviço Configurado com Sucesso!

A Evolution API WhatsApp está rodando e pronta para uso.

---

## 📱 Passo 1: Conectar WhatsApp (QR Code)

### Opção A: Via Página HTML (Recomendado)
1. Abra: `qrcode_whatsapp.html` (já deve estar aberta no navegador)
2. Aguarde o QR Code aparecer
3. Abra WhatsApp no celular → **Aparelhos conectados** → **Conectar aparelho**
4. Escaneie o QR Code
5. Aguarde a mensagem "✓ WhatsApp conectado com sucesso!"

### Opção B: Via Evolution Manager
1. Acesse: http://localhost:8021/manager/login
2. Preencha:
   - **Server URL**: `http://localhost:8021`
   - **API Key Global**: `3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW`
3. Clique em **Login**
4. Vá em **Instances** → **leguas-instance** → **Connect**
5. Escaneie o QR Code

---

## ⚙️ Passo 2: Configurar Django System Config

1. Acesse: http://localhost:8000/system/
2. Role até a seção **WhatsApp (Evolution API)**
3. Preencha:

```
☑️ Ativar WhatsApp

Evolution API URL:
http://evolution-api:8080

Evolution API Key:
3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW

Nome da Instância:
leguas-instance
```

4. Clique em **Salvar**

> ⚠️ **IMPORTANTE**: Use `http://evolution-api:8080` (nome do container Docker), **NÃO** use `localhost:8021`

---

## 🧪 Passo 3: Testar Envio de Mensagem

### Via Python (Django Shell):

```python
python manage.py shell
```

```python
from system_config.models import SystemConfiguration
from system_config.whatsapp_helper import WhatsAppEvolutionAPI

# Carregar configuração do sistema
config = SystemConfiguration.objects.first()

# Criar cliente WhatsApp
wa = WhatsAppEvolutionAPI.from_config(config)

# Enviar mensagem de teste
# SUBSTITUA pelo seu número com DDI (ex: 351912345678)
result = wa.send_text(
    number="351XXXXXXXXX",  # Seu número com DDI (sem +)
    text="🎉 WhatsApp Evolution API funcionando!\n\nMensagem enviada via Léguas Franzinas."
)

print(result)
```

### Via API REST (PowerShell):

```powershell
$headers = @{
    "apikey" = "3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"
    "Content-Type" = "application/json"
}

$body = @{
    number = "351XXXXXXXXX"  # Número com DDI (sem +)
    text = "Mensagem de teste da Evolution API!"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://localhost:8021/message/sendText/leguas-instance" `
    -Method Post `
    -Headers $headers `
    -Body $body
```

---

## 📊 Verificar Status da Conexão

### Via PowerShell:
```powershell
$headers = @{"apikey" = "3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"}

Invoke-RestMethod `
    -Uri "http://localhost:8021/instance/connectionState/leguas-instance" `
    -Headers $headers
```

**Resposta esperada quando conectado:**
```json
{
  "instance": {
    "instanceName": "leguas-instance",
    "state": "open"
  }
}
```

---

## 🔧 Comandos Docker Úteis

### Ver logs da Evolution API:
```powershell
docker-compose logs -f evolution-api
```

### Reiniciar serviço:
```powershell
docker-compose restart evolution-api
```

### Ver todos os serviços:
```powershell
docker-compose ps
```

---

## 📝 Informações Importantes

### URLs e Portas:
- **Evolution API**: http://localhost:8021
- **Evolution Manager**: http://localhost:8021/manager
- **PostgreSQL Evolution**: localhost:5433
- **Django**: http://localhost:8000

### Credenciais:
- **API Key**: `3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW`
- **Instance Name**: `leguas-instance`
- **Database**: `evolution_db` (PostgreSQL 15)

### Arquivos de Configuração:
- `docker-compose.yml` - Configuração dos containers
- `.env.docker` - Variáveis de ambiente
- `qrcode_whatsapp.html` - Página para QR Code
- `system_config/whatsapp_helper.py` - Cliente Python

---

## 🎯 Funcionalidades Disponíveis

A Evolution API suporta:

✅ Enviar mensagens de texto  
✅ Enviar imagens com legenda  
✅ Enviar documentos/arquivos  
✅ Enviar localização GPS  
✅ Criar grupos  
✅ Adicionar/remover participantes  
✅ Receber mensagens (via webhook)  
✅ Verificar status de conexão  
✅ Múltiplas instâncias (multi-sessão)

### Exemplos de uso completo:

```python
from system_config.whatsapp_helper import WhatsAppEvolutionAPI

wa = WhatsAppEvolutionAPI(
    base_url="http://evolution-api:8080",
    api_key="3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW",
    instance_name="leguas-instance"
)

# Enviar imagem
wa.send_image(
    number="351912345678",
    image_url="https://example.com/foto.jpg",
    caption="Foto do pedido #123"
)

# Enviar localização
wa.send_location(
    number="351912345678",
    latitude=41.1496,
    longitude=-8.6109,
    name="Escritório Léguas Franzinas",
    address="Porto, Portugal"
)

# Criar grupo
wa.create_group(
    subject="Equipe Léguas",
    participants=["351912345678", "351987654321"]
)
```

---

## ❌ Troubleshooting

### QR Code não aparece:
```powershell
# Verificar se a instância existe
$headers = @{"apikey" = "3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"}
Invoke-RestMethod -Uri "http://localhost:8021/instance/fetchInstances" -Headers $headers
```

### Erro 401 Unauthorized:
- Verifique se a API Key está correta
- Certifique-se de usar `3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW`

### WhatsApp desconectou:
```powershell
# Gerar novo QR Code
$headers = @{"apikey" = "3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"}
Invoke-RestMethod -Uri "http://localhost:8021/instance/connect/leguas-instance" -Headers $headers
```

### Reiniciar tudo do zero:
```powershell
docker-compose down
docker volume rm app.leguasfranzinas.pt_evolution_instances
docker volume rm app.leguasfranzinas.pt_evolution_store
docker-compose up -d
```

---

## 📚 Documentação Completa

- **WHATSAPP_SETUP.md** - Documentação técnica detalhada
- **Evolution API Docs**: https://doc.evolution-api.com/
- **whatsapp_helper.py** - Código do cliente Python com todos os métodos

---

## ✅ Checklist Final

- [ ] WhatsApp conectado via QR Code (status: "open")
- [ ] Django System Config configurado
- [ ] Mensagem de teste enviada com sucesso
- [ ] Webhooks configurados (opcional)
- [ ] Backup da API Key salvo em local seguro

---

**Status Atual**: ✅ Evolution API configurada e funcionando  
**Instância**: leguas-instance  
**Estado**: Aguardando conexão do WhatsApp

Agora é só escanear o QR Code e começar a usar! 🎉
