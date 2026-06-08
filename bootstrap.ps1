#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = $null
foreach ($name in @("python", "python3", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { $Py = $cmd.Source; break }
}
if (-not $Py) {
    Write-Error "python not found in PATH. Install Python 3.11+."
    exit 1
}

& $Py (Join-Path $Root "scripts\bootstrap.py") @args
exit $LASTEXITCODE
