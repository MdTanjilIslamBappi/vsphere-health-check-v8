#Requires -Version 5.1
<#
.SYNOPSIS
    Installs vhealth into a project-local virtual environment on Windows.
.DESCRIPTION
    Creates .venv, installs dependencies from the committed uv.lock, installs
    vhealth into it, and verifies the CLI works. Safe to run repeatedly. Does
    not require administrator privileges and never touches global/system
    Python packages.
#>

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

if (Test-Path ".venv") {
    Write-Step "Virtual environment already exists at .venv (reusing it)"
} else {
    Write-Step "Creating project-local virtual environment (.venv)"
    & uv venv --python ">=3.11" ".venv"
    if ($LASTEXITCODE -ne 0) { Fail "Failed to create the virtual environment." }
}

Write-Step "Installing locked dependencies (uv sync)"
& uv sync --locked
if ($LASTEXITCODE -ne 0) {
    Write-Host "    'uv sync --locked' failed; this means uv.lock is out of date with pyproject.toml." -ForegroundColor Yellow
    Fail "Dependency sync failed. If you intentionally changed pyproject.toml, run 'uv lock' first and commit the updated uv.lock."
}

Write-Step "Verifying the installed CLI"
$versionOutput = & ".venv\Scripts\vhealth.exe" --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Fail "vhealth was installed but '--version' failed:`n$versionOutput"
}
Write-Host "    $versionOutput"

Write-Host ""
Write-Host "Install complete." -ForegroundColor Green
Write-Host ""
Write-Host "Run vhealth with:"
Write-Host "    $RepoRoot\.venv\Scripts\vhealth.exe --help"
Write-Host "or, after activating the environment:"
Write-Host "    $RepoRoot\.venv\Scripts\Activate.ps1"
Write-Host "    vhealth --help"
