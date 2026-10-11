# AI Server Launcher

$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==============================="
Write-Host "       Starting AI AI"
Write-Host "==============================="

Set-Location $ROOT

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python was not found. Install Python first."
    pause
    exit 1
}

Write-Host "AI folder: $ROOT"
Write-Host "Starting server.py..."
Write-Host ""

python server.py

Write-Host ""
Write-Host "AI server stopped."
pause
