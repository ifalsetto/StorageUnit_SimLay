param(
    [ValidateSet('AJ-Desktop-Main','AJ-Desktop-2','AJ-Laptop')]
    [string]$DeviceName,
    [string]$Email
)

$ErrorActionPreference = 'Stop'
$Source = 'https://raw.githubusercontent.com/ifalsetto/StorageUnit_SimLay/main/tools/falsetech-node/Install-FalseTechNode.ps1'
$BootstrapDir = Join-Path $env:TEMP 'FalseTech-Node-Setup'
$Installer = Join-Path $BootstrapDir 'Install-FalseTechNode.ps1'

New-Item -ItemType Directory -Force -Path $BootstrapDir | Out-Null
Write-Host "`n=== FALSETECH NODE ONE-TIME SETUP ===" -ForegroundColor Cyan
Write-Host 'Downloading the canonical installer from SimLay main...' -ForegroundColor Green
Invoke-WebRequest $Source -OutFile $Installer -UseBasicParsing

$args = @('-ExecutionPolicy','Bypass','-File',"`"$Installer`"")
if ($DeviceName) { $args += @('-DeviceName', $DeviceName) }
if ($Email) { $args += @('-Email', $Email) }

& powershell.exe @args
exit $LASTEXITCODE
