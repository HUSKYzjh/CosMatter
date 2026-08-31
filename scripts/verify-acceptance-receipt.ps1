[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Path)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Fail-Receipt([string]$Message) {
    Write-Output (([ordered]@{ verified = $false; error = $Message } | ConvertTo-Json -Compress))
    exit 2
}

function Get-TextSha256([string]$Value) {
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value)))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha256.Dispose()
    }
}

try {
    $raw = [IO.File]::ReadAllText([IO.Path]::GetFullPath($Path), [Text.UTF8Encoding]::new($false))
    if ($raw -match '(?i)(api[_-]?key|token|https?://|[a-z]:\\)') { Fail-Receipt "receipt contains a forbidden sensitive marker" }
    $receipt = $raw | ConvertFrom-Json
}
catch {
    Fail-Receipt "receipt cannot be read as safe JSON"
}

$expectedKeys = @("schema_version", "trust_status", "status", "started_at", "finished_at", "options", "steps", "content_sha256")
$receiptKeySet = ($receipt.PSObject.Properties.Name | Sort-Object) -join "|"
$expectedKeySet = ($expectedKeys | Sort-Object) -join "|"
if ($receiptKeySet -ne $expectedKeySet) { Fail-Receipt "receipt fields are invalid" }
if ($receipt.schema_version -ne "1.1" -or $receipt.trust_status -ne "local_acceptance_receipt_not_provider_execution_or_scientific_evidence" -or $receipt.status -notin @("passed", "failed") -or $receipt.content_sha256 -notmatch '^[0-9a-f]{64}$') { Fail-Receipt "receipt identity is invalid" }
$optionKeySet = if ($receipt.options -is [pscustomobject]) { ($receipt.options.PSObject.Properties.Name | Sort-Object) -join "|" } else { "" }
if ($receipt.options -isnot [pscustomobject] -or $optionKeySet -ne "dsh_profile_smoke|plugin_packages|report_overwrite" -or @($receipt.options.PSObject.Properties.Value | Where-Object { $_ -isnot [bool] }).Count -ne 0) { Fail-Receipt "receipt options are invalid" }
if ($receipt.steps -isnot [System.Collections.IEnumerable] -or @($receipt.steps).Count -eq 0) { Fail-Receipt "receipt steps are invalid" }

$safeSteps = [System.Collections.Generic.List[object]]::new()
foreach ($step in $receipt.steps) {
    $stepKeySet = if ($step -is [pscustomobject]) { ($step.PSObject.Properties.Name | Sort-Object) -join "|" } else { "" }
    if ($step -isnot [pscustomobject] -or $stepKeySet -ne "elapsed_ms|id|status" -or $step.id -isnot [string] -or $step.id.Length -eq 0 -or $step.id.Length -gt 120 -or $step.status -notin @("passed", "failed") -or ($step.elapsed_ms -isnot [int] -and $step.elapsed_ms -isnot [long]) -or $step.elapsed_ms -lt 0) { Fail-Receipt "receipt step is invalid" }
    $safeSteps.Add([ordered]@{ id = $step.id; status = $step.status; elapsed_ms = $step.elapsed_ms })
}

$payload = [ordered]@{
    schema_version = $receipt.schema_version
    trust_status = $receipt.trust_status
    status = $receipt.status
    started_at = $receipt.started_at
    finished_at = $receipt.finished_at
    options = [ordered]@{
        dsh_profile_smoke = $receipt.options.dsh_profile_smoke
        plugin_packages = $receipt.options.plugin_packages
        report_overwrite = $receipt.options.report_overwrite
    }
    steps = @($safeSteps)
}
$actualHash = Get-TextSha256 ($payload | ConvertTo-Json -Depth 5 -Compress)
if ($actualHash -ne $receipt.content_sha256) { Fail-Receipt "receipt content hash does not match" }

Write-Output (([ordered]@{ verified = $true; schema_version = $receipt.schema_version; status = $receipt.status; step_count = @($safeSteps).Count } | ConvertTo-Json -Compress))
