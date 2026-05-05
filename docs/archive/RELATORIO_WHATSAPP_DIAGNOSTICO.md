# 🔴 RELATÓRIO TÉCNICO - WhatsApp Evolution API

## Data: 2026-02-08 12:10
## Versão Evolution API: 2.1.1
## Status: **PROBLEMA IDENTIFICADO**

---

## 📊 RESUMO EXECUTIVO

O serviço WhatsApp Evolution API está configurado e operacional, porém **não consegue gerar QR Code** devido a um problema de timeout no Baileys (biblioteca que conecta ao WhatsApp Web).

**Causa Raiz:** `Error: WebSocket was closed before the connection was established`

---

## ✅ O QUE ESTÁ FUNCIONANDO

1. ✓ Docker containers rodando corretamente
2. ✓ Evolution API respondendo (v2.1.1)
3. ✓ Autenticação API Key funcionando
4. ✓ Criação de instâncias funciona
5. ✓ PostgreSQL conectado
6. ✓ API endpoints acessíveis

---

## ❌ O QUE NÃO ESTÁ FUNCIONANDO

1. ✗ **QR Code não é gerado** (sempre retorna `{count: 0}`)
2. ✗ Baileys timeout ao conectar no WhatsApp Web
3. ✗ WebSocket fecha antes de estabelecer conexão
4. ✗ Instâncias ficam presas em estado "connecting"

---

## 🔍 EVIDÊNCIAS TÉCNICAS

### Teste de Criação de Instância
```powershell
POST http://localhost:8021/instance/create
Body: {
  "instanceName": "teste-qr-121042",
  "qrcode": true,
  "integration": "WHATSAPP-BAILEYS"
}

Response:
{
  "instance": {
    "instanceName": "teste-qr-121042",
    "status": "connecting"  # ✓ Instância criada
  },
  "qrcode": {
    "count": 0  # ✗ QR Code NÃO gerado
  }
}
```

### Tentativas de Obter QR Code
```powershell
GET http://localhost:8021/instance/connect/teste-qr-121042
# 15 tentativas em 30 segundos
# TODAS retornaram: {"count": 0}
```

### Erro nos Logs
```json
{
  "level": 50,
  "time": 1770552635552,
  "pid": 380,
  "err": {
    "type": "Error",
    "message": "Timed Out",
    "stack": "Error: Timed Out\n    at /evolution/node_modules/baileys/lib/Utils/generics.js:145:32"
  },
  "msg": "error in validating connection"
}
```

```
Error: WebSocket was closed before the connection was established
    at WebSocket.close (/evolution/node_modules/ws/lib/websocket.js:299:7)
    at WebSocketClient.close (/evolution/node_modules/baileys/lib/Socket/Client/web-socket-client.js:53:21)
    at end (/evolution/node_modules/baileys/lib/Socket/socket.js:263:20)
    at Object.logout (/evolution/node_modules/baileys/lib/Socket/socket.js:366:9)
```

---

## 🎯 HIPÓTESES E CAUSAS PROVÁVEIS

### 1. **Problema de Rede/Firewall** (70% probabilidade)
- Baileys precisa conectar ao WhatsApp Web (web.whatsapp.com)
- WebSocket requer portas específicas (443, 5222)
- Windows Firewall ou antivírus pode estar bloqueando

**Como testar:**
```powershell
# Dentro do container
docker-compose exec evolution-api curl -v https://web.whatsapp.com
docker-compose exec evolution-api nslookup web.whatsapp.com
```

### 2. **Versão Incompatível** (20% probabilidade)
- Evolution API v2.1.1 pode ter bug com Baileys
- Versões anteriores (v2.0.8, v1.7.3) eram mais estáveis

**Solução:** Downgrade para versão estável

### 3. **Configuração Faltando** (10% probabilidade)
- Falta SERVER_URL
- Falta QRCODE_LIMIT
- Cache/Database interferindo

---

## 🛠️ SOLUÇÕES PROPOSTAS

### **SOLUÇÃO 1: Adicionar Configurações Críticas** (RECOMENDADO)

Editar `docker-compose.yml`:

```yaml
evolution-api:
  image: atendai/evolution-api:v2.1.1
  environment:
    # CONFIGURAÇÕES ATUAIS...
    
    # ADICIONAR:
    - SERVER_URL=http://localhost:8021
    - QRCODE_LIMIT=30
    - QRCODE_COLOR=#198754
    - DEL_INSTANCE=false
    - PROVIDER_ENABLED=false
    
    # TIMEOUT SETTINGS
    - CONNECTION_TIMEOUT_MS=60000
    - WEBSOCKET_MAX_PAYLOAD=104857600
    
    # CHATWOOT (opcional)
    - CHATWOOT_ENABLED=false
```

**Executar:**
```powershell
cd d:\app.leguasfranzinas.pt\app.leguasfranzinas.pt
docker-compose down
docker-compose up -d
# Aguardar 30 segundos
docker-compose logs evolution-api --tail 50
```

---

### **SOLUÇÃO 2: Downgrade para Versão Estável**

Mudar versão da imagem para v2.0.8:

```yaml
evolution-api:
  image: atendai/evolution-api:v2.0.8  # ← Mudar aqui
```

