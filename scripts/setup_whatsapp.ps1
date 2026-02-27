# Script de Configuração Rápida do WhatsApp Evolution API
# Execute este script para configurar tudo automaticamente

Write-Host "🚀 CONFIGURAÇÃO WHATSAPP EVOLUTION API" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

# 1. API Key gerada
$apiKey = "3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"
Write-Host "✅ API Key gerada: $apiKey`n" -ForegroundColor Cyan

# 2. Adicionar ao .env.docker
Write-Host "📝 Adicionando API Key ao .env.docker..." -ForegroundColor Yellow

$envFile = ".env.docker"
$envContent = @"

# WhatsApp Evolution API Configuration
EVOLUTION_API_KEY=$apiKey
EVOLUTION_API_PUBLIC_URL=http://localhost:8021
EVOLUTION_DEFAULT_INSTANCE=leguas-instance
"@

Add-Content -Path $envFile -Value $envContent
Write-Host "✅ API Key adicionada ao .env.docker`n" -ForegroundColor Green

# 3. Reiniciar Evolution API
Write-Host "🔄 Reiniciando Evolution API..." -ForegroundColor Yellow
docker-compose restart evolution-api
Start-Sleep -Seconds 5
Write-Host "✅ Evolution API reiniciada`n" -ForegroundColor Green

# 4. Aguardar serviço estar pronto
Write-Host "⏳ Aguardando serviço ficar pronto (15 segundos)..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# 5. Criar instância
Write-Host "📱 Criando instância WhatsApp..." -ForegroundColor Yellow

$headers = @{
    "apikey" = $apiKey
    "Content-Type" = "application/json"
}

$body = @{
    instanceName = "leguas-instance"
    qrcode = $true
    integration = "WHATSAPP-BAILEYS"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8021/instance/create" -Method Post -Headers $headers -Body $body -ErrorAction Stop
    Write-Host "✅ Instância criada com sucesso!`n" -ForegroundColor Green
} catch {
    if ($_.Exception.Message -like "*already exists*") {
        Write-Host "⚠️  Instância já existe, continuando...`n" -ForegroundColor Yellow
    } else {
        Write-Host "❌ Erro ao criar instância: $($_.Exception.Message)`n" -ForegroundColor Red
    }
}

# 6. Obter QR Code
Write-Host "📲 Obtendo QR Code..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

try {
    $qrResponse = Invoke-RestMethod -Uri "http://localhost:8021/instance/connect/leguas-instance" -Method Get -Headers $headers -ErrorAction Stop
    Write-Host "✅ QR Code obtido!`n" -ForegroundColor Green
    
    # Salvar QR Code em arquivo HTML
    $qrBase64 = $qrResponse.base64
    $htmlContent = @"
<!DOCTYPE html>
<html>
<head>
    <title>WhatsApp QR Code - Léguas Franzinas</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        p {
            color: #666;
            margin-bottom: 30px;
        }
        img {
            border: 4px solid #667eea;
            border-radius: 10px;
            padding: 10px;
            background: white;
        }
        .instructions {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
            text-align: left;
        }
        .instructions ol {
            margin: 10px 0;
        }
        .instructions li {
            margin: 8px 0;
        }
        .timer {
            color: #e74c3c;
            font-weight: bold;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚚 Léguas Franzinas</h1>
        <p>Escaneie o QR Code para conectar o WhatsApp</p>
        <img src="$qrBase64" alt="QR Code WhatsApp" width="300" height="300">
        
        <div class="instructions">
            <strong>📱 Como conectar:</strong>
            <ol>
                <li>Abra o <strong>WhatsApp</strong> no celular</li>
                <li>Vá em <strong>⚙️ Configurações</strong></li>
                <li>Clique em <strong>📱 Aparelhos Conectados</strong></li>
                <li>Clique em <strong>➕ Conectar um aparelho</strong></li>
                <li><strong>Escaneie este QR Code</strong></li>
            </ol>
        </div>
        
        <div class="timer">
            ⏰ QR Code válido por 30 segundos
        </div>
    </div>
    
    <script>
        // Auto-refresh após 25 segundos
        setTimeout(function() {
            location.reload();
        }, 25000);
    </script>
</body>
</html>
"@
    
    $htmlContent | Out-File -FilePath "whatsapp_qrcode.html" -Encoding UTF8
    Write-Host "💾 QR Code salvo em: whatsapp_qrcode.html" -ForegroundColor Cyan
    
    # Abrir QR Code no navegador
    Start-Process "whatsapp_qrcode.html"
    Write-Host "🌐 Abrindo QR Code no navegador...`n" -ForegroundColor Cyan
    
} catch {
    Write-Host "❌ Erro ao obter QR Code: $($_.Exception.Message)`n" -ForegroundColor Red
    Write-Host "Tente manualmente: http://localhost:8021/manager/login`n" -ForegroundColor Yellow
}

# 7. Resumo final
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "✅ CONFIGURAÇÃO CONCLUÍDA!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "📋 INFORMAÇÕES IMPORTANTES:" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "🔑 API Key:" -ForegroundColor Yellow -NoNewline
Write-Host " $apiKey" -ForegroundColor White
Write-Host "🌐 Evolution Manager:" -ForegroundColor Yellow -NoNewline
Write-Host " http://localhost:8021/manager/login" -ForegroundColor White
Write-Host "📱 Nome da Instância:" -ForegroundColor Yellow -NoNewline
Write-Host " leguas-instance" -ForegroundColor White
Write-Host "⚙️  Django System Config:" -ForegroundColor Yellow -NoNewline
Write-Host " http://localhost:8000/system/" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor DarkGray

Write-Host "📱 PRÓXIMOS PASSOS:" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "1. Escaneie o QR Code que abriu no navegador" -ForegroundColor White
Write-Host "2. Aguarde 5-10 segundos após escanear" -ForegroundColor White
Write-Host "3. Configure no Django System Config:" -ForegroundColor White
Write-Host "   • Evolution API URL:" -ForegroundColor DarkGray -NoNewline
Write-Host " http://evolution-api:8080" -ForegroundColor Yellow
Write-Host "   • Evolution API Key:" -ForegroundColor DarkGray -NoNewline
Write-Host " $apiKey" -ForegroundColor Yellow
Write-Host "   • Nome da Instância:" -ForegroundColor DarkGray -NoNewline
Write-Host " leguas-instance" -ForegroundColor Yellow
Write-Host "4. Teste enviando uma mensagem!" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor DarkGray

Write-Host "🔍 VERIFICAR STATUS:" -ForegroundColor Cyan
Write-Host "docker-compose logs -f evolution-api" -ForegroundColor DarkGray
Write-Host ""

Write-Host "📚 DOCUMENTAÇÃO COMPLETA:" -ForegroundColor Cyan
Write-Host "GUIA_WHATSAPP_CONFIGURACAO.md" -ForegroundColor DarkGray
Write-Host ""

Write-Host "Pressione qualquer tecla para continuar..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
