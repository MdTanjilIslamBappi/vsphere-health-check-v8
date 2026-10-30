#Requires -Version 5.1
<#
.SYNOPSIS
    Removes what install.ps1 created, on Windows.
.DESCRIPTION
    Deletes the project-local virtual environment (.venv) and any local
    build/test caches. Safe to run repeatedly, including when nothing was
    ever installed. Requires no administrator privileges.

    Does NOT touch:
      - uv or Python themselves (installed outside this repo, and likely
        shared with other projects on this machine)
      - anything you passed to 'vhealth assess --output <dir>' (your own
        generated reports)
      - the cloned repo folder itself
    See the "Uninstall" section in README.md if you want those gone too.
#>

$ErrorActionPreference = "Stop"

function Write-Step($message) {
    Write-Host "==> $message" -ForegroundColor Cyan
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$removedSomething = $false

if (Test-Path ".venv") {
    Write-Step "Removing virtual environment (.venv)"
    Remove-Item -Recurse -Force ".venv"
    $removedSomething = $true
} else {
    Write-Host "    .venv not found (already removed, or vhealth was never installed here)."
}

$cacheDirs = @(".pytest_cache", ".ruff_cache", ".mypy_cache", "htmlcov", "dist", "build")
foreach ($dir in $cacheDirs) {
    if (Test-Path $dir) {
        Write-Step "Removing $dir"
        Remove-Item -Recurse -Force $dir
        $removedSomething = $true
    }
}

if (Test-Path ".coverage") {
    Write-Step "Removing .coverage"
    Remove-Item -Force ".coverage"
    $removedSomething = $true
}

Write-Host ""
if ($removedSomething) {
    Write-Host "Uninstall complete." -ForegroundColor Green
} else {
    Write-Host "Nothing to remove - vhealth wasn't installed in this folder." -ForegroundColor Green
}
Write-Host ""
Write-Host "Not touched (remove these yourself if you want a fully clean machine):"
Write-Host "  - uv / Python (shared with other projects; see https://docs.astral.sh/uv/)"
Write-Host "  - Any report folders you gave to 'vhealth assess --output ...'"
Write-Host "  - This cloned repo folder: $RepoRoot"
