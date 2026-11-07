#!/usr/bin/env pwsh
# ─────────────────────────────────────────────────────────────────────────────
# IntelliWatch — Frontend HTTPS Dev Launcher (Windows PowerShell)
#
# Switches .env.local to use https://localhost:8000 (the HTTPS backend) and
# starts the Vite dev server in HTTPS mode.
#
# Usage (from the frontend folder):
#   .\start_https.ps1
#
# Stop with Ctrl+C. The .env.local change is NOT reverted automatically;
# run .\start_http.ps1 or edit VITE_API_URL back to http:// for plain HTTP.
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = 'Stop'

$envLocal = Join-Path $PSScriptRoot ".env.local"

# ── Ensure .env.local exists ──────────────────────────────────────────────────
if (-not (Test-Path $envLocal)) {
    Write-Host "📄  Creating .env.local …" -ForegroundColor Cyan
    Set-Content $envLocal "VITE_API_URL=https://localhost:8000"
} else {
    # Update (or insert) VITE_API_URL for HTTPS
    $lines = Get-Content $envLocal
    $found = $false
    $updated = $lines | ForEach-Object {
        if ($_ -match '^\s*VITE_API_URL\s*=') {
            $found = $true
            "VITE_API_URL=https://localhost:8000"
        } else { $_ }
    }
    if (-not $found) { $updated += "VITE_API_URL=https://localhost:8000" }
    Set-Content $envLocal $updated
}

Write-Host "✅  VITE_API_URL set to https://localhost:8000 in .env.local" -ForegroundColor Green
Write-Host ""
Write-Host "   ⚠️  Make sure the backend is also running in HTTPS mode." -ForegroundColor Yellow
Write-Host "      Run  cd ..\Backend ; .\start_https.ps1  in another terminal." -ForegroundColor Yellow
Write-Host ""
Write-Host "   ⚠️  On first load your browser will warn about the self-signed" -ForegroundColor Yellow
Write-Host "      cert on port 8000.  Open https://localhost:8000/health in a" -ForegroundColor Yellow
Write-Host "      new tab and accept the cert, then return here." -ForegroundColor Yellow
Write-Host ""
Write-Host "🚀  Starting Vite dev server on https://localhost:5173 …" -ForegroundColor Cyan
Write-Host "    Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

npm run dev:https