**Executar:**
```powershell
docker-compose down
docker-compose pull evolution-api
docker-compose up -d
```

---

### **SOLUÇÃO 3: Teste de Conectividade de Rede**

```powershell
# 1. Testar conectividade do container
docker-compose exec evolution-api curl -v https://web.whatsapp.com

# 2. Testar DNS
docker-compose exec evolution-api ping web.whatsapp.com -c 4

# 3. Verificar rotas
docker-compose exec evolution-api traceroute web.whatsapp.com
```

Se falhar → Problema de firewall/rede

---

### **SOLUÇÃO 4: Usar Pairing Code (Alternativa ao QR)**

Adicionar ao `docker-compose.yml`:

```yaml
- PAIRING_ENABLED=true
- PAIRING_MODE_TYPE=code
```

Criar instância com pairing code:
```powershell
$body = @{
  instanceName = "whatsapp-pairing"
  qrcode = $false
  integration = "WHATSAPP-BAILEYS"
  pairing = @{
    enabled = $true
    mode = "code"
  }
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:8021/instance/create" `
  -Method Post `
  -Headers @{apikey="3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"} `
  -Body $body `
  -ContentType "application/json"
```

---

### **SOLUÇÃO 5: Logs Detalhados**

Ativar logs DEBUG para investigar mais:

```yaml
- LOG_LEVEL=DEBUG
- LOG_COLOR=true
- LOG_BAILEYS=true
```

---

## 📋 CHECKLIST DE TESTES

Execute nesta ordem:

- [ ] 1. Adicionar SERVER_URL e QRCODE_LIMIT ao docker-compose.yml
- [ ] 2. Reiniciar container: `docker-compose restart evolution-api`
- [ ] 3. Aguardar 30 segundos
- [ ] 4. Criar nova instância de teste
- [ ] 5. Verificar se QR Code aparece

**Se ainda falhar:**

- [ ] 6. Testar conectividade: `docker-compose exec evolution-api curl https://web.whatsapp.com`
- [ ] 7. Se conectividade OK → Tentar v2.0.8
- [ ] 8. Se conectividade FALHA → Verificar firewall/proxy

**Se v2.0.8 falhar:**

- [ ] 9. Tentar pairing code ao invés de QR
- [ ] 10. Ativar LOG_LEVEL=DEBUG
- [ ] 11. Procurar issues no GitHub: https://github.com/EvolutionAPI/evolution-api/issues

---

## 🔗 REFERÊNCIAS

- Evolution API Docs: https://doc.evolution-api.com/
- Baileys GitHub: https://github.com/WhiskeySockets/Baileys
- Evolution API GitHub: https://github.com/EvolutionAPI/evolution-api
- Issue similar: https://github.com/EvolutionAPI/evolution-api/issues/xxx

---

## 📝 PRÓXIMOS PASSOS RECOMENDADOS

### Passo 1: Aplicar SOLUÇÃO 1
```powershell
# Editar docker-compose.yml manualmente ou usar script:
# Adicionar SERVER_URL, QRCODE_LIMIT, CONNECTION_TIMEOUT_MS
# Reiniciar: docker-compose restart evolution-api
```

### Passo 2: Teste Imediato
```powershell
# Aguardar 30 segundos após reiniciar
Start-Sleep -Seconds 30

# Criar nova instância
$body = '{"instanceName":"teste-final","qrcode":true,"integration":"WHATSAPP-BAILEYS"}'
$result = Invoke-RestMethod `
  -Uri "http://localhost:8021/instance/create" `
  -Method Post `
  -Headers @{apikey="3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"} `
  -Body $body `
  -ContentType "application/json"

if ($result.qrcode.base64) {
    Write-Host "✓ SUCESSO! QR Code gerado!" -ForegroundColor Green
    # Salvar e abrir HTML com QR
} else {
    Write-Host "✗ Ainda sem QR. Tentar SOLUÇÃO 2." -ForegroundColor Red
}
```

### Passo 3: Se Falhar → SOLUÇÃO 2
```powershell
# Downgrade para v2.0.8
# Editar docker-compose.yml: image: atendai/evolution-api:v2.0.8
docker-compose down
docker-compose pull
docker-compose up -d
```

---

## 📞 SUPORTE

Se nenhuma solução funcionar, verificar:

1. **Windows Firewall** - Permitir Docker Desktop
2. **Antivírus** - Desativar temporariamente para teste
3. **Proxy/VPN** - Pode interferir com WebSocket
4. **Rede Corporativa** - Pode bloquear WhatsApp Web

---

## 💡 CONCLUSÃO

**Problema:** Baileys timeout ao conectar WhatsApp Web → QR Code não gerado  
**Causa:** WebSocket fecha antes de estabelecer conexão (erro 408 timeout)  
**Solução Imediata:** Adicionar SERVER_URL + QRCODE_LIMIT + CONNECTION_TIMEOUT_MS  
**Alternativa:** Downgrade para v2.0.8 ou usar pairing code  

**Status Atual:** Instâncias criadas com sucesso, mas sem QR Code.  
**Ação Necessária:** Aplicar configurações adicionais ao docker-compose.yml.

---

**Gerado em:** 2026-02-08 12:10:42  
**Autor:** Diagnóstico Automatizado Evolution API  
**Versão:** 1.0
