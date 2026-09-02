param(
    [Parameter(Mandatory=$true)][string]$ApiBase
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "CONTINUITY_CHECK_WINDOWS.ps1") -RequireCanonical | Out-Null
if (-not $ApiBase.StartsWith("https://")) { throw "ApiBase must be HTTPS for production: $ApiBase" }
Set-Location "$Root\frontend"
"VITE_API_BASE=$ApiBase" | Set-Content -Encoding UTF8 ".env.production"
npm ci
npm run build
Write-Host "Frontend production build completed in frontend\dist" -ForegroundColor Green
