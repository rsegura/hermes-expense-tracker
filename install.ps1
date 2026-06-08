#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPy = Join-Path $Root "mcp\expense-tracker\.venv\Scripts\python.exe"
$Wizard = Join-Path $Root "scripts\install_wizard.py"

function Get-SystemPython {
    foreach ($name in @("python", "python3", "py")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    throw "python not found in PATH. Install Python 3.11+."
}

if (-not (Test-Path $VenvPy)) {
    $env:QUIET = "1"
    $env:BOOTSTRAP_DB = "0"
    & (Join-Path $Root "bootstrap.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not (Test-Path $VenvPy)) {
    Write-Error "MCP venv missing after bootstrap."
    exit 1
}

& $VenvPy $Wizard
exit $LASTEXITCODE
