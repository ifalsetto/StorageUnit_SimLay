param(
    [string]$KeyAlias = "simlay_upload",
    [string]$StorePassword = "",
    [string]$KeyPassword = ""
)
$ErrorActionPreference = "Stop"
$mobile = Join-Path $PSScriptRoot "mobile\android"
$keyPath = Join-Path $mobile "release-upload-key.jks"
if (-not $StorePassword) { $StorePassword = Read-Host "Enter new keystore password" }
if (-not $KeyPassword) { $KeyPassword = Read-Host "Enter new key password" }
keytool -genkeypair -v -keystore $keyPath -alias $KeyAlias -keyalg RSA -keysize 4096 -validity 10000 -storepass $StorePassword -keypass $KeyPassword -dname "CN=FalseTech, OU=SimLay, O=FalseTech, L=Springfield, ST=MO, C=US"
@"
storeFile=../release-upload-key.jks
storePassword=$StorePassword
keyAlias=$KeyAlias
keyPassword=$KeyPassword
"@ | Set-Content -Encoding UTF8 (Join-Path $mobile "key.properties")
Write-Host "Created upload key and key.properties. Back up release-upload-key.jks securely." -ForegroundColor Yellow
