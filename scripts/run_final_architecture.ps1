param(
    [switch]$SkipStreaming,
    [switch]$IncludeAirflow,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) {
    $docker = $dockerCommand.Source
} else {
    $knownDocker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (-not (Test-Path -LiteralPath $knownDocker -PathType Leaf)) {
        throw "Docker CLI was not found. Start or install Docker Desktop first."
    }
    $docker = $knownDocker
}

function Invoke-Compose {
    param([string[]]$Arguments)
    & $docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed: $($Arguments -join ' ')"
    }
}

$build = @()
if (-not $SkipBuild) {
    $build = @("--build")
}

Write-Host "[1/6] Starting PostgreSQL, FastAPI, Kafka, and MinIO..."
Invoke-Compose (@("up", "-d") + $build + @("postgres", "api", "kafka", "minio"))

Write-Host "Creating Kafka topics..."
$topics = @(
    "safesite.frames.raw",
    "safesite.ppe.detections",
    "safesite.tracks",
    "safesite.candidate-violations",
    "safesite.candidate-violations.dlq"
)
foreach ($topic in $topics) {
    Invoke-Compose @(
        "exec", "-T", "kafka", "/opt/kafka/bin/kafka-topics.sh",
        "--bootstrap-server", "kafka:9092",
        "--create", "--if-not-exists",
        "--topic", $topic,
        "--partitions", "3",
        "--replication-factor", "1"
    )
}

Write-Host "[2/6] Applying idempotency and read-only-agent migrations..."
foreach ($migration in @("database/init/002_event_idempotency.sql", "database/init/003_agent_readonly.sql")) {
    Get-Content -Raw $migration | & $docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U safesite -d safesite
    if ($LASTEXITCODE -ne 0) {
        throw "Migration failed: $migration"
    }
}

Write-Host "[3/6] Starting the grounded agent, dashboard, and MLflow..."
$profiles = @("--profile", "agent", "--profile", "ui", "--profile", "mlops")
$services = @("agent", "dashboard", "mlflow")
if (-not $SkipStreaming) {
    $profiles += @("--profile", "streaming")
    $services += @(
        "camera-ingestion-worker",
        "ppe-inference-worker",
        "tracking-worker",
        "candidate-api-worker",
        "stream-monitor"
    )
}
Invoke-Compose ($profiles + @("up", "-d") + $build + $services)

Write-Host "[4/6] Creating the drift report..."
Invoke-Compose (@("--profile", "monitoring", "run", "--rm", "drift-monitor"))
Invoke-Compose (@("--profile", "monitoring", "run", "--rm", "event-quality"))

if ($IncludeAirflow) {
    Write-Host "[5/6] Starting Airflow..."
    Invoke-Compose (@("--profile", "orchestration", "up", "-d", "airflow"))
} else {
    Write-Host "[5/6] Airflow is implemented but not started. Use -IncludeAirflow for the heavy local service."
}

Write-Host "[6/6] Waiting for HTTP services..."
$checks = @(
    @{ Name = "FastAPI"; Url = "http://localhost:8000/health" },
    @{ Name = "Agent"; Url = "http://localhost:8010/health" },
    @{ Name = "Dashboard"; Url = "http://localhost:8502/_stcore/health" },
    @{ Name = "MLflow"; Url = "http://localhost:5000" }
)
foreach ($check in $checks) {
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $check.Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {}
        Start-Sleep -Seconds 2
    }
    if (-not $ready) {
        throw "$($check.Name) did not become healthy: $($check.Url)"
    }
    Write-Host "$($check.Name): healthy"
}

Write-Host "SafeSite final architecture is running."
Write-Host "Dashboard: http://localhost:8502"
Write-Host "API docs:  http://localhost:8000/docs"
Write-Host "Agent docs: http://localhost:8010/docs"
Write-Host "MLflow:     http://localhost:5000"
if ($IncludeAirflow) {
    Write-Host "Airflow:    http://localhost:8080"
}
