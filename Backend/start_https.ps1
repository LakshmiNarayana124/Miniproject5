# ── 6. Update frontend/.env.local to point at HTTPS backend ──
$envLocal = Join-Path $ROOT "frontend" ".env.local"

if (Test-Path $envLocal) {
    $lines = Get-Content $envLocal
    $found = $false

    $updated = $lines | ForEach-Object {
        if ($_ -match '^\s*VITE_API_URL\s*=') {
            $found = $true
            "VITE_API_URL=https://localhost:8000"
        }
        else {
            $_
        }
    }

    if (-not $found) {
        $updated += "VITE_API_URL=https://localhost:8000"
    }

    Set-Content -Path $envLocal -Value $updated
}
else {
    Set-Content -Path $envLocal -Value "VITE_API_URL=https://localhost:8000"
}

Write-Host "HTTPS API URL configured in frontend/.env.local" -ForegroundColor Green