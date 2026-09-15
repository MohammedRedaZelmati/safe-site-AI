# SafeSite AI MVP Demo

## What the MVP demonstrates

The completed MVP follows one video input through frame sampling, worker
tracking, PPE inference, spatial association, temporal confirmation, safe API
publishing, PostgreSQL storage, and a Streamlit dashboard.

## Prerequisites

- Docker Desktop is running.
- Python can run `streamlit`.
- The verified YOLO models and Construction-PPE dataset already exist in `data`.
- Ports `8000` and `8502` are available.

Install the dashboard dependency when needed:

```powershell
python -m pip install -r services/dashboard/requirements.txt
```

## One-command dry run

```powershell
.\scripts\run_mvp_demo.ps1
```

The command creates a unique directory under `data/demo`, starts the backend,
applies the idempotency migration, builds ingestion, creates the real-image
video fixture, samples 30 frames, tracks workers, detects PPE, associates
evidence, creates temporal candidates, validates publish payloads, and starts
the dashboard at `http://localhost:8502`.

Dry run is the default and writes no candidate event to PostgreSQL.

## Explicit send

After reviewing the dry-run artifacts:

```powershell
.\scripts\run_mvp_demo.ps1 -Send
```

New events return HTTP `201`. Replaying the same candidate returns HTTP `200`
and `skipped_duplicate` because PostgreSQL enforces the unique event key.

## Demo checkpoints

Show these in order during a presentation:

1. `source.mp4` proves the exact fixture used.
2. `frames/frames.jsonl` proves camera IDs and video timestamps.
3. `tracks/summary.json` proves temporary worker identities through time.
4. `ppe/summary.json` shows model detections and the intentionally low threshold.
5. `associations/annotated` shows which PPE evidence belongs to each track.
6. `temporal/candidate_events.jsonl` shows confirmed candidate incidents.
7. `publish/summary.json` shows dry-run, publish, skip, or duplicate outcomes.
8. The Streamlit dashboard shows stored events and evidence through FastAPI.

## Honest result from the validated run

The 6-second fixture produced 30 sampled frames and four temporal candidates:
two `NO_HELMET` and two unsupported `NO_GOGGLE` candidates. Dry run accepted
the two supported payloads. Explicit send inserted two database rows, and an
identical replay inserted zero rows.

The PPE confidence was about `0.03`. This is acceptable only for demonstrating
pipeline integration. It is not evidence of a production-ready safety model.

## Interview explanation

> I built an end-to-end computer-vision MVP that samples construction video,
> tracks workers, associates PPE detections, confirms repeated violations with
> a temporal rule, publishes idempotent events through FastAPI to PostgreSQL,
> and displays evidence in Streamlit. I also measured and documented the weak
> baseline model instead of presenting pipeline success as model accuracy.
