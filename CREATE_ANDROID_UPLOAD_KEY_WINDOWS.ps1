param(
    [string]$KeyAlias = "simlay_upload",
    [string]$StorePassword = "",
    [string]$KeyPassword = "",
    [string]$DistinguishedName = "CN=StorageUnit SimLay, OU=App Release, O=StorageUnit SimLay, L=City, ST=State, C=US"
)
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "CONTINUITY_CHECK_WINDOWS.ps1") -RequireCanonical | Out-Null
$mobile = Join-Path $PSScriptRoot "mobile\android"
$keyPath = Join-Path $mobile "release-upload-key.jks"
if (-not $StorePassword) { $StorePassword = Read-Host "Enter new keystore password" }
if (-not $KeyPassword) { $KeyPassword = Read-Host "Enter new key password" }
keytool -genkeypair -v -keystore $keyPath -alias $KeyAlias -keyalg RSA -keysize 4096 -validity 10000 -storepass $StorePassword -keypass $KeyPassword -dname $DistinguishedName
@"
storeFile=../release-upload-key.jks
storePassword=$StorePassword
keyAlias=$KeyAlias
keyPassword=$KeyPassword
"@ | Set-Content -Encoding UTF8 (Join-Path $mobile "key.properties")
Write-Host "Created upload key and key.properties. Back up release-upload-key.jks securely and do not commit it." -ForegroundColor Yellow
