# Mypy Progress Checker for Windows PowerShell

Write-Host "=== Mypy Progress Checker ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "📦 Phase 1 Packages:" -ForegroundColor Yellow
$packages = @("config", "core", "agent", "infra")
foreach ($pkg in $packages) {
    $errorCount = (uv run mypy "src/$pkg" --strict 2>&1 | Select-String "error:" | Measure-Object).Count
    Write-Host ("  {0,-10}: {1,3} errors" -f $pkg, $errorCount)
}

# Also check main.py
$mainErrors = (uv run mypy "src/main.py" --strict 2>&1 | Select-String "error:" | Measure-Object).Count
Write-Host ("  {0,-10}: {1,3} errors" -f "main.py", $mainErrors)

Write-Host ""
Write-Host "📊 Total remaining:" -ForegroundColor Yellow
$totalErrors = (uv run mypy src/ --strict 2>&1 | Select-String "error:" | Measure-Object).Count
if ($totalErrors -eq 0) {
    Write-Host "  ✅ No errors! All packages pass strict mode!" -ForegroundColor Green
} else {
    Write-Host "  $totalErrors errors remaining" -ForegroundColor Red
}

Write-Host ""
Write-Host "📈 Progress:" -ForegroundColor Yellow
$initial = 180
$fixed = $initial - $totalErrors
$percentage = [math]::Round(($fixed / $initial) * 100, 1)
Write-Host ("  Fixed: {0}/{1} ({2}%)" -f $fixed, $initial, $percentage)
