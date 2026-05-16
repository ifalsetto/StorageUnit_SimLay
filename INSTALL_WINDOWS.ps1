$ErrorActionPreference = "Stop"

Write-Host "=== StorageUnit SimLay Install ==="
Write-Host "Installing backend dependencies..."

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

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
    npm install
    Write-Host "Frontend ready."
}

Write-Host "Install complete. Run START_APP_WINDOWS.ps1 next."
