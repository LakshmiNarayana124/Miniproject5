# ============================================================
# IntelliWatch — Render Deploy Script
# Usage:
#   $env:RENDER_API_KEY     = "rnd_..."          (required)
#   $env:DATABASE_URL       = "postgresql://..."  (required - new Neon URL after rotation)
#   $env:INTELLIWATCH_SECRET_KEY = "..."          (required)
#   .\deploy_render.ps1
# ============================================================

param([string]$ApiKey = $env:RENDER_API_KEY)

if (-not $ApiKey)   { throw "Set RENDER_API_KEY env var or pass -ApiKey rnd_..." }
if (-not $env:DATABASE_URL) { throw "Set DATABASE_URL env var to your Neon connection string" }
if (-not $env:INTELLIWATCH_SECRET_KEY) { throw "Set INTELLIWATCH_SECRET_KEY env var" }

$ErrorActionPreference = "Stop"
$RENDER_API = "https://api.render.com/v1"
$headers    = @{ "Authorization" = "Bearer $ApiKey"; "Content-Type" = "application/json"; "Accept" = "application/json" }

function rAPI($method, $path, $body=$null) {
    $p = @{ Uri="$RENDER_API$path"; Method=$method; Headers=$headers; TimeoutSec=30 }
    if ($body) { $p.Body = ($body | ConvertTo-Json -Depth 10) }
    try   { return Invoke-RestMethod @p }
    catch { $m=$_.Exception.Message; try{$m=($_.ErrorDetails.Message|ConvertFrom-Json).message}catch{}; throw "Render $method $path : $m" }
}

Write-Host "`n=== IntelliWatch → Render Deploy ===" -ForegroundColor Cyan

# 1. Validate key
Write-Host "[1/4] Validating key..." -NoNewline
$owner = rAPI "GET" "/owners?limit=1"
$ownerId = $owner[0].owner.id
Write-Host " OK ($($owner[0].owner.name))" -ForegroundColor Green

# 2. Create or find service
Write-Host "[2/4] Setting up service..." -NoNewline
$existing = rAPI "GET" "/services?limit=20"
$svc = $existing | Where-Object { $_.service.name -eq "intelliwatch-backend" } | Select-Object -First 1

if ($svc) {
    $serviceId  = $svc.service.id
    $serviceUrl = "https://$($svc.service.serviceDetails.url)"
    Write-Host " already exists, updating env vars..." -ForegroundColor Yellow

    # Update env vars on existing service
    $envBody = @{
        envVars = @(
            @{ key="DATABASE_URL";              value=$env:DATABASE_URL }
            @{ key="INTELLIWATCH_SECRET_KEY";   value=$env:INTELLIWATCH_SECRET_KEY }
            @{ key="INTELLIWATCH_CORS_ORIGINS"; value="https://intelliwatch-iw.vercel.app" }
            @{ key="FIREBASE_PROJECT_ID";       value="intelliwatch-66ad0" }
            @{ key="INTELLIWATCH_HOST";         value="0.0.0.0" }
            @{ key="PYTHON_VERSION";            value="3.11.9" }
        )
    }
    rAPI "PUT" "/services/$serviceId/env-vars" $envBody | Out-Null
    Write-Host " env vars updated" -ForegroundColor Green

} else {
    # Create new service
    $body = @{
        type         = "web_service"
        name         = "intelliwatch-backend"
        ownerId      = $ownerId
        repo         = "https://github.com/LakshmiNarayana124/Miniproject5"
        branch       = "main"
        rootDir      = "Backend"
        buildCommand = "pip install -r requirements.txt"
        startCommand = "uvicorn server:app --host 0.0.0.0 --port `$PORT"
        plan         = "free"
        runtime      = "python"
        region       = "oregon"
        healthCheckPath = "/auth/registration-status"
        envVars      = @(
            @{ key="DATABASE_URL";              value=$env:DATABASE_URL }
            @{ key="INTELLIWATCH_SECRET_KEY";   value=$env:INTELLIWATCH_SECRET_KEY }
            @{ key="INTELLIWATCH_CORS_ORIGINS"; value="https://intelliwatch-iw.vercel.app" }
            @{ key="FIREBASE_PROJECT_ID";       value="intelliwatch-66ad0" }
            @{ key="INTELLIWATCH_HOST";         value="0.0.0.0" }
            @{ key="PYTHON_VERSION";            value="3.11.9" }
        )
    }
    $result    = rAPI "POST" "/services" $body
    $serviceId = $result.service.id
    $serviceUrl= "https://$($result.service.serviceDetails.url)"
    Write-Host " created: $serviceId" -ForegroundColor Green
}

# 3. Wait for deploy
Write-Host "[3/4] Waiting for build (up to 8 min)..." -ForegroundColor Cyan
$start = Get-Date; $last = ""
do {
    Start-Sleep -Seconds 20
    $d      = rAPI "GET" "/services/$serviceId/deploys?limit=1"
    $status = $d[0].deploy.status
    $sec    = [int]((Get-Date)-$start).TotalSeconds
    if ($status -ne $last) { Write-Host "  ${sec}s $status"; $last = $status }
} while ($status -notin @("live","failed","canceled","deactivated") -and $sec -lt 480)

if ($status -ne "live") {
    Write-Host "Build ended with: $status — check https://dashboard.render.com" -ForegroundColor Red
    Write-Host "URL when ready: $serviceUrl"
    exit 1
}
Write-Host "[3/4] Live! $serviceUrl" -ForegroundColor Green

# 4. Update Vercel env → new Render URL and redeploy
Write-Host "[4/4] Updating Vercel..." -NoNewline
if ($env:VERCEL_TOKEN -and $env:VERCEL_PROJECT_ID -and $env:VERCEL_TEAM_ID) {
    $vH = @{ "Authorization"="Bearer $env:VERCEL_TOKEN"; "Content-Type"="application/json" }
    $envs = Invoke-RestMethod "https://api.vercel.com/v9/projects/$env:VERCEL_PROJECT_ID/env?teamId=$env:VERCEL_TEAM_ID" -Headers $vH
    $apiId = ($envs.envs | Where-Object key -eq "VITE_API_URL").id
    if ($apiId) {
        $pb = @{value=$serviceUrl;target=@("production","preview");type="plain"} | ConvertTo-Json
        Invoke-RestMethod "https://api.vercel.com/v9/projects/$env:VERCEL_PROJECT_ID/env/$apiId`?teamId=$env:VERCEL_TEAM_ID" -Headers $vH -Method PATCH -Body $pb | Out-Null
        Write-Host " VITE_API_URL updated" -ForegroundColor Green
    }
} else {
    Write-Host " skipped (VERCEL_TOKEN not set - update manually)" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " DONE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Frontend : https://intelliwatch-iw.vercel.app"
Write-Host " Backend  : $serviceUrl"
Write-Host " API Docs : $serviceUrl/docs"
Write-Host "========================================"
