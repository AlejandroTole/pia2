$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $repoRoot "logs"
$logPath = Join-Path $logDirectory "pia2.log"
$utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

function Write-WatchdogLog {
    param([string]$Message)

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff zzz"
    [System.IO.File]::AppendAllText(
        $logPath,
        "$timestamp | INFO | WATCHDOG | $Message`r`n",
        $utf8WithoutBom
    )
}

$crashes = [System.Collections.Generic.Queue[datetime]]::new()
Set-Location $repoRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    $message = "Falta el entorno virtual: no existe $venvPython. Cree .venv e instale las dependencias antes de usar el watchdog."
    Write-WatchdogLog $message
    Write-Error $message
    exit 1
}

# UTF-8 para el proceso hijo: evita que los emojis rompan la salida en cp1252.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = $utf8WithoutBom
$OutputEncoding = $utf8WithoutBom

Write-WatchdogLog "Supervisor iniciado."

while ($true) {
    & $venvPython main.py
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-WatchdogLog "PIA terminó limpiamente (exit_code=0); no se reinicia."
        break
    }

    $now = Get-Date
    $crashes.Enqueue($now)
    while ($crashes.Count -gt 0 -and ($now - $crashes.Peek()).TotalMinutes -gt 10) {
        [void]$crashes.Dequeue()
    }

    if ($crashes.Count -ge 5) {
        Write-WatchdogLog "Supervisor detenido tras $($crashes.Count) crashes en 10 minutos (último exit_code=$exitCode)."
        break
    }

    Write-WatchdogLog "Crash exit_code=$exitCode; reinicio $($crashes.Count) de 5 en 30 segundos."
    Start-Sleep -Seconds 30
}
