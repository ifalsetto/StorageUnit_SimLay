param(
    [switch]$NoStart,
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Backups = if ($env:FALSETECH_ROOT) { Join-Path $env:FALSETECH_ROOT "Backups" } else { "C:\FalseTech\Backups" }

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Port-InUse([int]$Port) {
    try {
        return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
    } catch {
        return $false
    }
}

Write-Host "`n=== StorageUnit SimLay - Ready Workflow ===" -ForegroundColor Cyan
Require-Command git
Require-Command python
Require-Command node
Require-Command npm

Write-Host "`n[1/6] Continuity preflight" -ForegroundColor Cyan
& (Join-Path $Root "CONTINUITY_CHECK_WINDOWS.ps1") -RequireCanonical | Out-Null

if (-not $SkipSync) {
    Write-Host "`n[2/6] Safe canonical sync" -ForegroundColor Cyan
    Set-Location $Root
    & git fetch origin
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }

    $branch = (& git branch --show-current).Trim()
    if ($branch -ne "main") {
        Write-Warning "Current branch is '$branch'. Auto-sync is limited to main; leaving this branch unchanged."
    } else {
        $behind = [int]((& git rev-list --count HEAD..origin/main).Trim())
        if ($behind -gt 0) {
            $dirty = -not [string]::IsNullOrWhiteSpace((& git status --porcelain | Out-String))
            $stashCreated = $false
            $backupDir = $null
            if ($dirty) {
                $stamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
                $backupDir = Join-Path $Backups "SimLay-LocalChanges-$stamp"
                New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
                (& git status --porcelain) | Set-Content (Join-Path $backupDir "status.txt") -Encoding UTF8
                (& git diff) | Set-Content (Join-Path $backupDir "working-tree.patch") -Encoding UTF8
                (& git diff --cached) | Set-Content (Join-Path $backupDir "staged.patch") -Encoding UTF8
                (& git ls-files --others --exclude-standard) | Set-Content (Join-Path $backupDir "untracked-files.txt") -Encoding UTF8
                & git stash push -u -m "SimLay READY auto-preserve $stamp"
                if ($LASTEXITCODE -ne 0) { throw "Could not preserve local changes before sync." }
                $stashCreated = $true
                Write-Host "Local changes preserved: $backupDir"
            }

            & git pull --ff-only origin main
            if ($LASTEXITCODE -ne 0) { throw "Fast-forward sync failed. Local changes remain preserved." }

            if ($stashCreated) {
                & git stash pop
                if ($LASTEXITCODE -ne 0) {
                    throw "Canonical code synced, but local changes conflicted during restore. Use the backup at $backupDir."
                }
            }
        } else {
            Write-Host "Already current with origin/main."
        }
    }
} else {
    Write-Host "`n[2/6] Sync skipped by request" -ForegroundColor Yellow
}

Write-Host "`n[3/6] Backend environment" -ForegroundColor Cyan
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Set-Location $Backend
    python -m venv .venv
}
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $Backend "requirements.txt") pytest

Write-Host "`n[4/6] Frontend dependencies" -ForegroundColor Cyan
Set-Location $Frontend
npm ci
if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }

Write-Host "`n[5/6] Verification" -ForegroundColor Cyan
Set-Location $Backend
& $VenvPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }

Set-Location $Frontend
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed" }

# Re-run the full continuity gate after dependency/build activity and before runtime.
Set-Location $Root
& (Join-Path $Root "CONTINUITY_CHECK_WINDOWS.ps1") -RequireCanonical | Out-Null

Write-Host "`n[6/6] Runtime" -ForegroundColor Cyan
if ($NoStart) {
    Write-Host "PASS - SimLay is synced, installed, tested, and production-build clean." -ForegroundColor Green
    exit 0
}

$env:SIMLAY_CONTINUITY_STRICT = "1"
if (-not (Port-InUse 8000)) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:SIMLAY_CONTINUITY_STRICT='1'; cd '$Backend'; .\.venv\Scripts\Activate.ps1; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
} else {
    Write-Warning "Port 8000 is already listening; backend start skipped."
}

Start-Sleep -Seconds 2
if (-not (Port-InUse 5173)) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Frontend'; npm run dev -- --host 127.0.0.1"
} else {
    Write-Warning "Port 5173 is already listening; frontend start skipped."
}

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"
Write-Host "`nREADY" -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "Backend:  http://127.0.0.1:8000/docs"
Write-Host "Market:   http://127.0.0.1:8000/api/market/policy"
