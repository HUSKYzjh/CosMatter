[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]*$')]
    [string]$RunId,
    [ValidateRange(1024, 65535)]
    [int]$Port = 8765,
    [switch]$Api,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontend = Join-Path $projectRoot 'frontend'
$workspaceRoot = Split-Path (Split-Path $projectRoot -Parent) -Parent
$workspaceRuntime = Join-Path $workspaceRoot 'case-data\runtime'
$dataRoot = if ($env:COSMATTER_DATA_ROOT) {
    [System.IO.Path]::GetFullPath($env:COSMATTER_DATA_ROOT)
}
elseif (Test-Path -LiteralPath $workspaceRuntime -PathType Container) {
    $workspaceRuntime
}
else {
    $projectRoot
}
$bundle = if ($RunId) { Join-Path $dataRoot ("runs\{0}\ui.json" -f $RunId) } else { $null }

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Python virtual environment is missing. Create it with: python -m venv .venv'
}
if ($bundle -and -not (Test-Path -LiteralPath $bundle)) {
    throw "Missing exported UI bundle for the selected run. Run: .\.venv\Scripts\python.exe -m cosmatter export-ui --run-id $RunId"
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

$args = @('preview-ui', '--solid', '--port', $Port)
if ($RunId) { $args += @('--run-id', $RunId) }
if ($Api) { $args += '--api' }
$query = if ($RunId -and $Api) { '?ui=server&api=local' } elseif ($RunId) { '?ui=server' } elseif ($Api) { '?api=local' } else { '' }
Write-Host "CosMatter Solid preview: http://127.0.0.1:$Port/$query"
& $python -m cosmatter @args
