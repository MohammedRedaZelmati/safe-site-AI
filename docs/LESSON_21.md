# Lesson 21: Run the Streaming Architecture With One Command

## Goal

Replace many manual commands with one safe entry point:

```powershell
.\scripts\run_streaming_demo.ps1
```

The script does not replace Kafka, MinIO, YOLO, FastAPI, or PostgreSQL. It is an
orchestrator: it starts and calls each independent component in the correct order.

## The ten stages

```text
1.  Start Kafka, MinIO, PostgreSQL, and FastAPI
2.  Apply the idempotency migration
3.  Build the ingestion image
4.  Create isolated Kafka topics
5.  Generate and sample the fixture
6.  Publish frames to Bronze and Kafka
7.  Run PPE inference and write Silver
8.  Track workers, associate PPE, and write Gold
9.  Review confirmed candidate count
10. Verify API, Kafka, PostgreSQL, and measurements
```

If any stage fails, PowerShell stops immediately and writes the error into the run
summary instead of pretending the demo completed.

## Why every run gets new topics

The verified run used this prefix:

```text
safesite.demo.lesson21-20260821
```

Its topics were:

```text
safesite.demo.lesson21-20260821.frames.raw
safesite.demo.lesson21-20260821.ppe.detections
safesite.demo.lesson21-20260821.tracks
safesite.demo.lesson21-20260821.candidate-violations
safesite.demo.lesson21-20260821.candidate-violations.dlq
```

Run-specific topics prevent old Lesson 18, 19, or 20 messages from being confused
with the new demonstration. The Bronze object prefix is isolated for the same
reason.

## Candidate delivery remains opt-in

By default, the command never sends model candidates to PostgreSQL automatically.

```text
zero candidates -> finish with no_confirmed_candidates
candidates exist -> keep them pending_human_review
```

Only the explicit switch below allows API delivery:

```powershell
-SendCandidates
```

This safety boundary matters because the current PPE model is experimental and a
candidate may be a false positive.

## Verified complete run

The command used:

```powershell
.\scripts\run_streaming_demo.ps1 `
  -RunId lesson21-20260821 `
  -CameraId camera-stream-lesson21 `
  -FrameCount 30 `
  -BaseOccurredAt 2026-08-21T10:00:00+00:00
```

The final Kafka counts were:

```text
raw frame events:       30
PPE detection events:  30
track events:          30
candidate events:       0
dead-letter events:     0
```

The final MinIO counts were:

```text
Bronze objects: 30
Silver objects: 60
Gold objects:   60
empty objects:   0
```

Both processing consumer groups finished with lag `0`.

## Computer-vision result

```text
frames processed: 30
unique track IDs: 14
boots associated: 58
helmets associated: 19
vests associated: 3
confirmed violations: 0
```

PostgreSQL received zero rows for this camera because the stream produced no
confirmed violation. That is correct behavior, not a pipeline failure.

Remember:

```text
zero confirmed candidates != proof that everyone is compliant
```

## The final report

Every run writes:

```text
data/streaming/demo-<run-id>/run-summary.json
```

The report records stage status, exact topic names, API health, Kafka counts,
database rows, CV measurements, candidate mode, timestamps, and a safety
conclusion. It is the first file to inspect after a demo.

## Rerun protection

The command rejects:

- unsafe run IDs;
- camera IDs that could enter a shell or SQL command incorrectly;
- frame counts outside the 30-frame fixture;
- missing source images or model files;
- an existing run directory.

The verified guard test rejected both an invalid run ID and an attempt to reuse the
completed `lesson21-20260821` directory.

## Optional dashboard

Append the following switch to start Streamlit after the verified run:

```powershell
-StartDashboard
```

The API documentation remains available at:

```text
http://localhost:8000/docs
```

## Current limitation

This command runs finite 30-frame jobs sequentially for learning and demos. A
production system would run ingestion, inference, tracking, and API consumers as
long-lived independently scalable services. Run-specific Kafka topics must also be
cleaned according to a retention policy.

## Explain it aloud

Why is a one-command orchestrator useful even though Kafka, MinIO, FastAPI, and the
CV processors remain separate services?
