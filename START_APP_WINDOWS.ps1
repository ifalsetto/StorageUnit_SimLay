$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

& (Join-Path $Root "CONTINUITY_CHECK_WINDOWS.ps1") -RequireCanonical | Out-Null
$env:SIMLAY_CONTINUITY_STRICT = "1"

Write-Host "Starting StorageUnit SimLay..."

Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:SIMLAY_CONTINUITY_STRICT='1'; cd '$Backend'; .\.venv\Scripts\Activate.ps1; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Frontend'; npm run dev -- --host 127.0.0.1"

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"
Write-Host "Backend:  http://127.0.0.1:8000/docs"
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "Market:   http://127.0.0.1:8000/api/market/policy"
