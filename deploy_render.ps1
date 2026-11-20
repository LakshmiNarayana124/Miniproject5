# IntelliWatch - Render Deploy Script
# Secrets come from environment variables only - never hardcoded here
param([string]$ApiKey = $env:RENDER_API_KEY)

if (-not $ApiKey)                      { throw "Set RENDER_API_KEY" }
if (-not $env:DATABASE_URL)            { throw "Set DATABASE_URL" }
if (-not $env:INTELLIWATCH_SECRET_KEY) { throw "Set INTELLIWATCH_SECRET_KEY" }

$ErrorActionPreference = "Stop"
$BASE    = "https://api.render.com/v1"
$RH      = @{ "Authorization"="Bearer $ApiKey"; "Content-Type"="application/json"; "Accept"="application/json" }
$VT      = $env:VERCEL_TOKEN
$VP      = $env:VERCEL_PROJECT_ID
$VTM     = $env:VERCEL_TEAM_ID
$VH      = @{ "Authorization"="Bearer $VT"; "Content-Type"="application/json" }

function rAPI($method, $path, $body=$null) {
    $p = @{ Uri="$BASE$path"; Method=$method; Headers=$RH; TimeoutSec=30 }
    if ($body) { $p.Body = ($body | ConvertTo-Json -Depth 10) }
    try { return Invoke-RestMethod @p }
    catch {
        $m = $_.Exception.Message
        try { $m = ($_.ErrorDetails.Message | ConvertFrom-Json).message } catch {}
        throw "Render $method $path : $m"
    }
}

Write-Host ""
Write-Host "=== IntelliWatch Render Deploy ===" -ForegroundColor Cyan

# Step 1 — validate key and get owner
Write-Host "[1/4] Validating key..." -NoNewline
$owners  = rAPI "GET" "/owners?limit=1"
$ownerId = $owners[0].owner.id
Write-Host " OK ($($owners[0].owner.name))" -ForegroundColor Green

# Step 2 — create or reuse service
Write-Host "[2/4] Setting up Render service..." -NoNewline
$existing = rAPI "GET" "/services?limit=20"
$svc      = $existing | Where-Object { $_.service.name -eq "intelliwatch-backend" } | Select-Object -First 1

$envVarList = @(
    @{ key="DATABASE_URL";              value=$env:DATABASE_URL }
    @{ key="INTELLIWATCH_SECRET_KEY";   value=$env:INTELLIWATCH_SECRET_KEY }
    @{ key="INTELLIWATCH_CORS_ORIGINS"; value="https://intelliwatch-iw.vercel.app" }
    @{ key="FIREBASE_PROJECT_ID";       value="intelliwatch-66ad0" }
    @{ key="INTELLIWATCH_HOST";         value="0.0.0.0" }
    @{ key="PYTHON_VERSION";            value="3.11.9" }
)

if ($svc) {
    $serviceId  = $svc.service.id
    $serviceUrl = "https://$($svc.service.serviceDetails.url)"
    Write-Host " exists, updating env vars..." -ForegroundColor Yellow
    # env-vars PUT takes a plain array
    Invoke-RestMethod "$BASE/services/$serviceId/env-vars" -Headers $RH -Method PUT -Body ($envVarList | ConvertTo-Json -Depth 5) -TimeoutSec 30 | Out-Null
    # trigger a manual deploy
    Invoke-RestMethod "$BASE/services/$serviceId/deploys" -Headers $RH -Method POST -Body '{"clearCache":"do_not_clear"}' -TimeoutSec 30 | Out-Null
    Write-Host " redeploying" -ForegroundColor Green
} else {
    $body = @{
        type    = "web_service"
        name    = "intelliwatch-backend"
        ownerId = $ownerId
        repo    = "https://github.com/LakshmiNarayana124/Miniproject5"
        branch  = "main"
        rootDir = "Backend"
        envVars = $envVarList
        serviceDetails = @{
            runtime         = "python"
            plan            = "free"
            region          = "oregon"
            healthCheckPath = "/auth/registration-status"
            envSpecificDetails = @{
                buildCommand = "pip install -r requirements.txt"
                startCommand = "uvicorn server:app --host 0.0.0.0 --port `$PORT"
            }
        }
    }
    $result     = rAPI "POST" "/services" $body
    $serviceId  = $result.service.id
    $serviceUrl = "https://$($result.service.serviceDetails.url)"
    Write-Host " created: $serviceId" -ForegroundColor Green
}

