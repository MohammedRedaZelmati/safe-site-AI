[CmdletBinding()]
param(
    [string]$RunId = (Get-Date -Format "yyyyMMdd-HHmmss"),
    [string]$CameraId = "camera-stream-demo",
    [string]$SourceImage = "data/datasets/construction-ppe/images/test/image1145.jpg",
    [string]$BaseOccurredAt = (Get-Date).ToUniversalTime().ToString("o"),
    [int]$FrameCount = 30,
    [switch]$SendCandidates,
    [switch]$StartDashboard,
    [int]$DashboardPort = 8502
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if ($RunId -notmatch "^[a-zA-Z0-9][a-zA-Z0-9-]{2,40}$") {
    throw "RunId must contain 3-41 letters, digits, or hyphens."
}
if ($CameraId -notmatch "^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$") {
    throw "CameraId must contain 1-64 safe identifier characters."
}
if ($FrameCount -lt 1 -or $FrameCount -gt 30) {
    throw "FrameCount must be between 1 and the fixture's 30 sampled frames."
}
if ($DashboardPort -lt 1 -or $DashboardPort -gt 65535) {
    throw "DashboardPort must be between 1 and 65535."
}
try {
    $baseTime = [DateTimeOffset]::Parse($BaseOccurredAt)
} catch {
    throw "BaseOccurredAt must be a valid ISO 8601 timestamp with a timezone."
}

$hostSourceImage = Join-Path $projectRoot $SourceImage
$hostTrackingModel = Join-Path $projectRoot "data/models/yolo26n.pt"
$hostPpeModel = Join-Path $projectRoot "data/training/ppe-baseline-e10-full-img320/weights/best.pt"
foreach ($requiredFile in @($hostSourceImage, $hostTrackingModel, $hostPpeModel)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required file does not exist: $requiredFile"
    }
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

$normalizedRunId = $RunId.ToLowerInvariant()
$topicPrefix = "safesite.demo.$normalizedRunId"
$topics = [ordered]@{
    raw = "$topicPrefix.frames.raw"
    ppe = "$topicPrefix.ppe.detections"
    tracks = "$topicPrefix.tracks"
    candidates = "$topicPrefix.candidate-violations"
    dead_letter = "$topicPrefix.candidate-violations.dlq"
}
$hostRunDirectory = Join-Path $projectRoot "data/streaming/demo-$normalizedRunId"
$containerRunDirectory = "/data/streaming/demo-$normalizedRunId"
$summaryPath = Join-Path $hostRunDirectory "run-summary.json"
if (Test-Path -LiteralPath $hostRunDirectory) {
    throw "Run directory already exists: $hostRunDirectory"
}
New-Item -ItemType Directory -Path $hostRunDirectory | Out-Null

$runSummary = [ordered]@{
    schema_version = 1
    run_id = $normalizedRunId
    status = "running"
    started_at = (Get-Date).ToUniversalTime().ToString("o")
    camera_id = $CameraId
    frame_count_requested = $FrameCount
    base_occurred_at = $baseTime.ToString("o")
    send_candidates = [bool]$SendCandidates
    topics = $topics
    stages = [ordered]@{}
}

function Save-RunSummary {
    $runSummary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $summaryPath -Encoding utf8
}

function Invoke-DockerChecked {
    param(
        [Parameter(Mandatory)] [string[]]$Arguments,
        [Parameter(Mandatory)] [string]$FailureMessage
    )
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (docker exit code $LASTEXITCODE)"
    }
}

