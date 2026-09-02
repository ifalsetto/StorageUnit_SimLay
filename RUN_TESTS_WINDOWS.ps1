$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
& (Join-Path $Root "CONTINUITY_CHECK_WINDOWS.ps1") -RequireCanonical | Out-Null
Set-Location $Backend
& ".\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH='.'
pytest -q
