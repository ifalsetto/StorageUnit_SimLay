param(
    [ValidateSet('AJ-Desktop-Main','AJ-Desktop-2','AJ-Laptop')]
    [string]$DeviceName,
    [string]$Email
)

$ErrorActionPreference = 'Stop'
$Root = 'C:\FalseTech'
$SystemDir = Join-Path $Root 'System'
$NodeDir = Join-Path $SystemDir 'FalseTech-Node'
$ContinuityDir = Join-Path $Root 'Continuity'
$ReportsDir = Join-Path $ContinuityDir 'Reports'
$ConfigPath = Join-Path $SystemDir 'FalseTech-Node.json'
$Venv = Join-Path $NodeDir '.venv'
$PythonExe = Join-Path $Venv 'Scripts\python.exe'
$AgentScript = Join-Path $NodeDir 'falsetech_node.py'
$StorageScript = Join-Path $NodeDir 'falsetech_storage_sync.py'
$FetchScript = Join-Path $NodeDir 'falsetech_storage_fetch.py'
$Requirements = Join-Path $NodeDir 'requirements.txt'
$SupabaseUrl = 'https://ppbchnypnyscwkbmoiqv.supabase.co'
$PublishableKey = 'sb_publishable_6xfEmDvcJvxO0fuNNA6E5g_fwCeDLe2'
$RawBase = 'https://raw.githubusercontent.com/ifalsetto/StorageUnit_SimLay/continuity/shared-data-platform/tools/falsetech-node'

