param(
    [switch]$RequireCanonical,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$CanonicalRepo = "ifalsetto/StorageUnit_SimLay"
$FalseTechRoot = if ($env:FALSETECH_ROOT) { $env:FALSETECH_ROOT } else { "C:\FalseTech" }
$ReportDir = Join-Path $Root "backend\data\exports"
$ReportPath = Join-Path $ReportDir "continuity_preflight.json"

function Normalize-Remote([string]$Remote) {
    if (-not $Remote) { return "" }
    return ($Remote.Trim().ToLower() -replace '\.git$','')
}

function Is-CanonicalRemote([string]$Remote) {
    $normalized = Normalize-Remote $Remote
    return $normalized -match 'github\.com[/:]ifalsetto/storageunit_simlay$'
}

function Get-Origin([string]$RepoPath) {
    try {
        $value = (& git -C $RepoPath remote get-url origin 2>$null)
        if ($LASTEXITCODE -eq 0) { return ($value | Select-Object -First 1).Trim() }
    } catch {}
    return $null
}

function Get-RepoRole([string]$RepoPath) {
    $roleFile = Join-Path $RepoPath "FALSETECH_REPOSITORY_ROLE.md"
    if (-not (Test-Path $roleFile)) { return "unknown" }
    $text = (Get-Content $roleFile -Raw -ErrorAction SilentlyContinue).ToLower()
    if ($text -match 'not the simlay core' -and $text -match 'wix') { return "wix_storefront_adapter" }
    if ($text -match 'canonical simlay core') { return "declared_canonical" }
    return "documented_other"
}

$errors = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
$repos = New-Object System.Collections.Generic.List[object]
$references = New-Object System.Collections.Generic.List[string]

$agentsPath = Join-Path $Root "AGENTS.md"
if (-not (Test-Path $agentsPath)) {
    $errors.Add("AGENTS.md canonical lineage marker is missing.")
} else {
    $agents = Get-Content $agentsPath -Raw
    if ($agents -notmatch [regex]::Escape($CanonicalRepo)) {
        $errors.Add("AGENTS.md does not declare $CanonicalRepo as canonical.")
    }
}

$currentRemote = Get-Origin $Root
if ($currentRemote -and -not (Is-CanonicalRemote $currentRemote)) {
    $errors.Add("Current checkout origin is not canonical: $currentRemote")
} elseif (-not $currentRemote) {
    $warnings.Add("Current Git origin could not be read.")
}

$projectsRoot = Join-Path $FalseTechRoot "Projects"
if (Test-Path $projectsRoot) {
    $gitDirs = Get-ChildItem $projectsRoot -Directory -Recurse -Force -Filter ".git" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\(node_modules|\.venv|venv|dist|build|__pycache__)\\' }

    foreach ($gitDir in $gitDirs) {
        $repoPath = $gitDir.Parent.FullName
        $remote = Get-Origin $repoPath
        $identity = ("$repoPath $remote").ToLower()
        if ($identity -notmatch 'simlay|storageunit|storage-unit') { continue }
        $role = Get-RepoRole $repoPath
        $isCanonical = Is-CanonicalRemote $remote
        $isCurrent = ([IO.Path]::GetFullPath($repoPath).TrimEnd('\') -eq [IO.Path]::GetFullPath($Root).TrimEnd('\'))
        $record = [ordered]@{
            path = $repoPath
            remote = $remote
            role = $role
            is_current = $isCurrent
            is_canonical_remote = $isCanonical
        }
        $repos.Add([pscustomobject]$record)

        if (-not $isCurrent -and -not $isCanonical -and $role -ne "wix_storefront_adapter") {
            $errors.Add("Potential parallel SimLay core repository: $repoPath")
        }
        if (-not $isCurrent -and $isCanonical) {
            $warnings.Add("Additional canonical checkout found: $repoPath")
        }
    }
}

foreach ($area in @("Backups", "DATASETS", "SKILLS")) {
    $areaPath = Join-Path $FalseTechRoot $area
    if (-not (Test-Path $areaPath)) { continue }
    Get-ChildItem $areaPath -Directory -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'SimLay|StorageUnit' } |
        ForEach-Object { $references.Add($_.FullName) }
}

New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$report = [ordered]@{
    checked_at = (Get-Date).ToUniversalTime().ToString("o")
    canonical_repository = $CanonicalRepo
    current_root = $Root
    current_remote = $currentRemote
    false_tech_root = $FalseTechRoot
    repositories = @($repos)
    reference_copies = @($references)
    errors = @($errors)
    warnings = @($warnings)
    passed = ($errors.Count -eq 0)
}
$report | ConvertTo-Json -Depth 8 | Set-Content $ReportPath -Encoding UTF8

if (-not $Quiet) {
    Write-Host "`n=== SimLay Continuity Gate ===" -ForegroundColor Cyan
    Write-Host "Canonical: $CanonicalRepo"
    Write-Host "Current:   $Root"
    if ($currentRemote) { Write-Host "Origin:    $currentRemote" }
    Write-Host "Active SimLay Git repos: $($repos.Count)"
    Write-Host "Reference copies found:  $($references.Count)"
    foreach ($warning in $warnings) { Write-Warning $warning }
    if ($errors.Count -eq 0) {
        Write-Host "PASS - continuity lineage is safe to continue." -ForegroundColor Green
    } else {
        foreach ($problem in $errors) { Write-Host "ERROR - $problem" -ForegroundColor Red }
    }
    Write-Host "Report: $ReportPath"
}

if ($RequireCanonical -and $errors.Count -gt 0) {
    throw "SimLay continuity gate failed. No code execution should continue until the lineage conflict is resolved."
}

return [pscustomobject]$report
