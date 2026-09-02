$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "CONTINUITY_CHECK_WINDOWS.ps1") -RequireCanonical | Out-Null
Write-Host "Checking backend tests..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:PYTHONPATH='.'
python scripts\validate_config.py
pytest -q
Write-Host "Checking frontend build..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\frontend"
npm ci
npm run build
Set-Location $PSScriptRoot
& (Join-Path $PSScriptRoot "CONTINUITY_CHECK_WINDOWS.ps1") -RequireCanonical | Out-Null
Write-Host "Release verification completed." -ForegroundColor Green
