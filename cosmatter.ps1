[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    Write-Error "CosMatter's project interpreter is missing. Run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e ."
    exit 2
}

& $pythonExe -m cosmatter @CommandArgs
exit $LASTEXITCODE
