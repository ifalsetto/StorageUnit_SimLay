param([switch]$FullScan)

$ErrorActionPreference = 'Stop'
$Root = 'C:\FalseTech'
$SystemDir = Join-Path $Root 'System'
$NodeDir = Join-Path $SystemDir 'FalseTech-Node'
$ConfigPath = Join-Path $SystemDir 'FalseTech-Node.json'
$PythonExe = Join-Path $NodeDir '.venv\Scripts\python.exe'
$AgentScript = Join-Path $NodeDir 'falsetech_node.py'
$Requirements = Join-Path $NodeDir 'requirements.txt'
$RawBase = 'https://raw.githubusercontent.com/ifalsetto/StorageUnit_SimLay/continuity/shared-data-platform/tools/falsetech-node'

if (-not (Test-Path $ConfigPath)) {
    throw 'FalseTech Node is not installed on this PC. Run Install-FalseTechNode.ps1 first.'
}

Write-Host "`n=== FALSETECH NODE REPAIR ===" -ForegroundColor Cyan
Write-Host 'This repair does not delete databases, files, projects, or Continuity history.' -ForegroundColor Green

New-Item -ItemType Directory -Force -Path $NodeDir | Out-Null
Invoke-WebRequest "$RawBase/falsetech_node.py" -OutFile $AgentScript -UseBasicParsing
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
$doctorCommand = "`"$PythonExe`" `"$AgentScript`" --config `"$ConfigPath`" --doctor"
schtasks.exe /Create /TN 'FalseTech Node Daily Health Check' /SC DAILY /ST 07:15 /RL HIGHEST /TR $doctorCommand /F | Out-Null

if ($FullScan) {
    & $PythonExe $AgentScript --config $ConfigPath --once
}

& $PythonExe $AgentScript --config $ConfigPath --doctor
if ($LASTEXITCODE -ne 0) { throw 'Repair completed but the health check still reports an error. Open C:\FalseTech\Continuity\Reports.' }
Write-Host "`nFALSETECH NODE REPAIR COMPLETE" -ForegroundColor Green
