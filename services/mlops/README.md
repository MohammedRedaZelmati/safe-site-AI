# SafeSite MLflow

This local MLOps service records the existing PPE baseline without retraining it.
It uses SQLite for experiment and registry metadata and the local filesystem for
artifacts. No Docker service is required.

## What is recorded

- training parameters and environment;
- final training, overall evaluation, and per-class metrics;
- dataset archive, config, and model-weight SHA256 fingerprints;
- result tables, plots, confusion matrices, configuration, and audit files;
- a custom MLflow PyFunc package containing the verified YOLO weights;
- a registered model version with the `candidate` alias.

The version is deliberately tagged `experimental`. It is not assigned a
`champion` alias because the current violation-class recall is not production-ready.

## Local setup

```powershell
python -m venv services\mlops\.venv
services\mlops\.venv\Scripts\python.exe -m pip install -r services\mlops\requirements.txt
```

## Log the baseline

```powershell
services\mlops\.venv\Scripts\python.exe services\mlops\log_ppe_experiment.py `
  --training-dir data\training\ppe-baseline-e10-full-img320 `
  --dataset-config data\datasets\construction-ppe\data.yaml `
  --dataset-audit data\datasets\reports\construction-ppe-audit.json
```

The command writes `data/mlflow/mlflow.db`, local artifacts, and
`data/mlflow/block29-proof.json`.

## Open the UI

```powershell
.\scripts\start_mlflow_ui.ps1
```

Then open `http://127.0.0.1:5000`. Stop the local server with `Ctrl+C`.

For a shared production deployment, replace SQLite with PostgreSQL and local
artifacts with protected object storage.

## Compare runs

```powershell
services\mlops\.venv\Scripts\python.exe services\mlops\compare_ppe_runs.py `
  data\training\ppe-smoke-e1-f010-img320 `
  data\training\ppe-baseline-e10-full-img320
```

The comparison selects by mAP50-95, then recall, then precision. Winning this
comparison makes a run an experimental candidate, not a production model.