# Step 3 — wait for build to go live
Write-Host "[3/4] Waiting for build (~4 min)..." -ForegroundColor Cyan
$start = Get-Date; $last = ""
do {
    Start-Sleep -Seconds 20
    $deploys = rAPI "GET" "/services/$serviceId/deploys?limit=1"
    $status  = $deploys[0].deploy.status
    $sec     = [int]((Get-Date) - $start).TotalSeconds
    if ($status -ne $last) { Write-Host "  ${sec}s $status"; $last = $status }
} while ($status -notin @("live","failed","canceled","deactivated") -and $sec -lt 600)

if ($status -ne "live") {
    Write-Host ""
    Write-Host "Build ended: $status" -ForegroundColor Red
    Write-Host "Check: https://dashboard.render.com"
    Write-Host "Once live, update Vercel manually: VITE_API_URL = $serviceUrl"
    exit 1
}
Write-Host "[3/4] Backend live: $serviceUrl" -ForegroundColor Green

# Step 4 — update Vercel and redeploy
Write-Host "[4/4] Wiring Vercel to Render..." -NoNewline
$envs = Invoke-RestMethod "https://api.vercel.com/v9/projects/$VP/env?teamId=$VTM" -Headers $VH
$eid  = ($envs.envs | Where-Object key -eq "VITE_API_URL").id
if ($eid) {
    $pb = @{ value=$serviceUrl; target=@("production","preview"); type="plain" } | ConvertTo-Json
    Invoke-RestMethod "https://api.vercel.com/v9/projects/$VP/env/$eid`?teamId=$VTM" -Headers $VH -Method PATCH -Body $pb | Out-Null
}
# trigger Vercel redeploy
$db = @{
    name      = "intelliwatch"
    target    = "production"
    gitSource = @{ type="github"; repo="Miniproject5"; ref="main"; repoId="1422077519" }
} | ConvertTo-Json -Depth 5
$nd = Invoke-RestMethod "https://api.vercel.com/v13/deployments?teamId=$VTM&forceNew=1" -Headers $VH -Method POST -Body $db -ErrorAction SilentlyContinue
# wait for Vercel build
if ($nd.id) {
    $vs = ""; $t0 = Get-Date
    do {
        Start-Sleep -Seconds 15
        $vr = Invoke-RestMethod "https://api.vercel.com/v13/deployments/$($nd.id)?teamId=$VTM" -Headers $VH -ErrorAction SilentlyContinue
        $vs = $vr.readyState
    } while ($vs -notin @("READY","ERROR","CANCELED") -and ([int]((Get-Date)-$t0).TotalSeconds) -lt 240)
    if ($vs -eq "READY") {
        Invoke-RestMethod "https://api.vercel.com/v2/deployments/$($nd.id)/aliases?teamId=$VTM" -Headers $VH -Method POST -Body (@{alias="intelliwatch-iw.vercel.app"} | ConvertTo-Json) | Out-Null
    }
}
Write-Host " done" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host " Frontend : https://intelliwatch-iw.vercel.app"
Write-Host " Backend  : $serviceUrl"
Write-Host " API Docs : $serviceUrl/docs"
Write-Host " Database : Neon Postgres (free)"
Write-Host "=========================================="
Write-Host " Google Sign-In : enabled (FIREBASE_PROJECT_ID set)"
Write-Host "=========================================="
