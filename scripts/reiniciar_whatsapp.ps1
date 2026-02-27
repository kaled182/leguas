# ====================================================
# SCRIPT DE REINICIALIZAÇÃO - WhatsApp Evolution API
# ====================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  WhatsApp Evolution API - Reiniciar  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Passo 1: Verificar Docker
Write-Host "Verificando Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker version --format '{{.Server.Version}}' 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Docker está rodando (versão $dockerVersion)" -ForegroundColor Green
    } else {
        throw "Docker não está respondendo"
    }
} catch {
    Write-Host "✗ ERRO: Docker Desktop não está rodando!" -ForegroundColor Red
    Write-Host ""
    Write-Host "AÇÃO NECESSÁRIA:" -ForegroundColor Yellow
    Write-Host "1. Clique com botão direito no ícone Docker Desktop (bandeja do Windows)" -ForegroundColor White
    Write-Host "2. Selecione 'Quit Docker Desktop'" -ForegroundColor White
    Write-Host "3. Aguarde fechar completamente" -ForegroundColor White
    Write-Host "4. Abra Docker Desktop novamente pelo menu Iniciar" -ForegroundColor White
    Write-Host "5. Aguarde aparecer 'Docker Desktop is running'" -ForegroundColor White
    Write-Host "6. Execute este script novamente" -ForegroundColor White
    Write-Host ""
    pause
    exit 1
}

Write-Host ""

# Passo 2: Parar containers
Write-Host "Parando containers antigos..." -ForegroundColor Yellow
docker-compose down 2>$null
Write-Host "✓ Containers parados" -ForegroundColor Green
Write-Host ""

# Passo 3: Limpar volumes (opcional)
Write-Host "Deseja limpar os dados antigos do WhatsApp? (S/N)" -ForegroundColor Yellow
$resposta = Read-Host "Digite S para limpar ou N para manter"
if ($resposta -eq "S" -or $resposta -eq "s") {
    Write-Host "Removendo volumes..." -ForegroundColor Yellow
    docker volume rm app.leguasfranzinas.pt_evolution_instances 2>$null
    docker volume rm app.leguasfranzinas.pt_evolution_store 2>$null
    Write-Host "✓ Volumes removidos" -ForegroundColor Green
} else {
    Write-Host "✓ Volumes mantidos" -ForegroundColor Green
}
Write-Host ""

# Passo 4: Iniciar containers
Write-Host "Iniciando containers..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Containers iniciados" -ForegroundColor Green
} else {
    Write-Host "✗ ERRO ao iniciar containers" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Passo 5: Aguardar Evolution API
Write-Host "Aguardando Evolution API inicializar (30 segundos)..." -ForegroundColor Yellow
for ($i=30; $i -gt 0; $i--) {
    Write-Host -NoNewline "`rTempo restante: $i segundos   "
    Start-Sleep -Seconds 1
}
Write-Host ""
Write-Host ""

# Passo 6: Verificar status
Write-Host "Verificando status dos serviços..." -ForegroundColor Yellow
$containers = docker-compose ps --format json | ConvertFrom-Json
foreach ($container in $containers) {
    $status = $container.State
    $name = $container.Service
    if ($status -eq "running") {
        Write-Host "✓ $name : RODANDO" -ForegroundColor Green
    } else {
        Write-Host "✗ $name : $status" -ForegroundColor Red
    }
}
Write-Host ""

# Passo 7: Testar Evolution API
Write-Host "Testando Evolution API..." -ForegroundColor Yellow
try {
    $headers = @{"apikey" = "3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"}
    $response = Invoke-RestMethod -Uri "http://localhost:8021/instance/fetchInstances" -Headers $headers -ErrorAction Stop
    Write-Host "✓ Evolution API está respondendo!" -ForegroundColor Green
} catch {
    Write-Host "✗ Evolution API ainda não está pronta. Aguarde mais 30 segundos." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8021/instance/fetchInstances" -Headers $headers -ErrorAction Stop
        Write-Host "✓ Evolution API está respondendo!" -ForegroundColor Green
    } catch {
        Write-Host "✗ ERRO: Evolution API não está respondendo" -ForegroundColor Red
        Write-Host "Verifique os logs: docker-compose logs evolution-api --tail 50" -ForegroundColor Yellow
    }
}
Write-Host ""

# Passo 8: Verificar instância
Write-Host "Verificando instância do WhatsApp..." -ForegroundColor Yellow
try {
    $headers = @{"apikey" = "3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"}
    $instances = Invoke-RestMethod -Uri "http://localhost:8021/instance/fetchInstances" -Headers $headers
    
    if ($instances.Count -gt 0) {
        Write-Host "✓ Instância encontrada: $($instances[0].instance.instanceName)" -ForegroundColor Green
        
        # Verificar estado
        $state = Invoke-RestMethod -Uri "http://localhost:8021/instance/connectionState/$($instances[0].instance.instanceName)" -Headers $headers
        if ($state.instance.state -eq "open") {
            Write-Host "✓ WhatsApp JÁ ESTÁ CONECTADO!" -ForegroundColor Green
        } else {
            Write-Host "⚠ WhatsApp precisa ser conectado (state: $($state.instance.state))" -ForegroundColor Yellow
        }
    } else {
        Write-Host "⚠ Nenhuma instância encontrada. Será criada automaticamente." -ForegroundColor Yellow
        
        # Criar instância
        Write-Host "Criando instância leguas-instance..." -ForegroundColor Yellow
        $body = @{
            instanceName = "leguas-instance"
            qrcode = $true
            integration = "WHATSAPP-BAILEYS"
        } | ConvertTo-Json
        
        $newInstance = Invoke-RestMethod -Uri "http://localhost:8021/instance/create" -Method Post -Headers @{"apikey"="3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW"; "Content-Type"="application/json"} -Body $body
        Write-Host "✓ Instância criada: $($newInstance.instance.instanceName)" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ ERRO ao verificar instância: $_" -ForegroundColor Red
}
Write-Host ""

# Passo 9: Abrir páginas
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PRÓXIMOS PASSOS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. GERAR QR CODE:" -ForegroundColor Yellow
Write-Host "   Abra: http://localhost:8021/manager/login" -ForegroundColor White
Write-Host "   - Server URL: http://localhost:8021" -ForegroundColor White
Write-Host "   - API Key: 3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW" -ForegroundColor White
Write-Host ""
Write-Host "2. OU use a página HTML:" -ForegroundColor Yellow
Write-Host "   qrcode_whatsapp.html" -ForegroundColor White
Write-Host ""

$abrir = Read-Host "Deseja abrir Evolution Manager agora? (S/N)"
if ($abrir -eq "S" -or $abrir -eq "s") {
    Start-Process "http://localhost:8021/manager/login"
    Write-Host "✓ Evolution Manager aberto no navegador" -ForegroundColor Green
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CREDENCIAIS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Server URL: http://localhost:8021" -ForegroundColor White
Write-Host "API Key: 3zqvcSeK8EuGPwtHd01ViDaZx7okYbXW" -ForegroundColor White
Write-Host "Instance: leguas-instance" -ForegroundColor White
Write-Host ""

Write-Host "Pressione qualquer tecla para sair..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
