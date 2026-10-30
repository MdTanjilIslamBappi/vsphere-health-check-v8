#Requires -Version 5.1
<#
.SYNOPSIS
    Installs vhealth into a project-local virtual environment on Windows.
.DESCRIPTION
    Creates .venv (or -VenvDir), installs dependencies from the committed
    uv.lock, installs vhealth into it, and verifies the CLI works. Safe to
    run repeatedly. Does not require administrator privileges and never
    touches global/system Python packages.

    If you access this same checkout from both Windows and WSL/Linux (e.g.
    C:\path and /mnt/c/path are the same folder), pass a different -VenvDir
    here so the two OSes don't fight over one .venv -- a Windows venv and a
    Linux venv cannot be the same directory:
        .\scripts\windows\install.ps1 -VenvDir .venv-windows
.PARAMETER VenvDir
    Directory to create the virtual environment in. Defaults to .venv.
#>

param(
    [string]$VenvDir = ".venv"
)

$ErrorActionPreference = "Stop"

function Write-Step($message) {
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Fail($message) {
    Write-Host "ERROR: $message" -ForegroundColor Red
    exit 1
}

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot
$env:UV_PROJECT_ENVIRONMENT = $VenvDir

Write-Step "Checking for uv"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Fail "uv was not found on PATH. Install it from https://docs.astral.sh/uv/ and re-run this script.`nQuick install (no admin required): irm https://astral.sh/uv/install.ps1 | iex"
}
$uvVersion = (& uv --version) 2>&1
Write-Host "    Found: $uvVersion"

Write-Step "Checking for a usable Python interpreter"
$pythonCheck = & uv python find ">=3.11" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "    No Python >=3.11 found; letting uv install one into its own managed location."
}

if ((Test-Path $VenvDir) -and -not (Test-Path "$VenvDir\Scripts\python.exe")) {
    Fail "'$VenvDir' already exists but isn't a Windows virtual environment (missing $VenvDir\Scripts\python.exe). This usually means the same checkout is also used from WSL/Linux, which created $VenvDir as a Linux venv ($VenvDir/bin/...) -- a Linux venv and a Windows venv can't share one directory. Re-run with a different -VenvDir instead, e.g.:`n    .\scripts\windows\install.ps1 -VenvDir .venv-windows"
}

if (Test-Path $VenvDir) {
    Write-Step "Virtual environment already exists at $VenvDir (reusing it)"
} else {
    Write-Step "Creating project-local virtual environment ($VenvDir)"
    & uv venv --python ">=3.11" $VenvDir
    if ($LASTEXITCODE -ne 0) { Fail "Failed to create the virtual environment." }
}

Write-Step "Installing locked dependencies (uv sync)"
& uv sync --locked
if ($LASTEXITCODE -ne 0) {
    Write-Host "    'uv sync --locked' failed; this means uv.lock is out of date with pyproject.toml." -ForegroundColor Yellow
    Fail "Dependency sync failed. If you intentionally changed pyproject.toml, run 'uv lock' first and commit the updated uv.lock."
}

Write-Step "Verifying the installed CLI"
$versionOutput = & "$VenvDir\Scripts\vhealth.exe" --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Fail "vhealth was installed but '--version' failed:`n$versionOutput"
}
Write-Host "    $versionOutput"

Write-Host ""
Write-Host "Install complete." -ForegroundColor Green
Write-Host ""
Write-Host "Run vhealth with:"
Write-Host "    $RepoRoot\$VenvDir\Scripts\vhealth.exe --help"
Write-Host "or, after activating the environment:"
Write-Host "    $RepoRoot\$VenvDir\Scripts\Activate.ps1"
Write-Host "    vhealth --help"
