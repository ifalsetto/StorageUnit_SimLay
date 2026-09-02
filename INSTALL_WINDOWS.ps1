$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

& (Join-Path $Root "CONTINUITY_CHECK_WINDOWS.ps1") -RequireCanonical | Out-Null

Write-Host "=== StorageUnit SimLay Install ==="
Write-Host "Installing backend dependencies..."

Set-Location $Backend

if (!(Test-Path ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt

python scripts\validate_config.py
python scripts\init_db.py

Write-Host "Backend ready."

if (Test-Path $Frontend) {
    Write-Host "Installing frontend dependencies..."
    Set-Location $Frontend
    npm ci
    Write-Host "Frontend ready."
}

& (Join-Path $Root "CONTINUITY_CHECK_WINDOWS.ps1") -RequireCanonical | Out-Null
Write-Host "Install complete. Run READY_SIMLAY_WINDOWS.ps1 for full verification and startup."
