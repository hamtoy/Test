<#
.SYNOPSIS
    Zip project artifacts for a quick personal backup.

.EXAMPLE
    pwsh scripts/backup.ps1

.EXAMPLE
    pwsh scripts/backup.ps1 -DestinationDir "D:\backups" -SkipEnv
#>

param (
    [string]$DestinationDir = "backups",
    [string[]]$Include = @("data", ".env", "cache_stats.jsonl", "checkpoint.jsonl", "app.log"),
    [switch]$SkipEnv
)

if ($SkipEnv) {
    $Include = $Include | Where-Object { $_ -ne ".env" }
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$destDir = Join-Path -Path (Get-Location) -ChildPath $DestinationDir
if (-not (Test-Path $destDir)) {
    New-Item -ItemType Directory -Path $destDir | Out-Null
}

$existing = @()
foreach ($item in $Include) {
    if (Test-Path $item) {
        $existing += $item
    } else {
        Write-Verbose "Skipping missing path: $item"
    }
}

if (-not $existing.Count) {
    Write-Warning "No files found to back up."
    exit 1
}

$zipPath = Join-Path -Path $destDir -ChildPath ("shining-quasar-{0}.zip" -f $timestamp)
Compress-Archive -Path $existing -DestinationPath $zipPath -Force
Write-Host "Backup created at $zipPath"

if (-not $SkipEnv -and $Include -contains ".env") {
    Write-Host "Note: .env included in archive (contains secrets)." -ForegroundColor Yellow
}
