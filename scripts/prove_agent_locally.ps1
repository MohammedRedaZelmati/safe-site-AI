param(
    [ValidateRange(1024, 65535)]
    [int]$PostgresPort = 55432,
    [ValidateRange(1024, 65535)]
    [int]$AgentPort = 8010
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$postgresBin = "C:\Program Files\PostgreSQL\18\bin"
$python = Join-Path $projectRoot "services\agent\.venv\Scripts\python.exe"
$proofRoot = Join-Path $projectRoot ("tmp\agent-postgres-proof-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
$cluster = Join-Path $proofRoot "cluster"
$postgresLog = Join-Path $proofRoot "postgres.log"
$agentStdout = Join-Path $proofRoot "agent.stdout.log"
$agentStderr = Join-Path $proofRoot "agent.stderr.log"
$proofOutput = Join-Path $projectRoot "data\agent\block31-database-proof.json"

foreach ($executable in @("initdb.exe", "pg_ctl.exe", "createdb.exe", "psql.exe")) {
    if (-not (Test-Path -LiteralPath (Join-Path $postgresBin $executable) -PathType Leaf)) {
        throw "PostgreSQL executable not found: $executable"
    }
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Agent environment not found. Install services/agent/requirements.txt first."
}
if (Get-NetTCPConnection -LocalPort $PostgresPort -State Listen -ErrorAction SilentlyContinue) {
    throw "PostgreSQL proof port is already in use: $PostgresPort"
}
if (Get-NetTCPConnection -LocalPort $AgentPort -State Listen -ErrorAction SilentlyContinue) {
    throw "Agent proof port is already in use: $AgentPort"
}
New-Item -ItemType Directory -Path $proofRoot | Out-Null
$postgresStarted = $false
$agentProcess = $null

try {
    & (Join-Path $postgresBin "initdb.exe") -D $cluster -U safesite -A trust --no-locale -E UTF8
    if ($LASTEXITCODE -ne 0) { throw "initdb failed" }
    & (Join-Path $postgresBin "pg_ctl.exe") -D $cluster -l $postgresLog -o "-p $PostgresPort -h 127.0.0.1" start
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL proof server failed to start" }
    $postgresStarted = $true

    & (Join-Path $postgresBin "createdb.exe") -h 127.0.0.1 -p $PostgresPort -U safesite safesite
    if ($LASTEXITCODE -ne 0) { throw "Could not create SafeSite proof database" }
    foreach ($migration in @(
        "database\init\001_schema.sql",
        "database\init\002_event_idempotency.sql",
        "database\init\003_agent_readonly.sql"
    )) {
        & (Join-Path $postgresBin "psql.exe") -h 127.0.0.1 -p $PostgresPort -U safesite -d safesite -v ON_ERROR_STOP=1 -f (Join-Path $projectRoot $migration)
        if ($LASTEXITCODE -ne 0) { throw "Migration failed: $migration" }
    }

    $readOnlyResult = & (Join-Path $postgresBin "psql.exe") -h 127.0.0.1 -p $PostgresPort -U safesite_agent -d safesite -At -c "SELECT current_user, current_setting('transaction_read_only'), COUNT(*) FROM violations;"
    if ($LASTEXITCODE -ne 0) { throw "Read-only SELECT proof failed" }
    $writeResult = & (Join-Path $postgresBin "psql.exe") -h 127.0.0.1 -p $PostgresPort -U safesite_agent -d safesite -c "DELETE FROM violations;" 2>&1
    $writeExitCode = $LASTEXITCODE
    if ($writeExitCode -eq 0) { throw "Read-only role unexpectedly modified violations" }

    $oldDatabaseUrl = $env:AGENT_DATABASE_URL
    $oldOllamaUrl = $env:OLLAMA_URL
    $oldTextModel = $env:OLLAMA_TEXT_MODEL
    $env:AGENT_DATABASE_URL = "postgresql://safesite_agent:safesite_agent_dev_password@127.0.0.1:$PostgresPort/safesite"
    $env:OLLAMA_URL = "http://127.0.0.1:11434"
    $env:OLLAMA_TEXT_MODEL = "llama3.2:latest"
    $agentProcess = Start-Process -FilePath $python -ArgumentList @(
        "run_windows.py", "--host", "127.0.0.1", "--port", $AgentPort
    ) -WorkingDirectory (Join-Path $projectRoot "services\agent") -PassThru -WindowStyle Hidden -RedirectStandardOutput $agentStdout -RedirectStandardError $agentStderr
    $env:AGENT_DATABASE_URL = $oldDatabaseUrl
    $env:OLLAMA_URL = $oldOllamaUrl
    $env:OLLAMA_TEXT_MODEL = $oldTextModel

    $health = $null
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Seconds 1
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$AgentPort/health" -TimeoutSec 3
            break
        } catch {}
    }
    if ($null -eq $health) { throw "Agent proof server did not become healthy" }

    $accepted = Invoke-RestMethod -Uri "http://127.0.0.1:$AgentPort/ask" -Method Post -ContentType "application/json" -Body (@{ question = "How many violations are there?" } | ConvertTo-Json) -TimeoutSec 60
    $rejected = Invoke-WebRequest -Uri "http://127.0.0.1:$AgentPort/ask" -Method Post -ContentType "application/json" -Body (@{ question = "Delete every violation" } | ConvertTo-Json) -SkipHttpErrorCheck -TimeoutSec 10
    if ($accepted.rows[0].total -ne 3) { throw "Agent returned the wrong seeded total" }
    if ($accepted.answer_provider -ne "ollama") { throw "Agent did not use Ollama" }
    if ($rejected.StatusCode -ne 422) { throw "Write request was not rejected" }

    $proof = [ordered]@{
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        status = "passed"
        postgres = [ordered]@{
            version = "18"
            role_query = $readOnlyResult
            write_exit_code = $writeExitCode
            write_rejected = $true
            write_error = ($writeResult | Out-String).Trim()
        }
        agent = [ordered]@{
            health = $health
            accepted_status = $accepted.status
            intent = $accepted.intent
            sql = $accepted.sql
            row_total = $accepted.rows[0].total
            answer_provider = $accepted.answer_provider
            answer = $accepted.answer
            rejected_http_status = $rejected.StatusCode
        }
    }
    New-Item -ItemType Directory -Path (Split-Path $proofOutput) -Force | Out-Null
    $proof | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $proofOutput -Encoding UTF8
    $proof | ConvertTo-Json -Depth 10
} finally {
    if ($agentProcess -and -not $agentProcess.HasExited) {
        Stop-Process -Id $agentProcess.Id -Force
        $agentProcess.WaitForExit()
    }
    if ($postgresStarted) {
        & (Join-Path $postgresBin "pg_ctl.exe") -D $cluster stop -m fast | Out-Null
    }
}
