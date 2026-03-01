# Script de limpeza e formatação automática do código
# Sistema Leguas Franzinas - 01/03/2026
# PowerShell Version

Write-Host "`n🧹 Iniciando limpeza e formatação do código...`n" -ForegroundColor Cyan

# 1. Instalar ferramentas (se necessário)
Write-Host "📦 Verificando ferramentas de formatação..." -ForegroundColor Yellow
docker-compose exec -T web pip install -q black autopep8 isort autoflake flake8

Write-Host "`n⚠️  ATENÇÃO: Faça backup ou commit antes de continuar!`n" -ForegroundColor Yellow
$confirmation = Read-Host "Deseja continuar? (s/n)"
if ($confirmation -ne 's' -and $confirmation -ne 'S' -and $confirmation -ne 'y' -and $confirmation -ne 'Y') {
    Write-Host "❌ Cancelado pelo usuário" -ForegroundColor Red
    exit 1
}

# 2. Contar problemas antes
Write-Host "`n📊 Contando problemas atuais..." -ForegroundColor Cyan
$before = (docker-compose exec -T web flake8 . 2>$null | Measure-Object -Line).Lines
if (!$before) { $before = 0 }
Write-Host "   Problemas encontrados: $before" -ForegroundColor Red

# 3. Remover imports não utilizados
Write-Host "`n🗑️  Removendo imports não utilizados..." -ForegroundColor Yellow
docker-compose exec -T web bash -c @"
find . -name '*.py' \
    -not -path '*/migrations/*' \
    -not -path '*/.venv/*' \
    -not -path '*/venv/*' \
    -not -path '*/staticfiles/*' \
    -not -path '*/media/*' \
    -exec autoflake --in-place --remove-all-unused-imports --remove-unused-variables {} \;
"@

Write-Host "   ✓ Imports não utilizados removidos" -ForegroundColor Green

# 4. Organizar imports
Write-Host "`n📑 Organizando imports..." -ForegroundColor Yellow
docker-compose exec -T web isort . `
    --skip migrations `
    --skip .venv `
    --skip venv `
    --skip staticfiles `
    --skip media `
    --profile black `
    --line-length 120

Write-Host "   ✓ Imports organizados" -ForegroundColor Green

# 5. Formatar código com Black
Write-Host "`n🎨 Formatando código com Black..." -ForegroundColor Yellow
docker-compose exec -T web black --line-length 120 `
    --exclude '(migrations|\.venv|venv|staticfiles|media|__pycache__)' .

Write-Host "   ✓ Código formatado" -ForegroundColor Green

# 6. Contar problemas depois
Write-Host "`n📊 Contando problemas após limpeza..." -ForegroundColor Cyan
$after = (docker-compose exec -T web flake8 . 2>$null | Measure-Object -Line).Lines
if (!$after) { $after = 0 }
Write-Host "   Problemas restantes: $after" -ForegroundColor Yellow

# 7. Mostrar resultado
$reduction = $before - $after
$percent = if ($before -gt 0) { [math]::Round(($reduction / $before) * 100, 1) } else { 0 }

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ LIMPEZA CONCLUÍDA!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "   Antes:    $before problemas" -ForegroundColor Red
Write-Host "   Depois:   $after problemas" -ForegroundColor Yellow
Write-Host "   Redução:  $reduction problemas ($percent%)" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Cyan

# 8. Mostrar top problemas restantes
Write-Host "🔍 Verificando problemas restantes..." -ForegroundColor Cyan
docker-compose exec -T web bash -c "flake8 . 2>/dev/null | grep -oE '[A-Z][0-9]+' | sort | uniq -c | sort -rn | head -10"

Write-Host "`n💡 Dicas:" -ForegroundColor Yellow
Write-Host "   - Revise as mudanças com: git diff"
Write-Host "   - Teste a aplicação: docker-compose restart web"
Write-Host "   - Para ver problemas: docker-compose exec web flake8 ."
Write-Host ""
