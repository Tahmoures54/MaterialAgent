# Build iMat Warehouse Windows package with PyInstaller
# Run from repo root:  powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Installing build deps..." -ForegroundColor Cyan
python -m pip install -U pip pyinstaller
python -m pip install -r requirements.txt

Write-Host "Building..." -ForegroundColor Cyan
pyinstaller packaging/imat.spec --noconfirm

Write-Host "Output: dist/iMatWarehouse/" -ForegroundColor Green
Write-Host "Copy aimat.db only if you intentionally ship sample data." -ForegroundColor Yellow
