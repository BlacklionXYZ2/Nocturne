<#
.SYNOPSIS
    PowerShell Launcher for the Local Agent & VTuber Management Center.
.DESCRIPTION
    Sets up virtual environment, installs dependencies, and launches the native desktop app.
#>

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  Local Agent & VTuber Management Center Launcher" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

# 1. Check Python
try {
    $pyVer = & python --version
    Write-Host "[INFO] Detected $pyVer" -ForegroundColor Gray
} catch {
    Write-Host "[ERROR] Python was not found in PATH." -ForegroundColor Red
    exit 1
}

# 2. Check or Create Virtual Environment
if (-not (Test-Path -Path ".venv")) {
    Write-Host "[INFO] Initializing Python virtual environment in .venv..." -ForegroundColor Yellow
    & python -m venv .venv
}

# 3. Activate Virtual Environment
$venvActivate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    . $venvActivate
}

# 4. Install / Verify Requirements
Write-Host "[INFO] Checking Python dependencies..." -ForegroundColor Gray
& pip install -r requirements.txt --quiet --disable-pip-version-check

# 5. Launch App
Write-Host "`n[INFO] Launching Native Desktop Window..." -ForegroundColor Green
& python app.py $args
