$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
Set-Location $Backend
& ".\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH='.'
pytest -q
