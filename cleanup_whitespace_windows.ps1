# Script PowerShell para limpar trailing whitespace
# Roda DIRETAMENTE nos arquivos do Windows

$baseDir = "D:\app.leguasfranzinas.pt\app.leguasfranzinas.pt"

$dirsToProcess = @(
    "accounting",
    "analytics",
    "converter",
    "core",
    "customauth",
    "drivers_app",
    "fleet_management",
    "management",
    "my_project",
    "orders_manager",
    "ordersmanager_paack",
    "paack_dashboard",
    "pricing",
    "route_allocation",
    "send_paack_reports",
    "settlements",
    "system_config"
)

$totalFiles = 0
$totalCleaned = 0

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "LIMPEZA DE TRAILING WHITESPACE - WINDOWS" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

foreach ($dir in $dirsToProcess) {
    $dirPath = Join-Path $baseDir $dir
    
    if (-not (Test-Path $dirPath)) {
        continue
    }
    
    Write-Host "$dir/" -ForegroundColor Yellow
    
    $pyFiles = Get-ChildItem -Path $dirPath -Filter "*.py" -Recurse | Where-Object {
        $_.FullName -notmatch "\\migrations\\" -and
        $_.FullName -notmatch "\\__pycache__\\"
    }
    
    foreach ($file in $pyFiles) {
        $totalFiles++
        
        try {
            # Ler conteúdo
            $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
            $originalContent = $content
            
            # Remover trailing whitespace de cada linha
            $lines = $content -split "`r?`n"
            $cleanedLines = @()
            
            foreach ($line in $lines) {
                # Remove espaços e tabs do final
                $cleanedLine = $line -replace '[ \t]+$', ''
                $cleanedLines += $cleanedLine
            }
            
            # Reconstruir com line breaks Windows
            $newContent = $cleanedLines -join "`r`n"
            
            # Garantir newline no final
            if ($newContent -and -not $newContent.EndsWith("`r`n")) {
                $newContent += "`r`n"
            }
            
            # Salvar se mudou
            if ($newContent -ne $originalContent) {
                [System.IO.File]::WriteAllText($file.FullName, $newContent, [System.Text.Encoding]::UTF8)
                $totalCleaned++
                
                $relativePath = $file.FullName.Replace($baseDir + "\", "")
                Write-Host "   OK: $relativePath" -ForegroundColor Green
            }
        }
        catch {
            Write-Host "   ERRO em $($file.Name): $_" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "CONCLUIDO!" -ForegroundColor Green
Write-Host "   Arquivos processados: $totalFiles" -ForegroundColor White
Write-Host "   Arquivos limpos: $totalCleaned" -ForegroundColor White
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

if ($totalCleaned -gt 0) {
    Write-Host "Recarregue o VS Code: Ctrl + Shift + P -> Reload Window" -ForegroundColor Yellow
} else {
    Write-Host "Nenhum arquivo precisou ser modificado (ja estao limpos)" -ForegroundColor Cyan
}