function Write-Step([string]$Message) {
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Ensure-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host 'Restarting once with Administrator rights...' -ForegroundColor Yellow
        $args = @('-ExecutionPolicy','Bypass','-File',"`"$PSCommandPath`"")
        if ($DeviceName) { $args += @('-DeviceName', $DeviceName) }
        if ($Email) { $args += @('-Email', $Email) }
        Start-Process powershell.exe -Verb RunAs -ArgumentList $args
        exit
    }
}

function Resolve-DeviceName {
    if ($DeviceName) { return $DeviceName }
    Write-Host 'Choose this computer:' -ForegroundColor Yellow
    Write-Host '  1. AJ-Desktop-Main'
    Write-Host '  2. AJ-Desktop-2'
    Write-Host '  3. AJ-Laptop'
    $choice = Read-Host 'Enter 1, 2, or 3'
    switch ($choice) {
        '1' { return 'AJ-Desktop-Main' }
        '2' { return 'AJ-Desktop-2' }
        '3' { return 'AJ-Laptop' }
        default { throw 'Invalid device choice.' }
    }
}

function Ensure-Python {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { throw 'Python 3.11+ is required and winget was not found.' }
    Write-Step 'Installing Python'
    winget install --id Python.Python.3.11 --exact --accept-source-agreements --accept-package-agreements --silent
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    $candidate = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python" -Filter python.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $candidate) { throw 'Python installation completed but python.exe could not be located.' }
    return $candidate.FullName
}

Ensure-Admin
$DeviceName = Resolve-DeviceName

Write-Step 'Continuity-first discovery'
New-Item -ItemType Directory -Force -Path $Root,$SystemDir,$NodeDir,$ContinuityDir,$ReportsDir,(Join-Path $Root 'Shared') | Out-Null
$existing = Get-ChildItem $Root -Force -ErrorAction SilentlyContinue | Select-Object Name,FullName,LastWriteTime
Write-Host "Existing FalseTech root contains $($existing.Count) top-level entries. Nothing is deleted or blindly moved." -ForegroundColor Green

Write-Step 'Installing FalseTech Node runtime'
$SystemPython = Ensure-Python
Invoke-WebRequest "$RawBase/falsetech_node.py" -OutFile $AgentScript -UseBasicParsing
Invoke-WebRequest "$RawBase/falsetech_storage_sync.py" -OutFile $StorageScript -UseBasicParsing
Invoke-WebRequest "$RawBase/falsetech_storage_fetch.py" -OutFile $FetchScript -UseBasicParsing
Invoke-WebRequest "$RawBase/requirements.txt" -OutFile $Requirements -UseBasicParsing
if (-not (Test-Path $PythonExe)) {
    & $SystemPython -m venv $Venv
}
& $PythonExe -m pip install --upgrade pip | Out-Null
& $PythonExe -m pip install -r $Requirements

if (-not $Email) { $Email = Read-Host 'Email to use for your FalseTech login' }
if ([string]::IsNullOrWhiteSpace($Email)) { throw 'Email is required.' }

$downloadRoot = Join-Path $env:USERPROFILE 'Downloads'
$desktopRoot = Join-Path $env:USERPROFILE 'Desktop'
$documentsRoot = Join-Path $env:USERPROFILE 'Documents'
$managedDownloads = Join-Path $Root 'Downloads'
$managedMedia = Join-Path $Root 'Media'
$managedDocuments = Join-Path $Root 'Documents'
$managedExports = Join-Path $Root 'Exports'
New-Item -ItemType Directory -Force -Path $managedDownloads,$managedMedia,$managedDocuments,$managedExports | Out-Null

$deviceType = if ($DeviceName -eq 'AJ-Laptop') { 'laptop' } else { 'desktop' }
$config = [ordered]@{
    root = $Root
    db_path = (Join-Path $ContinuityDir 'FalseTech-Node-Cache.db')
    supabase_url = $SupabaseUrl
    publishable_key = $PublishableKey
    email = $Email
    device_name = $DeviceName
    device_type = $deviceType
    poll_seconds = 60
    scan_roots = @($Root,$downloadRoot,$desktopRoot,$documentsRoot)
    rename_roots = @($downloadRoot,$managedDownloads,$managedMedia,$managedDocuments,$managedExports)
}
$config | ConvertTo-Json -Depth 5 | Set-Content -Path $ConfigPath -Encoding UTF8

Write-Step 'Authenticating this device'
Write-Host 'Enter the FalseTech/Supabase password once. The refresh token is stored in Windows Credential Manager, not in this config file.' -ForegroundColor Yellow
& $PythonExe $AgentScript --config $ConfigPath --login

Write-Step 'Registering device and running first scan'
& $PythonExe $AgentScript --config $ConfigPath --once

Write-Step 'Synchronizing shared files'
& $PythonExe $StorageScript --config $ConfigPath --limit 250
& $PythonExe $FetchScript --config $ConfigPath --limit 500

Write-Step 'Installing automatic startup'
$taskCommand = "`"$PythonExe`" `"$AgentScript`" --config `"$ConfigPath`" --watch"
schtasks.exe /Create /TN 'FalseTech Node Agent' /SC ONLOGON /RL HIGHEST /TR $taskCommand /F | Out-Null

$storageCommand = "`"$PythonExe`" `"$StorageScript`" --config `"$ConfigPath`" --limit 500"
schtasks.exe /Create /TN 'FalseTech Node Storage Upload' /SC HOURLY /MO 1 /RL HIGHEST /TR $storageCommand /F | Out-Null

$fetchCommand = "`"$PythonExe`" `"$FetchScript`" --config `"$ConfigPath`" --limit 1000"
schtasks.exe /Create /TN 'FalseTech Node Storage Download' /SC ONLOGON /RL HIGHEST /TR $fetchCommand /F | Out-Null
schtasks.exe /Create /TN 'FalseTech Node Storage Download Hourly' /SC HOURLY /MO 1 /RL HIGHEST /TR $fetchCommand /F | Out-Null

$doctorCommand = "`"$PythonExe`" `"$AgentScript`" --config `"$ConfigPath`" --doctor"
schtasks.exe /Create /TN 'FalseTech Node Daily Health Check' /SC DAILY /ST 07:15 /RL HIGHEST /TR $doctorCommand /F | Out-Null

Write-Step 'Final health check'
& $PythonExe $AgentScript --config $ConfigPath --doctor
if ($LASTEXITCODE -ne 0) { throw 'FalseTech Node health check failed. Review the human-readable report under C:\FalseTech\Continuity\Reports.' }

Write-Host "`nFALSETECH NODE INSTALLED" -ForegroundColor Green
Write-Host "Device: $DeviceName"
Write-Host "Config: $ConfigPath"
Write-Host "Local continuity database: $ContinuityDir\FalseTech-Node-Cache.db"
Write-Host 'Automatic metadata/event sync: enabled at Windows logon'
Write-Host 'Private shareable-file upload: every hour, up to 200 MB per file'
Write-Host 'Incoming shared files: C:\FalseTech\Shared, fetched at logon and hourly'
Write-Host 'Daily health check: 7:15 AM'
Write-Host 'Opaque filenames: automatically renamed only in safe managed/download locations; source-code paths are cataloged without destructive renaming.'
