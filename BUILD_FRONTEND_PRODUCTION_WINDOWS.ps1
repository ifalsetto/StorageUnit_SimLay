param(
    [Parameter(Mandatory=$true)][string]$ApiBase
)
$ErrorActionPreference = "Stop"
if (-not $ApiBase.StartsWith("https://")) { throw "ApiBase must be HTTPS for production: $ApiBase" }
Set-Location "$PSScriptRoot\frontend"
"VITE_API_BASE=$ApiBase" | Set-Content -Encoding UTF8 ".env.production"
npm install
npm run build
Write-Host "Frontend production build completed in frontend\dist" -ForegroundColor Green
