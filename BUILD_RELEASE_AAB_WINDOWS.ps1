param(
    [Parameter(Mandatory=$true)][string]$AppUrl,
    [string]$VersionName = "1.0.0",
    [int]$VersionCode = 1
)
$ErrorActionPreference = "Stop"
if (-not $AppUrl.StartsWith("https://")) { throw "AppUrl must be HTTPS for Google Play release: $AppUrl" }
$androidRoot = Join-Path $PSScriptRoot "mobile\android"
$keyProps = Join-Path $androidRoot "key.properties"
if (-not (Test-Path $keyProps)) {
    throw "Missing mobile\android\key.properties. Run CREATE_ANDROID_UPLOAD_KEY_WINDOWS.ps1 first."
}
Set-Location $androidRoot
if (Test-Path ".\gradlew.bat") {
    .\gradlew.bat clean bundleRelease -PSIMLAY_APP_URL=$AppUrl -PSIMLAY_VERSION_NAME=$VersionName -PSIMLAY_VERSION_CODE=$VersionCode
} else {
    gradle clean bundleRelease -PSIMLAY_APP_URL=$AppUrl -PSIMLAY_VERSION_NAME=$VersionName -PSIMLAY_VERSION_CODE=$VersionCode
}
$aab = Join-Path $androidRoot "app\build\outputs\bundle\release\app-release.aab"
if (-not (Test-Path $aab)) { throw "AAB was not created at $aab" }
Write-Host "Google Play AAB ready: $aab" -ForegroundColor Green
