[CmdletBinding()]
param(
    [switch]$Send,
    [switch]$SkipDashboard,
    [string]$CameraId = "camera-mvp-01",
    [string]$SourceImage = "data/datasets/construction-ppe/images/test/image1145.jpg",
    [string]$BaseOccurredAt = (Get-Date).ToUniversalTime().ToString("o"),
    [int]$DashboardPort = 8502
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$hostRunDirectory = Join-Path $projectRoot "data/demo/mvp-$runId"
$containerRunDirectory = "/data/demo/mvp-$runId"
$hostSourceImage = Join-Path $projectRoot $SourceImage

if (-not (Test-Path -LiteralPath $hostSourceImage -PathType Leaf)) {
    throw "Missing fixture source: $hostSourceImage. Run scripts/download_construction_ppe_dataset.py first."
}
$projectRootFull = [System.IO.Path]::GetFullPath($projectRoot).TrimEnd("\") + "\"
$sourceImageFull = [System.IO.Path]::GetFullPath($hostSourceImage)
if (-not $sourceImageFull.StartsWith($projectRootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "SourceImage must be inside the project directory."
}
$relativeSourceImage = $sourceImageFull.Substring($projectRootFull.Length).Replace("\", "/")
if (-not $relativeSourceImage.StartsWith("data/")) {
    throw "SourceImage must be inside the project's data directory."
}
$containerSourceImage = "/data/" + $relativeSourceImage.Substring(5)

Write-Host "[1/9] Starting PostgreSQL and FastAPI..."
docker compose up -d postgres api
if ($LASTEXITCODE -ne 0) { throw "Could not start the backend." }

Write-Host "[2/9] Applying the idempotency migration..."
Get-Content -Raw "database/init/002_event_idempotency.sql" |
    docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U safesite -d safesite
if ($LASTEXITCODE -ne 0) { throw "Could not apply the database migration." }

Write-Host "[3/9] Building the ingestion tool image..."
docker compose --profile tools build ingestion
if ($LASTEXITCODE -ne 0) { throw "Could not build the ingestion image." }

Write-Host "[4/9] Creating the real-image video fixture..."
docker compose --profile tools run --rm ingestion python -m app.generate_violation_fixture `
    --source-image $containerSourceImage `
    --output-video "$containerRunDirectory/source.mp4"
if ($LASTEXITCODE -ne 0) { throw "Fixture generation failed." }

Write-Host "[5/9] Sampling five frames per second..."
docker compose --profile tools run --rm ingestion python -m app.sample_frames `
    --input "$containerRunDirectory/source.mp4" `
    --output-dir "$containerRunDirectory/frames" `
    --target-fps 5 --camera-id $CameraId
if ($LASTEXITCODE -ne 0) { throw "Frame sampling failed." }

Write-Host "[6/9] Tracking workers and detecting PPE..."
docker compose --profile tools run --rm ingestion python -m app.track_frames `
    --manifest "$containerRunDirectory/frames/frames.jsonl" `
    --output-dir "$containerRunDirectory/tracks" `
    --model /data/models/yolo26n.pt --confidence 0.25 --class-id 0
if ($LASTEXITCODE -ne 0) { throw "Person tracking failed." }
docker compose --profile tools run --rm ingestion python -m app.detect_frames `
    --manifest "$containerRunDirectory/frames/frames.jsonl" `
    --output-dir "$containerRunDirectory/ppe" `
    --model /data/training/ppe-baseline-e10-full-img320/weights/best.pt `
    --confidence 0.02 --image-size 640 --device cpu
if ($LASTEXITCODE -ne 0) { throw "PPE detection failed." }

Write-Host "[7/9] Associating PPE with tracked workers..."
docker compose --profile tools run --rm ingestion python -m app.associate_ppe_tracks `
    --tracks "$containerRunDirectory/tracks/tracks.jsonl" `
    --predictions "$containerRunDirectory/ppe/predictions.jsonl" `
    --output-dir "$containerRunDirectory/associations"
if ($LASTEXITCODE -ne 0) { throw "PPE association failed." }

Write-Host "[8/9] Applying the temporal violation rule..."
docker compose --profile tools run --rm ingestion python -m app.temporal_violations `
    --associations "$containerRunDirectory/associations/associations.jsonl" `
    --output-dir "$containerRunDirectory/temporal" `
    --window-size 5 --evidence-threshold 3 --cooldown-ms 10000 `
    --maximum-opposite-evidence 0
if ($LASTEXITCODE -ne 0) { throw "Temporal event generation failed." }

Write-Host "[9/9] Validating and publishing candidate events..."
$publishArguments = @(
    "compose", "--profile", "tools", "run", "--rm", "ingestion",
    "python", "-m", "app.publish_candidate_events",
    "--candidates", "$containerRunDirectory/temporal/candidate_events.jsonl",
    "--output-dir", "$containerRunDirectory/publish",
    "--base-occurred-at", $BaseOccurredAt,
    "--api-url", "http://api:8000"
)
if ($Send) { $publishArguments += "--send" }
& docker @publishArguments
if ($LASTEXITCODE -ne 0) { throw "Candidate publishing failed." }

if (-not $SkipDashboard) {
    $env:SAFESITE_API_URL = "http://localhost:8000"
    $env:SAFESITE_DATA_ROOT = Join-Path $projectRoot "data"
    Start-Process -FilePath "python" -WindowStyle Hidden -ArgumentList @(
        "-m", "streamlit", "run", "services/dashboard/app.py",
        "--server.port", $DashboardPort, "--server.headless", "true"
    )
}

$mode = if ($Send) { "SEND" } else { "DRY RUN" }
Write-Host ""
Write-Host "SafeSite MVP completed in $mode mode."
Write-Host "Run artifacts: $hostRunDirectory"
Write-Host "API docs: http://localhost:8000/docs"
if (-not $SkipDashboard) { Write-Host "Dashboard: http://localhost:$DashboardPort" }
Write-Host "Use -Send only after reviewing a dry run."
