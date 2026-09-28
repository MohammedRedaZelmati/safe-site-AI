[CmdletBinding()]
param(
    [string]$RunId = ("e2e-" + (Get-Date -Format "yyyyMMdd-HHmmss")),
    [string]$CameraId = ("camera-e2e-" + (Get-Date -Format "HHmmss")),
    [ValidateRange(1, 30)]
    [int]$FrameCount = 10,
    [switch]$KeepDatabaseEvidence
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

$normalizedRunId = $RunId.ToLowerInvariant()
$baseOccurredAt = (Get-Date).ToUniversalTime().ToString("o")
$runDirectory = Join-Path $projectRoot "data/streaming/demo-$normalizedRunId"
$pipelineSummaryPath = Join-Path $runDirectory "run-summary.json"
$reportPath = Join-Path $projectRoot "data/final/e2e-streaming-$normalizedRunId.json"
$candidateTopic = "safesite.e2e.$normalizedRunId.candidate"
$deadLetterTopic = "safesite.e2e.$normalizedRunId.candidate.dlq"
$deliveryFirstDirectory = "/data/streaming/demo-$normalizedRunId/e2e-delivery-first"
$deliveryReplayDirectory = "/data/streaming/demo-$normalizedRunId/e2e-delivery-replay"
$hostDeliveryFirstSummary = Join-Path $runDirectory "e2e-delivery-first/summary.json"
$hostDeliveryReplaySummary = Join-Path $runDirectory "e2e-delivery-replay/summary.json"
$databaseRowCreated = $false
$startedAt = Get-Date

$report = [ordered]@{
    schema_version = 1
    test_name = "SafeSite full streaming pipeline end-to-end"
    run_id = $normalizedRunId
    camera_id = $CameraId
    started_at = $startedAt.ToUniversalTime().ToString("o")
    status = "running"
    scope = @(
        "video fixture and OpenCV frame sampling",
        "MinIO Bronze object storage",
        "Kafka raw, PPE, and tracking topics",
        "YOLO PPE inference",
        "ByteTrack and temporal rules",
        "candidate Kafka delivery to FastAPI",
        "PostgreSQL persistence",
        "database-level duplicate protection"
    )
    assertions = @()
    artifacts = [ordered]@{}
}

function Save-Report {
    $parent = Split-Path -Parent $reportPath
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $report | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $reportPath -Encoding utf8
}

function Add-Assertion {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [bool]$Passed,
        [Parameter(Mandatory)] [string]$Expected,
        [Parameter(Mandatory)] [string]$Actual
    )
    $report.assertions += [ordered]@{
        name = $Name
        passed = $Passed
        expected = $Expected
        actual = $Actual
    }
    $label = if ($Passed) { "PASS" } else { "FAIL" }
    $color = if ($Passed) { "Green" } else { "Red" }
    Write-Host ("[{0}] {1} | expected: {2} | actual: {3}" -f $label, $Name, $Expected, $Actual) -ForegroundColor $color
    Save-Report
    if (-not $Passed) {
        throw "Assertion failed: $Name"
    }
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

function Test-DockerEngineAvailability {
    $probeDirectory = Join-Path $projectRoot "data/final/docker-probe"
    New-Item -ItemType Directory -Force -Path $probeDirectory | Out-Null
    $probeId = [Guid]::NewGuid().ToString("N")
    $standardOutput = Join-Path $probeDirectory "$probeId.out.txt"
    $standardError = Join-Path $probeDirectory "$probeId.err.txt"
    try {
        $process = Start-Process -FilePath "docker.exe" `
            -ArgumentList @("info", "--format", "{{.ServerVersion}}") `
            -NoNewWindow `
            -PassThru `
            -RedirectStandardOutput $standardOutput `
            -RedirectStandardError $standardError
        if (-not $process.WaitForExit(20000)) {
            $process.Kill()
            $process.WaitForExit()
            throw "Docker Engine did not answer within 20 seconds. Restart Docker Desktop and retry."
        }
        $process.Refresh()
        $outputText = ""
        if (Test-Path $standardOutput) {
            $rawOutputText = Get-Content -Raw $standardOutput
            if ($null -ne $rawOutputText) {
                $outputText = $rawOutputText.Trim()
            }
        }
        $errorText = ""
        if (Test-Path $standardError) {
            $rawErrorText = Get-Content -Raw $standardError
            if ($null -ne $rawErrorText) {
                $errorText = $rawErrorText.Trim()
            }
        }
        if ([string]::IsNullOrWhiteSpace($outputText)) {
            throw "Docker Engine is not reachable: $errorText"
        }
    } finally {
        Remove-Item -LiteralPath $standardOutput, $standardError -Force -ErrorAction SilentlyContinue
    }
}

function Get-DatabaseCount {
    $value = & docker compose exec -T postgres psql -U safesite -d safesite -tAc `
        "SELECT COUNT(*) FROM violations WHERE camera_id = '$CameraId';"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not count PostgreSQL evidence rows."
    }
    return [int]$value.Trim()
}

function Get-MinioObjectCount {
    $prefix = "runs/$normalizedRunId/raw-frames/$CameraId/"
    $python = "from minio import Minio; import os; c=Minio('minio:9000',access_key=os.getenv('MINIO_ACCESS_KEY','safesite'),secret_key=os.getenv('MINIO_SECRET_KEY','safesite_dev_password'),secure=False); print(sum(1 for _ in c.list_objects('safesite-bronze',prefix='$prefix',recursive=True)))"
    $output = & docker compose --profile tools run --rm --no-deps ingestion python -c $python
    if ($LASTEXITCODE -ne 0) {
        throw "Could not verify MinIO Bronze objects."
    }
    $numericLine = @($output | Where-Object { $_ -match '^\s*\d+\s*$' })[-1]
    return [int]$numericLine.Trim()
}

function New-KafkaTopic {
    param([Parameter(Mandatory)] [string]$Topic)
    Invoke-DockerChecked -Arguments @(
        "compose", "exec", "-T", "kafka",
        "/opt/kafka/bin/kafka-topics.sh",
        "--bootstrap-server", "localhost:9092",
        "--create", "--if-not-exists",
        "--topic", $Topic,
        "--partitions", "3",
        "--replication-factor", "1"
    ) -FailureMessage "Could not create Kafka topic $Topic"
}

function Invoke-CandidateConsumer {
    param(
        [Parameter(Mandatory)] [string]$GroupId,
        [Parameter(Mandatory)] [string]$OutputDirectory
    )
    Invoke-DockerChecked -Arguments @(
        "compose", "--profile", "tools", "run", "--rm", "ingestion",
        "python", "-m", "app.consume_candidate_events",
        "--topic", $candidateTopic,
        "--dead-letter-topic", $deadLetterTopic,
        "--group-id", $GroupId,
        "--output-dir", $OutputDirectory,
        "--base-occurred-at", $baseOccurredAt,
        "--api-url", "http://api:8000",
        "--max-messages", "1",
        "--idle-timeout-seconds", "30",
        "--max-attempts", "3",
        "--retry-backoff-seconds", "1"
    ) -FailureMessage "Candidate consumer failed for group $GroupId"
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " SAFESITE AI - FULL STREAMING END-TO-END TEST" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Run ID   : $normalizedRunId"
Write-Host "Camera   : $CameraId"
Write-Host "Frames   : $FrameCount"
Write-Host "Report   : $reportPath"
Write-Host ""
Save-Report

try {
    Write-Host "[PHASE 1] Real streaming pipeline" -ForegroundColor Yellow
    Test-DockerEngineAvailability
    Add-Assertion -Name "Docker Engine" -Passed $true -Expected "reachable" -Actual "reachable"

    & (Join-Path $PSScriptRoot "run_streaming_demo.ps1") `
        -RunId $normalizedRunId `
        -CameraId $CameraId `
        -BaseOccurredAt $baseOccurredAt `
        -FrameCount $FrameCount

    $pipelineSummary = Get-Content -Raw -LiteralPath $pipelineSummaryPath | ConvertFrom-Json
    Add-Assertion -Name "Pipeline completion" -Passed ($pipelineSummary.status -eq "completed") -Expected "completed" -Actual ([string]$pipelineSummary.status)
    Add-Assertion -Name "API and database health" -Passed (($pipelineSummary.api_health.status -eq "healthy") -and ($pipelineSummary.api_health.database -eq "reachable")) -Expected "healthy / reachable" -Actual ("{0} / {1}" -f $pipelineSummary.api_health.status, $pipelineSummary.api_health.database)
    Add-Assertion -Name "Kafka raw frames" -Passed ([int]$pipelineSummary.topic_message_counts.raw -eq $FrameCount) -Expected "$FrameCount" -Actual ([string]$pipelineSummary.topic_message_counts.raw)
    Add-Assertion -Name "YOLO PPE output events" -Passed ([int]$pipelineSummary.topic_message_counts.ppe -eq $FrameCount) -Expected "$FrameCount" -Actual ([string]$pipelineSummary.topic_message_counts.ppe)
    Add-Assertion -Name "Tracking output events" -Passed ([int]$pipelineSummary.topic_message_counts.tracks -eq $FrameCount) -Expected "$FrameCount" -Actual ([string]$pipelineSummary.topic_message_counts.tracks)
    Add-Assertion -Name "Tracking frames processed" -Passed ([int]$pipelineSummary.measurements.tracking_frames_processed -eq $FrameCount) -Expected "$FrameCount" -Actual ([string]$pipelineSummary.measurements.tracking_frames_processed)

    $minioCount = Get-MinioObjectCount
    Add-Assertion -Name "MinIO Bronze objects" -Passed ($minioCount -eq $FrameCount) -Expected "$FrameCount" -Actual "$minioCount"

    Write-Host ""
    Write-Host "[PHASE 2] Deterministic violation delivery probe" -ForegroundColor Yellow
    New-KafkaTopic -Topic $candidateTopic
    New-KafkaTopic -Topic $deadLetterTopic

    $eventSeed = "safesite-e2e|$normalizedRunId|candidate-1"
    $eventBytes = [System.Text.Encoding]::UTF8.GetBytes($eventSeed)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $eventHash = $sha256.ComputeHash($eventBytes)
    } finally {
        $sha256.Dispose()
    }
    $eventId = [System.BitConverter]::ToString($eventHash).Replace("-", "").ToLowerInvariant()
    $frameUri = "s3://safesite-bronze/runs/$normalizedRunId/raw-frames/$CameraId/frame_000000_t000000000ms.jpg"
    $candidate = [ordered]@{
        schema_version = 1
        event_id = $eventId
        camera_id = $CameraId
        track_id = 9001
        violation_type = "NO_HELMET"
        video_timestamp_ms = 0
        confidence = 0.99
        frame_uri = $frameUri
    }
    $candidateJson = $candidate | ConvertTo-Json -Compress
    $kafkaLine = "$CameraId|$candidateJson"

    $databaseCountBefore = Get-DatabaseCount
    $kafkaLine | & docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh `
        --bootstrap-server localhost:9092 `
        --topic $candidateTopic `
        --property parse.key=true `
        --property "key.separator=|"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not publish the deterministic candidate to Kafka."
    }
    Add-Assertion -Name "Candidate published to Kafka" -Passed $true -Expected "1 message" -Actual "1 message"

    Invoke-CandidateConsumer -GroupId "$normalizedRunId-api-first" -OutputDirectory $deliveryFirstDirectory
    $firstDelivery = Get-Content -Raw -LiteralPath $hostDeliveryFirstSummary | ConvertFrom-Json
    $firstPublished = if ($null -ne $firstDelivery.status_counts.published) { [int]$firstDelivery.status_counts.published } else { 0 }
    Add-Assertion -Name "Kafka to FastAPI delivery" -Passed ($firstPublished -eq 1) -Expected "published=1 (HTTP 201)" -Actual ("published={0}" -f $firstPublished)

    $databaseCountAfterFirst = Get-DatabaseCount
    $databaseRowCreated = $databaseCountAfterFirst -gt $databaseCountBefore
    Add-Assertion -Name "PostgreSQL persistence" -Passed ($databaseCountAfterFirst -eq ($databaseCountBefore + 1)) -Expected ([string]($databaseCountBefore + 1)) -Actual ([string]$databaseCountAfterFirst)

    $encodedCamera = [Uri]::EscapeDataString($CameraId)
    $apiRows = @(Invoke-RestMethod -Uri "http://localhost:8000/violations?camera_id=$encodedCamera&limit=10" -TimeoutSec 10)
    $matchingRows = @($apiRows | Where-Object { $_.camera_id -eq $CameraId -and $_.track_id -eq 9001 -and $_.violation_type -eq "NO_HELMET" })
    Add-Assertion -Name "FastAPI read-back" -Passed ($matchingRows.Count -eq 1) -Expected "1 matching violation" -Actual ("{0} matching violation(s)" -f $matchingRows.Count)

    Write-Host ""
    Write-Host "[PHASE 3] Idempotent replay" -ForegroundColor Yellow
    Invoke-CandidateConsumer -GroupId "$normalizedRunId-api-replay" -OutputDirectory $deliveryReplayDirectory
    $replayDelivery = Get-Content -Raw -LiteralPath $hostDeliveryReplaySummary | ConvertFrom-Json
    $skippedDuplicate = if ($null -ne $replayDelivery.status_counts.skipped_duplicate) { [int]$replayDelivery.status_counts.skipped_duplicate } else { 0 }
    Add-Assertion -Name "Duplicate replay response" -Passed ($skippedDuplicate -eq 1) -Expected "skipped_duplicate=1 (HTTP 200)" -Actual ("skipped_duplicate={0}" -f $skippedDuplicate)

    $databaseCountAfterReplay = Get-DatabaseCount
    Add-Assertion -Name "No duplicate database row" -Passed ($databaseCountAfterReplay -eq $databaseCountAfterFirst) -Expected ([string]$databaseCountAfterFirst) -Actual ([string]$databaseCountAfterReplay)

    $report.status = "passed"
    $report.completed_at = (Get-Date).ToUniversalTime().ToString("o")
    $report.duration_seconds = [Math]::Round(((Get-Date) - $startedAt).TotalSeconds, 2)
    $report.artifacts.pipeline_summary = $pipelineSummaryPath
    $report.artifacts.first_delivery_summary = $hostDeliveryFirstSummary
    $report.artifacts.replay_delivery_summary = $hostDeliveryReplaySummary
    $report.artifacts.minio_evidence_uri = $frameUri
    $report.artifacts.api_evidence = $matchingRows[0]
    $report.notes = @(
        "Phase 1 uses the real CV streaming path and checks one output event per requested frame.",
        "Phase 2 uses a deterministic known-positive integration fixture because model accuracy is a separate evaluation concern.",
        "Phase 3 replays the same Kafka event with a fresh consumer group and proves the database row is not duplicated."
    )
    Save-Report

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " E2E RESULT: PASSED" -ForegroundColor Green
    Write-Host " Assertions : $($report.assertions.Count) passed, 0 failed" -ForegroundColor Green
    Write-Host " Duration   : $($report.duration_seconds) seconds" -ForegroundColor Green
    Write-Host " Report     : $reportPath" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} catch {
    $report.status = "failed"
    $report.completed_at = (Get-Date).ToUniversalTime().ToString("o")
    $report.duration_seconds = [Math]::Round(((Get-Date) - $startedAt).TotalSeconds, 2)
    $report.error = $_.Exception.Message
    Save-Report
    Write-Host ""
    Write-Host "E2E RESULT: FAILED - $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Report: $reportPath" -ForegroundColor Red
    throw
} finally {
    if ($databaseRowCreated -and -not $KeepDatabaseEvidence) {
        & docker compose exec -T postgres psql -U safesite -d safesite -c `
            "DELETE FROM violations WHERE camera_id = '$CameraId';" | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Cleanup: removed the isolated PostgreSQL test row." -ForegroundColor DarkGray
        } else {
            Write-Warning "Cleanup could not remove the isolated PostgreSQL test row."
        }
    }
}
