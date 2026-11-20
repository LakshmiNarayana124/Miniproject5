# IntelliWatch - Render Deploy Script
# Keys come from environment variables set before running - never hardcoded
param([string]$ApiKey = $env:RENDER_API_KEY)

if (-not $ApiKey)                        { throw "Set RENDER_API_KEY" }
if (-not $env:DATABASE_URL)              { throw "Set DATABASE_URL" }
if (-not $env:INTELLIWATCH_SECRET_KEY)   { throw "Set INTELLIWATCH_SECRET_KEY" }

$ErrorActionPreference = "Stop"
$BASE = "https://api.render.com/v1"
$H    = @{ "Authorization"="Bearer $ApiKey"; "Content-Type"="application/json"; "Accept"="application/json" }

function rAPI($method, $path, $body=$null) {
    $p = @{ Uri="$BASE$path"; Method=$method; Headers=$H; TimeoutSec=30 }
    if ($body) { $p.Body = ($body | ConvertTo-Json -Depth 10) }
    try   { return Invoke-RestMethod @p }
    catch {
        $m = $_.Exception.Message
        try { $m = ($_.ErrorDetails.Message | ConvertFrom-Json).message } catch {}
        throw "Render $method $path : $m"
    }
}

Write-Host ""
Write-Host "=== IntelliWatch Render Deploy ===" -ForegroundColor Cyan

# 1 - validate
Write-Host "[1/4] Validating key..." -NoNewline
$owners  = rAPI "GET" "/owners?limit=1"
$ownerId = $owners[0].owner.id
Write-Host " OK ($($owners[0].owner.name))" -ForegroundColor Green

# 2 - create or reuse service
Write-Host "[2/4] Setting up service..." -NoNewline
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
    Write-Host " exists ($serviceId), updating env vars..." -ForegroundColor Yellow
    rAPI "PUT" "/services/$serviceId/env-vars" @{ envVars=$envVarList } | Out-Null
    Write-Host " done" -ForegroundColor Green
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
            env    = "python"
            plan   = "free"
            region = "oregon"
            healthCheckPath    = "/auth/registration-status"
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

# 3 - wait for build
Write-Host "[3/4] Waiting for build (up to 8 min)..." -ForegroundColor Cyan
$start = Get-Date; $last = ""
do {
    Start-Sleep -Seconds 20
    $d      = rAPI "GET" "/services/$serviceId/deploys?limit=1"
    $status = $d[0].deploy.status
    $sec    = [int]((Get-Date) - $start).TotalSeconds
    if ($status -ne $last) { Write-Host "  ${sec}s $status"; $last = $status }
} while ($status -notin @("live","failed","canceled","deactivated") -and $sec -lt 480)

if ($status -ne "live") {
    Write-Host "Build status: $status - check https://dashboard.render.com" -ForegroundColor Red
    exit 1
}
Write-Host "[3/4] Live: $serviceUrl" -ForegroundColor Green

# 4 - update Vercel VITE_API_URL and redeploy
Write-Host "[4/4] Updating Vercel..." -NoNewline
$vT = $env:VERCEL_TOKEN; $vP = $env:VERCEL_PROJECT_ID; $vTm = $env:VERCEL_TEAM_ID
if ($vT -and $vP -and $vTm) {
    $vH   = @{ "Authorization"="Bearer $vT"; "Content-Type"="application/json" }
    $envs = Invoke-RestMethod "https://api.vercel.com/v9/projects/$vP/env?teamId=$vTm" -Headers $vH
    $eid  = ($envs.envs | Where-Object key -eq "VITE_API_URL").id
    if ($eid) {
        $pb = @{ value=$serviceUrl; target=@("production","preview"); type="plain" } | ConvertTo-Json
        Invoke-RestMethod "https://api.vercel.com/v9/projects/$vP/env/$eid`?teamId=$vTm" -Headers $vH -Method PATCH -Body $pb | Out-Null
    }
    # trigger redeploy
    $db = @{ name="intelliwatch"; target="production"; gitSource=@{ type="github"; repo="Miniproject5"; ref="main"; repoId="1422077519" } } | ConvertTo-Json -Depth 5
    $nd = Invoke-RestMethod "https://api.vercel.com/v13/deployments?teamId=$vTm&forceNew=1" -Headers $vH -Method POST -Body $db -ErrorAction SilentlyContinue
    # wait up to 3 min for Vercel build
    if ($nd.id) {
        $vs = ""; $vs2 = Get-Date
        do {
            Start-Sleep -Seconds 15
            $vr = Invoke-RestMethod "https://api.vercel.com/v13/deployments/$($nd.id)?teamId=$vTm" -Headers $vH -ErrorAction SilentlyContinue
            $vs = $vr.readyState
        } while ($vs -notin @("READY","ERROR","CANCELED") -and ([int]((Get-Date)-$vs2).TotalSeconds) -lt 180)
        if ($vs -eq "READY") {
            Invoke-RestMethod "https://api.vercel.com/v2/deployments/$($nd.id)/aliases?teamId=$vTm" -Headers $vH -Method POST -Body (@{alias="intelliwatch-iw.vercel.app"}|ConvertTo-Json) | Out-Null
        }
    }
    Write-Host " done" -ForegroundColor Green
} else {
    Write-Host " skipped (no VERCEL_TOKEN)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host " DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host " Frontend : https://intelliwatch-iw.vercel.app"
Write-Host " Backend  : $serviceUrl"
Write-Host " API Docs : $serviceUrl/docs"
Write-Host "======================================"
