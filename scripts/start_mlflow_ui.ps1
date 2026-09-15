param(
    [ValidateRange(1, 65535)]
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$mlflowExecutable = Join-Path $projectRoot "services\mlops\.venv\Scripts\mlflow.exe"
$databasePath = (Join-Path $projectRoot "data\mlflow\mlflow.db").Replace("\", "/")
$artifactPath = (Join-Path $projectRoot "data\mlflow\artifacts").Replace("\", "/")

if (-not (Test-Path -LiteralPath $mlflowExecutable -PathType Leaf)) {
    throw "MLflow is not installed. Follow services/mlops/README.md first."
}

& $mlflowExecutable server `
    --backend-store-uri "sqlite:///$databasePath" `
    --default-artifact-root "file:///$artifactPath" `
    --host 127.0.0.1 `
    --port $Port
