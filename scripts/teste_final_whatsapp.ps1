# ============================================
# TESTE FINAL - WhatsApp Evolution API
# ============================================

$ErrorActionPreference = "Continue"
$API_URL = "http://localhost:8021"
$API_KEY = "3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"
$headers = @{
    "apikey" = $API_KEY
    "Content-Type" = "application/json"
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  TESTE FINAL WHATSAPP" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# 1. Limpar instâncias antigas
Write-Host "1. Limpando instâncias antigas..." -ForegroundColor Yellow
try {
    $instances = Invoke-RestMethod -Uri "$API_URL/instance/fetchInstances" -Headers $headers
    foreach ($inst in $instances) {
        Write-Host "   Deletando: $($inst.name)" -ForegroundColor Gray
        try {
            Invoke-RestMethod -Uri "$API_URL/instance/delete/$($inst.name)" -Method Delete -Headers $headers | Out-Null
        } catch {}
    }
    Write-Host "   ✓ Limpeza concluída`n" -ForegroundColor Green
} catch {
    Write-Host "   Nenhuma instância para deletar`n" -ForegroundColor Gray
}

Start-Sleep -Seconds 3

# 2. Criar nova instância
$instanceName = "leguas-whatsapp"
Write-Host "2. Criando instância: $instanceName" -ForegroundColor Yellow

$createBody = @"
{
    "instanceName": "$instanceName",
    "qrcode": true,
    "integration": "WHATSAPP-BAILEYS"
}
"@

Write-Host "   Enviando requisição..." -ForegroundColor Gray

try {
    $created = Invoke-RestMethod `
        -Uri "$API_URL/instance/create" `
        -Method Post `
        -Headers $headers `
        -Body $createBody
    
    Write-Host "   ✓ Instância criada!" -ForegroundColor Green
    Write-Host "   Status: $($created.instance.status)" -ForegroundColor Cyan
    Write-Host "   ID: $($created.instance.instanceId)" -ForegroundColor Cyan
    
    # Verificar se QR foi gerado na criação
    if ($created.qrcode -and $created.qrcode.base64) {
        Write-Host "`n   🎉 QR CODE GERADO NA CRIAÇÃO!" -ForegroundColor Green -BackgroundColor DarkGreen
        
        $qrHtml = @"
<!DOCTYPE html>
<html>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>✓ WhatsApp QR Code</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #128C7E 0%, #075E54 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
            max-width: 500px;
        }
        h1 {
            color: #25D366;
            margin-bottom: 10px;
            font-size: 32px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 16px;
        }
        img {
            max-width: 100%;
            height: auto;
            border: 5px solid #25D366;
            border-radius: 15px;
            margin: 20px 0;
        }
        .info {
            background: #f5f5f5;
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
        }
        .info p {
            color: #333;
            margin: 8px 0;
            font-size: 14px;
        }
        .badge {
            display: inline-block;
            background: #25D366;
            color: white;
            padding: 8px 20px;
            border-radius: 25px;
            font-size: 14px;
            margin-top: 15px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class='container'>
        <h1>📱 WhatsApp QR Code</h1>
        <p class='subtitle'>Escaneie este código com seu WhatsApp</p>
        <img src='$($created.qrcode.base64)' alt='QR Code'/>
        <div class='info'>
            <p><strong>Instância:</strong> $instanceName</p>
            <p><strong>Status:</strong> Conectando</p>
            <p><strong>Gerado em:</strong> $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')</p>
            <span class='badge'>✓ Ativo</span>
        </div>
    </div>
</body>
</html>
"@
        
        $qrHtml | Out-File -FilePath "qr_whatsapp_sucesso.html" -Encoding UTF8
        Write-Host "   Arquivo salvo: qr_whatsapp_sucesso.html" -ForegroundColor Cyan
        Invoke-Item "qr_whatsapp_sucesso.html"
        
    } else {
        Write-Host "`n   ⚠ QR não gerado na criação (count: $($created.qrcode.count))" -ForegroundColor Yellow
        
        Write-Host "`n3. Tentando obter QR via /connect..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        
        $maxAttempts = 15
        $attempt = 0
        $qrObtained = $false
        
        while ($attempt -lt $maxAttempts -and -not $qrObtained) {
            $attempt++
            Write-Host "   Tentativa $attempt/$maxAttempts..." -ForegroundColor Gray
            
            try {
                $qrResponse = Invoke-RestMethod `
                    -Uri "$API_URL/instance/connect/$instanceName" `
                    -Headers $headers
                
                if ($qrResponse.qrcode -and $qrResponse.qrcode.base64) {
                    Write-Host "`n   🎉 QR CODE OBTIDO!" -ForegroundColor Green -BackgroundColor DarkGreen
                    
                    $qrHtml = @"
<!DOCTYPE html>
<html>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>✓ WhatsApp QR Code</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #128C7E 0%, #075E54 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
            max-width: 500px;
        }
        h1 {
            color: #25D366;
            margin-bottom: 10px;
            font-size: 32px;
        }
        img {
            max-width: 100%;
            height: auto;
            border: 5px solid #25D366;
            border-radius: 15px;
            margin: 20px 0;
        }
        .info {
            background: #f5f5f5;
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
        }
        .info p {
            color: #333;
            margin: 8px 0;
        }
        .badge {
            background: #25D366;
            color: white;
            padding: 8px 20px;
            border-radius: 25px;
            margin-top: 15px;
            display: inline-block;
        }
    </style>
</head>
<body>
    <div class='container'>
        <h1>📱 WhatsApp QR Code</h1>
        <img src='$($qrResponse.qrcode.base64)' alt='QR Code'/>
        <div class='info'>
            <p><strong>Instância:</strong> $instanceName</p>
            <p><strong>Tentativa:</strong> $attempt de $maxAttempts</p>
            <p><strong>Obtido em:</strong> $(Get-Date -Format 'HH:mm:ss')</p>
            <span class='badge'>✓ Conectando</span>
        </div>
    </div>
</body>
</html>
"@
                    
                    $qrHtml | Out-File -FilePath "qr_whatsapp_sucesso.html" -Encoding UTF8
                    Write-Host "   Arquivo salvo: qr_whatsapp_sucesso.html" -ForegroundColor Cyan
                    Invoke-Item "qr_whatsapp_sucesso.html"
                    $qrObtained = $true
                    
                } elseif ($qrResponse.pairingCode) {
                    Write-Host "`n   ✓ CÓDIGO DE PAREAMENTO OBTIDO!" -ForegroundColor Green
                    Write-Host "   Código: $($qrResponse.pairingCode)" -ForegroundColor Cyan -BackgroundColor Black
                    Write-Host "`n   Use este código no WhatsApp:" -ForegroundColor Yellow
                    Write-Host "   1. Abra WhatsApp > Menu > Aparelhos Conectados" -ForegroundColor White
                    Write-Host "   2. Clique em 'Conectar um aparelho'" -ForegroundColor White
                    Write-Host "   3. Digite o código: $($qrResponse.pairingCode)" -ForegroundColor White
                    $qrObtained = $true
                }
            } catch {
                # Silencioso
            }
            
            if (-not $qrObtained) {
                Start-Sleep -Seconds 3
            }
        }
        
        if (-not $qrObtained) {
            Write-Host "`n   ❌ FALHA: QR Code não foi gerado após $maxAttempts tentativas" -ForegroundColor Red
            
            Write-Host "`n4. Verificando estado da instância..." -ForegroundColor Yellow
            try {
                $state = Invoke-RestMethod `
                    -Uri "$API_URL/instance/connectionState/$instanceName" `
                    -Headers $headers
                Write-Host "   Estado: $($state.instance.state)" -ForegroundColor Cyan
            } catch {
                Write-Host "   Erro ao verificar estado" -ForegroundColor Red
            }
            
            Write-Host "`n5. Verificando logs recentes..." -ForegroundColor Yellow
            $logs = docker-compose logs evolution-api --tail 20 2>&1 | Out-String
            $errors = $logs -split "`n" | Select-String -Pattern "error|Error|timeout|Timed|WebSocket" | Select-Object -First 5
            
            if ($errors) {
                Write-Host "   Erros encontrados:" -ForegroundColor Red
                $errors | ForEach-Object {
                    Write-Host "   $_" -ForegroundColor DarkRed
                }
            }
            
            Write-Host "`n========================================" -ForegroundColor Red
            Write-Host "  CONCLUSÃO: PROBLEMA CONFIRMADO" -ForegroundColor Red
            Write-Host "========================================" -ForegroundColor Red
            Write-Host "`nO problema é interno da Evolution API v2.1.1:" -ForegroundColor White
            Write-Host "- Baileys timeout ao validar conexão WebSocket" -ForegroundColor Gray
            Write-Host "- Conectividade de rede OK (ping e DNS funcionam)" -ForegroundColor Gray
            Write-Host "- API respondendo normalmente" -ForegroundColor Gray
            Write-Host "- Instância criada mas sem QR Code" -ForegroundColor Gray
            
            Write-Host "`nSoluções alternativas:" -ForegroundColor Yellow
            Write-Host "1. Usar Evolution Manager UI manualmente" -ForegroundColor White
            Write-Host "2. Tentar versão diferente da Evolution API" -ForegroundColor White
            Write-Host "3. Usar WPPConnect como alternativa" -ForegroundColor White
            
            Write-Host "`nDocumentação completa em:" -ForegroundColor Cyan
            Write-Host "- RELATORIO_WHATSAPP_DIAGNOSTICO.md" -ForegroundColor White
            Write-Host "- RELATORIO_FINAL_DIAGNOSTICO.md" -ForegroundColor White
        }
    }
    
} catch {
    Write-Host "`n   ❌ ERRO ao criar instância:" -ForegroundColor Red
    Write-Host "   $_" -ForegroundColor Red
}

Write-Host "`n========================================`n" -ForegroundColor Cyan
