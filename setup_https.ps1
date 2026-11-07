#!/usr/bin/env pwsh
# =============================================================================
# IntelliWatch — HTTPS Setup  (Windows, zero external installs)
#
# Generates a locally-trusted self-signed TLS certificate using the OpenSSL
# bundled with Git for Windows, then starts BOTH the frontend (Vite) and
# backend (uvicorn) over HTTPS.
#
# ── What this does ────────────────────────────────────────────────────────────
#   1. Locate openssl.exe inside Git for Windows (already on your machine).
#   2. Create  certs/intelliwatch.crt  +  certs/intelliwatch.key
#   3. Install the cert as a Trusted Root CA so browsers show a green padlock.
#   4. Update frontend/.env.local   → VITE_API_URL=https://localhost:8000
#   5. Print instructions to start the backend with SSL.
#
# ── Legal / cost ─────────────────────────────────────────────────────────────
#   • OpenSSL  — Apache-2.0 / OpenSSL licence (free, open-source)
#   • Git       — GPL-2.0 (free)
#   • Vite      — MIT (free)
#   • uvicorn   — BSD-3-Clause (free)
#   No paid services, no cloud, no subscriptions.
#
# ── Run once ─────────────────────────────────────────────────────────────────
#   Right-click → "Run with PowerShell"
#   -or-
#   powershell -ExecutionPolicy Bypass -File .\setup_https.ps1
# =============================================================================

$ErrorActionPreference = 'Stop'
$ROOT  = $PSScriptRoot
$CERTS = Join-Path $ROOT "certs"

# ── 1. Find openssl.exe (Git for Windows bundles it) ─────────────────────────
$OPENSSL = $null
$candidates = @(
    "C:\Program Files\Git\usr\bin\openssl.exe",
    "C:\Program Files (x86)\Git\usr\bin\openssl.exe",
    (Get-Command openssl -ErrorAction SilentlyContinue)?.Source
)
foreach ($c in $candidates) {
    if ($c -and (Test-Path $c)) { $OPENSSL = $c; break }
}
if (-not $OPENSSL) {
    Write-Error @"
openssl.exe not found.
Install Git for Windows from https://git-scm.com (free, includes OpenSSL).
Then re-run this script.
"@
    exit 1
}
Write-Host "✅  Using OpenSSL: $OPENSSL" -ForegroundColor Green

# ── 2. Create certs directory ─────────────────────────────────────────────────
if (-not (Test-Path $CERTS)) { New-Item -ItemType Directory -Path $CERTS | Out-Null }

$CERT = Join-Path $CERTS "intelliwatch.crt"
$KEY  = Join-Path $CERTS "intelliwatch.key"
$CNF  = Join-Path $CERTS "openssl.cnf"

# ── 3. Write OpenSSL config with Subject Alternative Names ───────────────────
#       This is what makes browsers trust it (CN alone is not enough).
@"
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
x509_extensions    = v3_req

[dn]
CN = intelliwatch-local

[v3_req]
subjectAltName = @alt_names
keyUsage       = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = localhost
DNS.2 = intelliwatch.local
IP.1  = 127.0.0.1
IP.2  = ::1
"@ | Set-Content $CNF

# ── 4. Generate cert (skip if already exists and still valid) ─────────────────
$needNew = $true
if ((Test-Path $CERT) -and (Test-Path $KEY)) {
    # Check expiry — regenerate only if expiring within 30 days
    $expiry = & $OPENSSL x509 -enddate -noout -in $CERT 2>$null
    if ($expiry -match 'notAfter=(.+)') {
        $exp = [datetime]::ParseExact($Matches[1].Trim(), "MMM  d HH:mm:ss yyyy GMT",
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::None)
        if ($exp -gt (Get-Date).AddDays(30)) {
            Write-Host "🔒  Existing certificate is still valid (expires $($exp.ToString('yyyy-MM-dd')))." -ForegroundColor Green
            $needNew = $false
        }
    }
}

if ($needNew) {
    Write-Host "⚙️   Generating 2048-bit RSA certificate …" -ForegroundColor Cyan
    & $OPENSSL req -x509 -newkey rsa:2048 `
        -keyout $KEY  -out $CERT `
        -days   825   -nodes `
        -config $CNF  2>&1 | Out-Null
    Write-Host "✅  Certificate written to $CERTS\" -ForegroundColor Green
}

# ── 5. Install cert as Trusted Root CA (so browsers show green padlock) ───────
Write-Host ""
Write-Host "🔐  Installing certificate as Trusted Root CA …" -ForegroundColor Cyan
Write-Host "    (Windows will ask for UAC / admin confirmation)" -ForegroundColor DarkGray
try {
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store(
        [System.Security.Cryptography.X509Certificates.StoreName]::Root,
        [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine)
    $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    $certObj = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($CERT)
    # Only install if not already there
    $existing = $store.Certificates | Where-Object { $_.Subject -eq $certObj.Subject }
    if (-not $existing) {
        $store.Add($certObj)
        Write-Host "✅  Certificate installed — browsers will now show a green padlock." -ForegroundColor Green
    } else {
        Write-Host "✅  Certificate already trusted." -ForegroundColor Green
    }
    $store.Close()
} catch {
    Write-Host "⚠️   Could not install as Trusted Root (need admin rights)." -ForegroundColor Yellow
    Write-Host "    Chrome/Edge will still show HTTPS but with a 'Not Secure' warning." -ForegroundColor Yellow
    Write-Host "    To fix: run this script as Administrator." -ForegroundColor Yellow
}

# ── 6. Update frontend/.env.local to point at HTTPS backend ──────────────────
$envLocal = Join-Path $ROOT "frontend" ".env.local"
if (Test-Path $envLocal) {
    $lines  = Get-Content $envLocal
    $found  = $false
    $updated = $lines | ForEach-Object {
        if ($_ -match '^\s*VITE_API_URL\s*=') { $found = $true; "VITE_API_URL=https://localhost:8000" }
        else { $_ }
    }
    if (-not $found) { $updated += "VITE_API_URL=https://localhost:8000" }
    Set-Content $envLocal $updated
} else {
    Set-Content $envLocal "VITE_API_URL=https://localhost:8000"
}
Write-Host "✅  frontend/.env.local → VITE_API_URL=https://localhost:8000" -ForegroundColor Green

# ── 7. Print next steps ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  HTTPS setup complete.  Start the app:" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Terminal 1 — Backend (HTTPS on port 8000):" -ForegroundColor White
Write-Host "    cd Backend" -ForegroundColor Yellow
Write-Host "    pip install uvicorn  # if not installed" -ForegroundColor DarkGray
Write-Host "    uvicorn server:app --ssl-keyfile ..\certs\intelliwatch.key --ssl-certfile ..\certs\intelliwatch.crt --host 0.0.0.0 --port 8000 --reload" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Terminal 2 — Frontend (HTTPS on port 5173):" -ForegroundColor White
Write-Host "    cd frontend" -ForegroundColor Yellow
Write-Host "    npm run dev" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Open: https://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "  ── For PRODUCTION (free, auto-renewing cert) ──────────" -ForegroundColor DarkGray
Write-Host "  Use Caddy — see  Caddyfile  in the repo root." -ForegroundColor DarkGray
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
