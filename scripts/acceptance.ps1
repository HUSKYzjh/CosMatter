[CmdletBinding()]
param(
    [string]$Python = $env:COSMATTER_PYTHON,
    [switch]$SkipDshProfileSmoke,
    [switch]$SkipPluginPackages,
    [string]$ReportPath,
    [switch]$OverwriteReport
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
# Native tools sometimes use stderr for non-failing diagnostics (notably Git's
# CRLF conversion notice). Their exit code remains the acceptance authority.
if ($PSVersionTable.PSVersion.Major -ge 7) { $PSNativeCommandUseErrorActionPreference = $false }

$projectRoot = Split-Path -Parent $PSScriptRoot
$startedAt = (Get-Date).ToUniversalTime().ToString("o")
$stepRecords = [System.Collections.Generic.List[object]]::new()
$resolvedReportPath = $null
if (-not [string]::IsNullOrWhiteSpace($ReportPath)) {
    $resolvedReportPath = [IO.Path]::GetFullPath($ReportPath)
    if ([IO.Path]::GetExtension($resolvedReportPath) -ne ".json") {
        throw "ReportPath must end in .json."
    }
    if (Test-Path -LiteralPath $resolvedReportPath) {
        if (-not $OverwriteReport) {
            throw "ReportPath already exists. Choose a new .json path or pass -OverwriteReport explicitly."
        }
        if (-not (Test-Path -LiteralPath $resolvedReportPath -PathType Leaf)) {
            throw "ReportPath must identify a file, not an existing directory."
        }
    }
}
if ([string]::IsNullOrWhiteSpace($Python)) {
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "Python was not found. Activate .venv or pass -Python <path-to-python.exe>."
    }
    $Python = $venvPython
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python executable was not found: $Python"
}

function Invoke-AcceptanceStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    $stepStarted = Get-Date
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    try {
        & $Action
        $stepRecords.Add([ordered]@{ id = $Name; status = "passed"; elapsed_ms = [int][math]::Round(((Get-Date) - $stepStarted).TotalMilliseconds) })
        Write-Host "PASS - $Name" -ForegroundColor Green
    }
    catch {
        $stepRecords.Add([ordered]@{ id = $Name; status = "failed"; elapsed_ms = [int][math]::Round(((Get-Date) - $stepStarted).TotalMilliseconds) })
        throw
    }
}

function Write-AcceptanceReport {
    param([Parameter(Mandatory = $true)][ValidateSet("passed", "failed")][string]$Status)

    if ($null -eq $resolvedReportPath) { return }
    $reportDirectory = Split-Path -Parent $resolvedReportPath
    if ([string]::IsNullOrWhiteSpace($reportDirectory)) {
        throw "ReportPath must include a parent directory."
    }
    New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
    $payload = [ordered]@{
        schema_version = "1.1"
        trust_status = "local_acceptance_receipt_not_provider_execution_or_scientific_evidence"
        status = $Status
        started_at = $startedAt
        finished_at = (Get-Date).ToUniversalTime().ToString("o")
        options = [ordered]@{
            dsh_profile_smoke = -not $SkipDshProfileSmoke
            plugin_packages = -not $SkipPluginPackages
            report_overwrite = [bool]$OverwriteReport
        }
        steps = @($stepRecords)
    }
    $canonicalPayload = $payload | ConvertTo-Json -Depth 5 -Compress
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        $contentSha256 = ([BitConverter]::ToString($sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonicalPayload)))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha256.Dispose()
    }
    $report = [ordered]@{}
    foreach ($key in $payload.Keys) { $report[$key] = $payload[$key] }
    $report["content_sha256"] = $contentSha256
    [IO.File]::WriteAllText($resolvedReportPath, ($report | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter()][string[]]$Arguments = @()
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

$pluginDirectories = @(
    "dsh-cosmatter-mission-plugin",
    "dsh-cosmatter-observability-plugin",
    "dsh-cosmatter-policy-plugin",
    "dsh-cosmatter-research-plugin",
    "dsh-cosmatter-review-plugin",
    "dsh-cosmatter-document-plugin",
    "dsh-cosmatter-graph-plugin"
)

try {
    Invoke-AcceptanceStep "Python unit and integration tests" {
        & (Join-Path $PSScriptRoot "test-all.ps1") -Python $Python
        if ($LASTEXITCODE -ne 0) { throw "Python test entrypoint failed with exit code $LASTEXITCODE." }
    }

    Invoke-AcceptanceStep "Frontend type check and test suite" {
        Push-Location (Join-Path $projectRoot "frontend")
        try {
            Invoke-CheckedCommand "Frontend type check" "npm.cmd" @("run", "check")
            Invoke-CheckedCommand "Frontend tests" "npm.cmd" @("test")
        }
        finally {
            Pop-Location
        }
    }

    Invoke-AcceptanceStep "DSH release and synthetic-replay gates" {
        Invoke-CheckedCommand "DSH release gate" $Python @("tools/verify_dsh_plugin_release.py")
        if (-not $SkipDshProfileSmoke) {
            Invoke-CheckedCommand "DSH isolated profile smoke" $Python @("tools/verify_dsh_plugin_release.py", "--profile-smoke")
        }
        Invoke-CheckedCommand "DSH synthetic replay" $Python @("tools/verify_dsh_synthetic_replay.py")
        Invoke-CheckedCommand "DSH harness recipe" $Python @("tools/verify_dsh_harness_recipe.py")
    }

    if (-not $SkipPluginPackages) {
        foreach ($pluginDirectory in $pluginDirectories) {
            Invoke-AcceptanceStep "DSH package $pluginDirectory" {
                Push-Location (Join-Path $projectRoot (Join-Path "plugins" $pluginDirectory))
                try {
                    Invoke-CheckedCommand "$pluginDirectory tests" "npm.cmd" @("test")
                    Invoke-CheckedCommand "$pluginDirectory package manifest" "npm.cmd" @("pack", "--dry-run")
                }
                finally {
                    Pop-Location
                }
            }
        }
    }

    Invoke-AcceptanceStep "Tracked-diff whitespace check" {
        Invoke-CheckedCommand "Git whitespace check" "git" @("diff", "--check")
    }
}
catch {
    try { Write-AcceptanceReport "failed" } catch { Write-Host "FAILED - unable to write the requested acceptance receipt." -ForegroundColor Red }
    Write-Host ""
    Write-Host "FAILED - CosMatter local acceptance failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-AcceptanceReport "passed"
Write-Host ""
Write-Host "OK - CosMatter full local acceptance passed." -ForegroundColor Green
exit 0
