param([switch]$FullScan)

$ErrorActionPreference = 'Stop'
$Root = 'C:\FalseTech'
$SystemDir = Join-Path $Root 'System'
$NodeDir = Join-Path $SystemDir 'FalseTech-Node'
$ConfigPath = Join-Path $SystemDir 'FalseTech-Node.json'
$PythonExe = Join-Path $NodeDir '.venv\Scripts\python.exe'
$AgentScript = Join-Path $NodeDir 'falsetech_node.py'
$StorageScript = Join-Path $NodeDir 'falsetech_storage_sync.py'
$FetchScript = Join-Path $NodeDir 'falsetech_storage_fetch.py'
$Requirements = Join-Path $NodeDir 'requirements.txt'
$RawBase = 'https://raw.githubusercontent.com/ifalsetto/StorageUnit_SimLay/main/tools/falsetech-node'

if (-not (Test-Path $ConfigPath)) {
    throw 'FalseTech Node is not installed on this PC. Run Install-FalseTechNode.ps1 first.'
}

Write-Host "`n=== FALSETECH NODE REPAIR ===" -ForegroundColor Cyan
Write-Host 'This repair does not delete databases, files, projects, or Continuity history.' -ForegroundColor Green

New-Item -ItemType Directory -Force -Path $NodeDir,(Join-Path $Root 'Shared') | Out-Null
Invoke-WebRequest "$RawBase/falsetech_node.py" -OutFile $AgentScript -UseBasicParsing
Invoke-WebRequest "$RawBase/falsetech_storage_sync.py" -OutFile $StorageScript -UseBasicParsing
Invoke-WebRequest "$RawBase/falsetech_storage_fetch.py" -OutFile $FetchScript -UseBasicParsing
Invoke-WebRequest "$RawBase/requirements.txt" -OutFile $Requirements -UseBasicParsing

if (-not (Test-Path $PythonExe)) {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $python) { throw 'Python is missing. Re-run Install-FalseTechNode.ps1 to repair the runtime.' }
    & $python.Source -m venv (Join-Path $NodeDir '.venv')
}

& $PythonExe -m pip install --upgrade pip | Out-Null
& $PythonExe -m pip install -r $Requirements

$taskCommand = "`"$PythonExe`" `"$AgentScript`" --config `"$ConfigPath`" --watch"
schtasks.exe /Create /TN 'FalseTech Node Agent' /SC ONLOGON /RL HIGHEST /TR $taskCommand /F | Out-Null
$storageCommand = "`"$PythonExe`" `"$StorageScript`" --config `"$ConfigPath`" --limit 500"
schtasks.exe /Create /TN 'FalseTech Node Storage Upload' /SC HOURLY /MO 1 /RL HIGHEST /TR $storageCommand /F | Out-Null
$fetchCommand = "`"$PythonExe`" `"$FetchScript`" --config `"$ConfigPath`" --limit 1000"
schtasks.exe /Create /TN 'FalseTech Node Storage Download' /SC ONLOGON /RL HIGHEST /TR $fetchCommand /F | Out-Null
schtasks.exe /Create /TN 'FalseTech Node Storage Download Hourly' /SC HOURLY /MO 1 /RL HIGHEST /TR $fetchCommand /F | Out-Null
$doctorCommand = "`"$PythonExe`" `"$AgentScript`" --config `"$ConfigPath`" --doctor"
schtasks.exe /Create /TN 'FalseTech Node Daily Health Check' /SC DAILY /ST 07:15 /RL HIGHEST /TR $doctorCommand /F | Out-Null

if ($FullScan) {
    & $PythonExe $AgentScript --config $ConfigPath --once
    & $PythonExe $StorageScript --config $ConfigPath --limit 1000
}
& $PythonExe $FetchScript --config $ConfigPath --limit 1000
& $PythonExe $AgentScript --config $ConfigPath --doctor
if ($LASTEXITCODE -ne 0) { throw 'Repair completed but the health check still reports an error. Open C:\FalseTech\Continuity\Reports.' }
Write-Host "`nFALSETECH NODE REPAIR COMPLETE" -ForegroundColor Green
