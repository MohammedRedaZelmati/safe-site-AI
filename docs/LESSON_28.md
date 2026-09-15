# Lesson 28: Gold Parquet, Data Quality, and Airflow

## Goal

Turn many detailed Gold JSON records into small analytics tables, verify that the
tables are trustworthy, and describe how Airflow runs this work every day.

## Why not analyze every JSON file directly?

One Gold JSON file is excellent evidence for one processed frame. It contains
tracks, boxes, PPE associations, temporal states, and candidate events.

Analytics asks different questions:

- How many frames did each camera process today?
- How many worker observations were produced?
- How many candidate violations appeared?
- Did the daily totals match the detailed records?

Opening thousands of nested JSON files for every question is slow and awkward.
Parquet reorganizes selected fields into typed columns. A query can read only the
columns it needs, and repeated values compress well.

## The three Parquet tables

### `frames.parquet`

One row represents one processed frame. It keeps the event ID, camera, event time,
sample position, evidence URIs, tracked-person count, association count, and
candidate count.

### `worker_evidence.parquet`

One row represents one tracked worker in one frame. It keeps the temporary track
ID, positive PPE evidence, direct violation evidence, and the number of unknown
temporal states.

### `daily_camera_summary.parquet`

One row represents one camera on one day. It contains totals calculated from the
two detailed tables.

```text
Gold JSON records
      |
      v
Parquet aggregation
      |
      +--> frames
      +--> worker evidence
      +--> daily camera summary
      |
      v
data-quality gate
```

## The quality gate

The validator runs 12 checks before analytics data is accepted. It verifies:

- required columns exist;
- the frame table is not empty;
- event IDs and camera IDs are present;
- every event ID is unique;
- capture times are timezone-aware UTC values;
- indexes and counts are non-negative;
- every worker row points to a real frame;
- daily totals equal the detailed tables;
- the JSON aggregation summary equals the Parquet row counts.

If one check fails, the command exits with code `1`. This matters because an
orchestrator must stop bad data instead of silently publishing it.

## Airflow in simple words

Airflow is a scheduler for workflows. A workflow is called a DAG, and each box in
the DAG is a task.

Our DAG has two ordered tasks:

```text
aggregate Gold JSON into Parquet
                |
                v
validate Parquet quality
```

The second task runs only after the first succeeds. The DAG is scheduled daily,
does not replay old dates automatically, and allows one active run at a time.

Airflow does not perform the aggregation itself. It starts our Python commands,
records their status, and stops the workflow when a command fails.

## Run the block with one command

For the default live-worker directories:

```powershell
docker compose --profile analytics run --rm --no-deps gold-analytics
```

For the verified three-camera records:

```powershell
$env:SAFESITE_GOLD_RECORDS_DIR = "/data/workers/block24to27/tracking/records"
$env:SAFESITE_GOLD_PARQUET_DIR = "/data/lake/gold/block28-proof"
docker compose --profile analytics run --rm --no-deps gold-analytics
```

## Verified result

The real Gold records created by the three-camera streaming proof produced:

```text
source JSON records:       3
frame rows:                3
worker evidence rows:      6
daily camera rows:         3
quality checks:           12
failed checks:             0
status:               passed
```

A separate negative test copied one event twice. The validator returned exit code
`1` and named `event_ids_unique` as the failed check. This proves the gate can
reject known bad data, not only approve good data.

## Honest boundary

The Airflow DAG and its runtime contract are implemented, but the heavy Airflow
webserver and scheduler were not launched for this local proof. The same two task
commands were run directly. In deployment, Airflow must receive the SafeSite
Python environment and the shared Gold data mount described in
`orchestration/airflow/README.md`.

## Explain it aloud

Why should Airflow stop after a failed quality check instead of publishing the
daily summary anyway?
