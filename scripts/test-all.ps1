[CmdletBinding()]
param(
    [string]$Python = $env:COSMATTER_PYTHON
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Python)) {
    $venvPython = Join-Path $projectRoot ".venv\\Scripts\\python.exe"
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        $Python = $venvPython
    }
    else {
        $pythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue
        if ($null -eq $pythonCommand) {
            throw "Python was not found. Activate .venv or pass -Python <path-to-python.exe>."
        }
        $Python = $pythonCommand.Source
    }
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python executable was not found: $Python"
}

$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = (Join-Path $projectRoot "src")
try {
    & $Python -m unittest discover -s tests -v
    $testExitCode = $LASTEXITCODE
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}

if ($testExitCode -ne 0) {
    Write-Host "FAILED - CosMatter full unittest acceptance failed (exit code $testExitCode)." -ForegroundColor Red
    exit $testExitCode
}

Write-Host ""
Write-Host "OK - CosMatter full unittest acceptance passed." -ForegroundColor Green
exit 0
