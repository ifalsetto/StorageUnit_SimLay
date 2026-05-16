$ErrorActionPreference = "Stop"
Write-Host "Checking backend tests..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:PYTHONPATH='.'
pytest -q
Write-Host "Checking frontend build..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\frontend"
npm install
npm run build
Write-Host "Release verification completed." -ForegroundColor Green
