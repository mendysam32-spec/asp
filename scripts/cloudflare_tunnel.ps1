# Cloudflare Tunnel - expose ASP to your phone / laptop.
# Your PC stays the host (Flask + ffmpeg can't run on Workers/Pages).
# Usage:  powershell -ExecutionPolicy Bypass -File scripts/cloudflare_tunnel.ps1
# Then open the printed https://...trycloudflare.com/?pw=YOUR_PASSWORD on any device.
param(
  [int]$Port = 5001
)

$ErrorActionPreference = "Stop"

# 1. Check dashboard is running
try {
  $h = Invoke-RestMethod -Uri "http://localhost:$Port/api/health" -TimeoutSec 5
  Write-Host "Dashboard OK (running=$($h.agent_running))" -ForegroundColor Green
} catch {
  Write-Host "Dashboard NOT running on :$Port - start it first:  python run_background.py" -ForegroundColor Red
  exit 1
}

# 2. Check password is set (tunnel without password = anyone can post as you)
$envFile = Join-Path $PSScriptRoot "..\\.env"
$hasPw = $false
if (Test-Path $envFile) {
  $txt = Get-Content $envFile -Raw
  $hasPw = $txt -match "(?m)^DASHBOARD_PASSWORD=.+"
}
if (-not $hasPw) {
  Write-Host "Set DASHBOARD_PASSWORD in .env first (see .env.example)." -ForegroundColor Red
  Write-Host "The tunnel exposes publish/terminal endpoints - never run it without a password." -ForegroundColor Yellow
  exit 1
}

# 3. Ensure cloudflared exists
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
  Write-Host "Installing cloudflared via winget..." -ForegroundColor Yellow
  winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
}

Write-Host ""
Write-Host "Starting tunnel: localhost:$Port -> internet (Ctrl+C to stop)" -ForegroundColor Cyan
Write-Host "Open the printed trycloudflare.com URL + ?pw=YOUR_PASSWORD on your other devices." -ForegroundColor Cyan
Write-Host ""
& cloudflared tunnel --url "http://localhost:$Port"
