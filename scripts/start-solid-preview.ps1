[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]*$')]
    [string]$RunId,
    [ValidateRange(1024, 65535)]
    [int]$Port = 8765,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontend = Join-Path $projectRoot 'frontend'
$bundle = Join-Path $projectRoot ("runs\{0}\ui.json" -f $RunId)

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Python virtual environment is missing. Create it with: python -m venv .venv'
}
if (-not (Test-Path -LiteralPath $bundle)) {
    throw "Missing exported UI bundle: $bundle. Run: .\.venv\Scripts\python.exe -m cosmatter export-ui --run-id $RunId"
}
if (-not $SkipBuild) {
    Push-Location $frontend
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Solid frontend build failed.' }
    }
    finally {
        Pop-Location
    }
}

Write-Host "CosMatter Solid preview: http://127.0.0.1:$Port/?ui=server"
& $python -m cosmatter preview-ui --solid --run-id $RunId --port $Port