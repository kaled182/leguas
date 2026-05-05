# 🔧 Correção WhatsApp Evolution API

## ⚠️ Problema Atual

O Docker Desktop está apresentando erro 500 Internal Server Error. Precisa ser reiniciado.

## ✅ Solução Rápida

### 1. Reiniciar Docker Desktop

1. **Clique com botão direito** no ícone do Docker Desktop na bandeja do Windows (próximo ao relógio)
2. Selecione **"Quit Docker Desktop"**
3. Aguarde fechar completamente (ícone some da bandeja)
4. Abra novamente o **Docker Desktop** pelo menu Iniciar
5. Aguarde até aparecer "Docker Desktop is running"

### 2. Após Docker iniciar, execute:

```powershell
# Voltar ao diretório do projeto
cd D:\app.leguasfranzinas.pt\app.leguasfranzinas.pt

# Reiniciar todos os serviços
docker-compose down
docker-compose up -d

# Aguardar 30 segundos
Start-Sleep -Seconds 30

# Verificar se Evolution API está rodando
docker-compose logs evolution-api --tail 20
```

### 3. Gerar QR Code

```powershell
# Aguardar 10 segundos
Start-Sleep -Seconds 10

# Fazer logout da instância anterior
$headers = @{"apikey" = "3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"}
try {
    Invoke-RestMethod -Uri "http://localhost:8021/instance/logout/leguas-instance" -Method Delete -Headers $headers
} catch {
    Write-Host "Instância ainda não existe ou já está desconectada"
}

# Aguardar
Start-Sleep -Seconds 5

# Conectar e obter QR Code
$response = Invoke-RestMethod -Uri "http://localhost:8021/instance/connect/leguas-instance" -Headers $headers
Write-Host "QR Code disponível! Acesse:"
Write-Host "http://localhost:8021/manager/login"
Write-Host ""
Write-Host "Ou abra o arquivo qrcode_whatsapp.html no navegador"
```

### 4. Acessar Evolution Manager

1. Abra: http://localhost:8021/manager/login
2. Preencha:
   - **Server URL**: `http://localhost:8021`
   - **API Key Global**: `3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW`
3. Clique em **Login**
4. Vá em **Instances** → **leguas-instance**
5. Clique em **"Gerar QR Code"** (botão laranja)
6. Escaneie o QR Code com seu WhatsApp

---

## 📋 Alterações Realizadas

Ajustei a configuração para seguir a documentação oficial:

### ✅ Mudanças no docker-compose.yml:

1. **Versão da imagem**: `atendai/evolution-api:v2.1.1` (versão estável)
2. **Removido Redis**: Usando apenas PostgreSQL + cache local
3. **Simplificado variáveis**: Removidas variáveis desnecessárias
4. **Cache local**: `CACHE_LOCAL_ENABLED=true` (não precisa Redis)

### ✅ Configuração Final:

```yaml
evolution-api:
  image: atendai/evolution-api:v2.1.1
  environment:
    - AUTHENTICATION_API_KEY=3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW
    - SERVER_URL=http://localhost:8021
    - DEL_INSTANCE=false
    - DATABASE_ENABLED=true
    - DATABASE_PROVIDER=postgresql
    - DATABASE_CONNECTION_URI=postgresql://evolution_user:evolution_pass@evolution_db:5432/evolution_db
    - CACHE_REDIS_ENABLED=false
    - CACHE_LOCAL_ENABLED=true
```

---

## 🎯 Após Conectar WhatsApp

### Configurar Django System Config:

1. Acesse: http://localhost:8000/system/
2. Preencha:
   - ☑️ **Ativar WhatsApp**
   - **Evolution API URL**: `http://evolution-api:8080`
   - **Evolution API Key**: `3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW`
   - **Nome da Instância**: `leguas-instance`
3. Clique em **Guardar**

### Testar:

```powershell
# Verificar conexão
$headers = @{"apikey" = "3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"}
$status = Invoke-RestMethod -Uri "http://localhost:8021/instance/connectionState/leguas-instance" -Headers $headers
$status.instance.state  # Deve retornar "open"
```

---

## 📚 Referências

- **Documentação Oficial**: https://doc.evolution-api.com/v2/pt/install/docker
- **Guia Rápido**: [WHATSAPP_GUIA_RAPIDO.md](WHATSAPP_GUIA_RAPIDO.md)
- **Documentação Técnica**: [WHATSAPP_SETUP.md](WHATSAPP_SETUP.md)
- **Cliente Python**: [system_config/whatsapp_helper.py](system_config/whatsapp_helper.py)

---

## ✅ Checklist

- [ ] Docker Desktop reiniciado
- [ ] Containers em execução (`docker-compose ps`)
- [ ] Evolution API respondendo (http://localhost:8021)
- [ ] QR Code gerado
- [ ] WhatsApp conectado (state = "open")
- [ ] Django System Config configurado
- [ ] Mensagem de teste enviada

**Siga os passos acima e o WhatsApp estará funcionando!** 🚀