function Get-TopicMessageCount {
    param([Parameter(Mandatory)] [string]$Topic)
    $offsetLines = & docker compose exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh `
        --bootstrap-server localhost:9092 --topic $Topic
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read offsets for topic $Topic"
    }
    $total = 0L
    foreach ($line in $offsetLines) {
        if ($line -match ":(-?\d+)$") {
            $offset = [long]$Matches[1]
            if ($offset -gt 0) { $total += $offset }
        }
    }
    return $total
}

try {
    Write-Host "[1/10] Starting Kafka, MinIO, PostgreSQL, and FastAPI..."
    Invoke-DockerChecked -Arguments @("compose", "up", "-d", "kafka", "minio", "postgres", "api") `
        -FailureMessage "Could not start infrastructure"
    $runSummary.stages.infrastructure = "healthy"
    Save-RunSummary

    Write-Host "[2/10] Applying the PostgreSQL idempotency migration..."
    Get-Content -Raw "database/init/002_event_idempotency.sql" |
        docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U safesite -d safesite
    if ($LASTEXITCODE -ne 0) { throw "Could not apply the database migration." }
    $runSummary.stages.database_migration = "applied"
    Save-RunSummary

    Write-Host "[3/10] Building the ingestion image..."
    Invoke-DockerChecked -Arguments @("compose", "--profile", "tools", "build", "ingestion") `
        -FailureMessage "Could not build the ingestion image"
    $runSummary.stages.ingestion_image = "built"
    Save-RunSummary

    Write-Host "[4/10] Creating isolated Kafka topics..."
    foreach ($topic in $topics.Values) {
        Invoke-DockerChecked -Arguments @(
            "compose", "exec", "-T", "kafka",
            "/opt/kafka/bin/kafka-topics.sh",
            "--bootstrap-server", "localhost:9092",
            "--create", "--if-not-exists",
            "--topic", $topic,
            "--partitions", "3",
            "--replication-factor", "1"
        ) -FailureMessage "Could not create topic $topic"
    }
    $runSummary.stages.kafka_topics = "created"
    Save-RunSummary

    Write-Host "[5/10] Generating and sampling the 30-frame fixture..."
    Invoke-DockerChecked -Arguments @(
        "compose", "--profile", "tools", "run", "--rm", "ingestion",
        "python", "-m", "app.generate_violation_fixture",
        "--source-image", $containerSourceImage,
        "--output-video", "$containerRunDirectory/source.mp4"
    ) -FailureMessage "Fixture generation failed"
    Invoke-DockerChecked -Arguments @(
        "compose", "--profile", "tools", "run", "--rm", "ingestion",
        "python", "-m", "app.sample_frames",
        "--input", "$containerRunDirectory/source.mp4",
        "--output-dir", "$containerRunDirectory/frames",
        "--target-fps", "5",
        "--camera-id", $CameraId
    ) -FailureMessage "Frame sampling failed"
    $runSummary.stages.frame_sampling = "completed"
    Save-RunSummary

    Write-Host "[6/10] Publishing frames to MinIO Bronze and Kafka..."
    Invoke-DockerChecked -Arguments @(
        "compose", "--profile", "tools", "run", "--rm", "ingestion",
        "python", "-m", "app.publish_frames",
        "--manifest", "$containerRunDirectory/frames/frames.jsonl",
        "--topic", $topics.raw,
        "--object-prefix", "runs/$normalizedRunId/raw-frames",
        "--limit", "$FrameCount"
    ) -FailureMessage "Frame publication failed"
    $runSummary.stages.bronze_publication = "completed"
    Save-RunSummary

    Write-Host "[7/10] Running streamed PPE inference into Silver..."
    Invoke-DockerChecked -Arguments @(
        "compose", "--profile", "tools", "run", "--rm", "ingestion",
        "python", "-m", "app.infer_frame_events",
        "--input-topic", $topics.raw,
        "--output-topic", $topics.ppe,
        "--group-id", "$normalizedRunId-ppe",
        "--output-dir", "$containerRunDirectory/ppe",
        "--model", "/data/training/ppe-baseline-e10-full-img320/weights/best.pt",
        "--confidence", "0.25",
        "--image-size", "320",
        "--device", "cpu",
        "--max-messages", "$FrameCount"
    ) -FailureMessage "Streamed PPE inference failed"
    $runSummary.stages.silver_inference = "completed"
    Save-RunSummary

    Write-Host "[8/10] Tracking workers, associating PPE, and writing Gold..."
    Invoke-DockerChecked -Arguments @(
        "compose", "--profile", "tools", "run", "--rm", "ingestion",
        "python", "-m", "app.process_ppe_stream",
        "--input-topic", $topics.ppe,
        "--track-topic", $topics.tracks,
        "--candidate-topic", $topics.candidates,
        "--group-id", "$normalizedRunId-tracking",
        "--output-dir", "$containerRunDirectory/tracking",
        "--tracking-model", "/data/models/yolo26n.pt",
        "--max-messages", "$FrameCount",
        "--tracking-confidence", "0.25",
        "--image-size", "640",
        "--device", "cpu",
        "--window-size", "5",
        "--evidence-threshold", "3",
        "--cooldown-ms", "10000",
        "--maximum-opposite-evidence", "0"
    ) -FailureMessage "Tracking and temporal processing failed"
    $runSummary.stages.gold_tracking = "completed"
    Save-RunSummary

    Write-Host "[9/10] Reviewing confirmed candidate count..."
    $candidateCount = Get-TopicMessageCount -Topic $topics.candidates
    if ($candidateCount -eq 0) {
        $candidateDelivery = "no_confirmed_candidates"
    } elseif (-not $SendCandidates) {
        $candidateDelivery = "pending_human_review"
    } else {
        Invoke-DockerChecked -Arguments @(
            "compose", "--profile", "tools", "run", "--rm", "ingestion",
            "python", "-m", "app.consume_candidate_events",
            "--topic", $topics.candidates,
            "--dead-letter-topic", $topics.dead_letter,
            "--group-id", "$normalizedRunId-api",
            "--output-dir", "$containerRunDirectory/api-delivery",
            "--base-occurred-at", $baseTime.ToString("o"),
            "--api-url", "http://api:8000",
            "--max-messages", "$candidateCount",
            "--max-attempts", "3",
            "--retry-backoff-seconds", "1"
        ) -FailureMessage "Candidate API delivery failed"
        $candidateDelivery = "sent_after_explicit_approval"
    }
    $runSummary.stages.candidate_delivery = $candidateDelivery
    Save-RunSummary

    Write-Host "[10/10] Verifying final checkpoints..."
    $apiHealth = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10
    $topicCounts = [ordered]@{}
    foreach ($entry in $topics.GetEnumerator()) {
        $topicCounts[$entry.Key] = Get-TopicMessageCount -Topic $entry.Value
    }
    $databaseCount = & docker compose exec -T postgres psql -U safesite -d safesite -tAc `
        "SELECT COUNT(*) FROM violations WHERE camera_id = '$CameraId';"
    if ($LASTEXITCODE -ne 0) { throw "Could not verify PostgreSQL." }

    $trackingSummary = Get-Content -Raw (Join-Path $hostRunDirectory "tracking/summary.json") | ConvertFrom-Json
    $runSummary.status = "completed"
    $runSummary.completed_at = (Get-Date).ToUniversalTime().ToString("o")
    $runSummary.api_health = $apiHealth
    $runSummary.topic_message_counts = $topicCounts
    $runSummary.database_rows_for_camera = [int]$databaseCount.Trim()
    $runSummary.measurements = [ordered]@{
        ppe_frames_processed = [int]$topicCounts.ppe
        tracking_frames_processed = [int]$trackingSummary.frames_processed
        unique_track_ids = @($trackingSummary.unique_track_ids).Count
        candidate_events = [int]$trackingSummary.candidate_event_count
        associated_class_counts = $trackingSummary.associated_class_counts
    }
    $runSummary.safety_conclusion = if ($candidateCount -eq 0) {
        "No direct temporal violation evidence was confirmed; this does not prove compliance."
    } elseif ($SendCandidates) {
        "Confirmed candidates were sent only because -SendCandidates was explicitly supplied."
    } else {
        "Confirmed candidates remain in Kafka pending human review."
    }
    Save-RunSummary

    if ($StartDashboard) {
        $env:SAFESITE_API_URL = "http://localhost:8000"
        $env:SAFESITE_DATA_ROOT = Join-Path $projectRoot "data"
        Start-Process -FilePath "python" -WindowStyle Hidden -ArgumentList @(
            "-m", "streamlit", "run", "services/dashboard/app.py",
            "--server.port", $DashboardPort, "--server.headless", "true"
        )
    }

    Write-Host ""
    Write-Host "SafeSite streaming demo completed."
    Write-Host "Run ID: $normalizedRunId"
    Write-Host "Summary: $summaryPath"
    Write-Host "Candidates: $candidateCount ($candidateDelivery)"
    Write-Host "API docs: http://localhost:8000/docs"
    if ($StartDashboard) { Write-Host "Dashboard: http://localhost:$DashboardPort" }
} catch {
    $runSummary.status = "failed"
    $runSummary.completed_at = (Get-Date).ToUniversalTime().ToString("o")
    $runSummary.error = $_.Exception.Message
    Save-RunSummary
    throw
}
