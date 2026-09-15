# Lesson 29: MLflow Experiments and Model Registry

## Goal

Keep a trustworthy history of model experiments and place one exact model version
in a registry without pretending that it is ready for production.

## The problem MLflow solves

Training creates many outputs: settings, metrics, charts, dataset information, and
weights. If these are kept in unrelated folders, it becomes difficult to answer:

- Which settings produced this model?
- Which dataset and weight file were used?
- Is this result better than an older run?
- Which exact model should another service test?

MLflow stores these facts together as one **run** inside an **experiment**.

```text
experiment: SafeSite-PPE-Experiments
             |
             +-- run A: settings + metrics + artifacts
             +-- run B: settings + metrics + artifacts
             +-- run C: settings + metrics + artifacts
```

## Five important words

### Experiment

A named group of related runs. Our experiment is `SafeSite-PPE-Experiments`.

### Run

One recorded attempt. A run has an ID, a status, parameters, metrics, tags, and
artifacts. Block 29 records the already-trained ten-epoch baseline; it does not
train it again.

### Parameter

A setting chosen before training, such as `epochs=10`, `image_size=320`, or
`batch_size=8`.

### Metric

A measured result, such as precision, recall, or mAP. Parameters are inputs;
metrics are results.

### Artifact

A file connected to the run, such as a chart, evaluation JSON, dataset audit, or
model weight.

## Two storage locations

MLflow separates structured metadata from large files:

```text
SQLite backend store                local artifact store
--------------------                --------------------
run IDs and status                  charts
parameters                          JSON reports
metrics                             dataset config
model versions                      best.pt
aliases
```

SQLite is practical for learning on one computer. A shared production deployment
would normally use a network database such as PostgreSQL and shared object storage
instead of one local folder.

## Model registry

The registry gives a model a stable name and immutable numbered versions:

```text
SafeSite-PPE-Detector
        |
        +-- version 1
                 |
                 +-- alias: candidate
```

An alias is a readable pointer. Code can request `candidate` instead of manually
typing version `1`. Later, the alias can move to a better version without changing
the consumer's code.

We intentionally do **not** create a `champion` alias. The current model has weak
violation recall, so calling it the production champion would be dishonest.

## How the model is packaged

`safesite_yolo_pyfunc.py` defines how MLflow loads the packaged YOLO weight and
turns image paths into structured detections. The logger stores that model code,
the exact `best.pt` weight, and pinned runtime requirements together.

This is called model-from-code. It avoids saving a fragile copy of a live Python
object and makes the model's loading behavior inspectable.

## Run it locally without Docker

Create the environment once:

```powershell
python -m venv services/mlops/.venv
services/mlops/.venv/Scripts/python.exe -m pip install -r services/mlops/requirements.txt
```

Record and register the baseline:

```powershell
services/mlops/.venv/Scripts/python.exe services/mlops/log_ppe_experiment.py
```

Open the tracking UI:

```powershell
.\scripts\start_mlflow_ui.ps1
```

Then visit http://127.0.0.1:5000. Press `Ctrl+C` to stop only the MLflow server.

## Verified result

The local proof created:

```text
experiment:              SafeSite-PPE-Experiments
run status:              FINISHED
parameters:              12
metrics:                 54
run artifacts:            9
registered model:        SafeSite-PPE-Detector
registered version:      1
alias:                   candidate
validation status:       experimental
SQLite integrity:        ok
MLflow UI HTTP status:   200
```

The run contains seven training artifacts and two dataset artifacts. The registry
entry exposes the MLflow PyFunc flavor and points to the exact packaged weight.

## Expected warning

The small logging environment installs MLflow but not Ultralytics. MLflow therefore
warns that the packaged model requires `ultralytics==8.4.107`. That is expected:
logging does not run YOLO inference, while an environment that loads this model
must install the pinned inference requirements.

## Honest boundary

This block proves experiment traceability, local storage, model packaging, and
registration. It does not prove model accuracy, production readiness, remote
collaboration, or deployment. The model remains an experimental candidate.

## Explain it aloud

Why is a registered model version not automatically a production-ready model?
