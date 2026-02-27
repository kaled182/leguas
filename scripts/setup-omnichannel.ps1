# 🚀 Script de Inicialização Rápida do Omnichannel
# Leguas Franzinas - Chatwoot + Typebot + WPPConnect

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OMNICHANNEL SETUP - LEGUAS FRANZINAS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar se Docker está rodando
Write-Host "[1/6] Verificando Docker..." -ForegroundColor Yellow
try {
    docker info | Out-Null
    Write-Host "OK Docker esta rodando" -ForegroundColor Green
}
catch {
    Write-Host "ERRO Docker nao esta rodando. Inicie o Docker Desktop." -ForegroundColor Red
    exit 1
}

# Subir containers
Write-Host ""
Write-Host "[2/6] Subindo containers do Omnichannel..." -ForegroundColor Yellow
docker compose up -d chatwoot_db chatwoot_redis chatwoot_web chatwoot_worker typebot_db typebot_builder typebot_viewer

# Aguardar inicialização
Write-Host ""
Write-Host "[3/6] Aguardando inicialização dos serviços..." -ForegroundColor Yellow
Write-Host "Isso pode levar 2-3 minutos na primeira vez..." -ForegroundColor Gray

Start-Sleep -Seconds 30

# Verificar status
Write-Host ""
Write-Host "[4/6] Verificando status dos containers..." -ForegroundColor Yellow
$containers = @(
    "leguas_chatwoot_db",
    "leguas_chatwoot_redis",
    "leguas_chatwoot_web",
    "leguas_chatwoot_worker",
    "leguas_typebot_db",
    "leguas_typebot_builder",
    "leguas_typebot_viewer"
)

foreach ($container in $containers) {
    $status = docker inspect -f '{{.State.Status}}' $container 2>$null
    if ($status -eq "running") {
        Write-Host "  OK $container" -ForegroundColor Green
    }
    else {
        Write-Host "  ERRO $container ($status)" -ForegroundColor Red
    }
}

# Aguardar health checks
Write-Host ""
Write-Host "[5/6] Aguardando health checks..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Exibir URLs de acesso
Write-Host ""
Write-Host "[6/6] URLs de Acesso:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Chatwoot (Central de Atendimento):" -ForegroundColor Cyan
Write-Host "    → http://localhost:3000" -ForegroundColor White
Write-Host "    Credenciais: criar conta na primeira vez" -ForegroundColor Gray
Write-Host ""
Write-Host "  Typebot Builder (Criar Fluxos):" -ForegroundColor Cyan
Write-Host "    → http://localhost:8081" -ForegroundColor White
Write-Host "    Credenciais: criar conta na primeira vez" -ForegroundColor Gray
Write-Host ""
Write-Host "  Typebot Viewer (Executar Bots):" -ForegroundColor Cyan
Write-Host "    → http://localhost:8082" -ForegroundColor White
Write-Host ""

# Próximos passos
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PRÓXIMOS PASSOS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Acesse o Chatwoot e crie sua conta admin" -ForegroundColor Yellow
Write-Host "2. Crie uma Inbox API para WhatsApp" -ForegroundColor Yellow
Write-Host "3. Copie o Inbox ID e API Token" -ForegroundColor Yellow
Write-Host "4. Configure o Bridge (edite docker-compose.yml)" -ForegroundColor Yellow
Write-Host "5. Reinicie o bridge: docker compose restart wppconnect_bridge" -ForegroundColor Yellow
Write-Host "6. Acesse o Typebot e crie o fluxo de cadastro" -ForegroundColor Yellow
Write-Host "7. Configure a integração Chatwoot no Typebot" -ForegroundColor Yellow
Write-Host "8. Publique o bot" -ForegroundColor Yellow
Write-Host "9. Teste enviando 'Oi' no WhatsApp" -ForegroundColor Yellow
Write-Host ""
Write-Host "📚 Documentação completa: docs/OMNICHANNEL_SETUP.md" -ForegroundColor Cyan
Write-Host ""

# Logs em tempo real (opcional)
Write-Host "Deseja acompanhar os logs em tempo real? (S/N): " -ForegroundColor Yellow -NoNewline
$response = Read-Host

if ($response -eq "S" -or $response -eq "s") {
    Write-Host ""
    Write-Host "Iniciando logs (Ctrl+C para sair)..." -ForegroundColor Gray
    Start-Sleep -Seconds 2
    docker compose logs -f chatwoot_web typebot_builder
}
else {
    Write-Host ""
    Write-Host "OK Setup concluido! Bom trabalho!" -ForegroundColor Green
    Write-Host ""
}
