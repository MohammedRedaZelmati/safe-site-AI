# Lesson 22: Monitor a Streaming Run in Streamlit

## Goal

Use one screen to answer four questions:

1. Did the complete pipeline finish?
2. Did every frame pass through Kafka processing stages?
3. What did computer vision measure?
4. Were confirmed violations written to PostgreSQL?

## Start it

After running the streaming demo, start the dashboard with:

```powershell
$env:SAFESITE_API_URL = "http://localhost:8000"
$env:SAFESITE_DATA_ROOT = "$PWD\data"
python -m streamlit run services/dashboard/app.py --server.port 8502
```

Then open:

```text
http://localhost:8502
```

You can also append `-StartDashboard` to `scripts/run_streaming_demo.ps1`.

## The two dashboard sections

### 1. Streaming pipeline runs

This section reads the saved `run-summary.json` files under `data/streaming`.
Choose a run to inspect its exact result.

It shows:

- the final run status;
- raw, PPE, and tracking Kafka message counts;
- confirmed candidate and PostgreSQL row counts;
- every orchestration stage result;
- frame, track, and PPE-association measurements;
- the safety conclusion;
- the complete technical JSON report.

For the verified 30-frame run, the important Kafka result is:

```text
raw 30 -> PPE 30 -> tracks 30
```

This proves that all requested frame events reached each processing stage. It does
not prove that the model understood every worker correctly.

### 2. Stored violation events

This section calls FastAPI, not PostgreSQL directly. It shows:

- total stored events;
- active cameras;
- camera and violation-type filters;
- event details;
- the local evidence image when available.

Keeping the dashboard behind FastAPI preserves one validated data contract. The UI
does not need database credentials or SQL knowledge.

## Why zero database writes can be correct

The verified run produced zero confirmed candidates. Therefore zero rows were sent
to PostgreSQL.

```text
zero candidates -> zero approved writes
```

That means the safety gate worked. It does not mean every worker was compliant,
because missing visual evidence remains unknown rather than automatically becoming
a violation.

## Refresh behavior

API responses and local run reports are cached for five seconds. Press **Refresh
now** to clear the cache immediately after a new run.

## Current limitation

This is a demo monitoring screen, not a production observability platform. It reads
completed run reports and current API data. Production monitoring would also use
live service metrics, logs, alerts, Kafka lag exporters, and MinIO health metrics.

## Explain it aloud

Why can `30 raw -> 30 PPE -> 30 tracks` prove pipeline completeness without proving
that the PPE model is accurate?
