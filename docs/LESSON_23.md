# Lesson 23: Run Inference and Tracking as Independent Workers

## Goal

Move from a finite demo process:

```text
start -> process N messages -> stop
```

to a service process:

```text
start once -> wait for Kafka -> process new messages -> keep waiting
```

## The two workers

`ppe-inference-worker` consumes raw frame events, downloads Bronze frames, runs the
PPE model, stores Silver evidence, and publishes PPE events.

`tracking-worker` consumes PPE events, tracks people, associates equipment, stores
Gold evidence, and publishes track and candidate events.

Both run at the same time. Kafka separates them, so inference never calls the
tracking Python function directly.

## Start and inspect them

```powershell
docker compose --profile streaming up -d --build ppe-inference-worker tracking-worker
docker compose ps ppe-inference-worker tracking-worker
docker compose logs -f ppe-inference-worker tracking-worker
```

Stop them with:

```powershell
docker compose --profile streaming stop ppe-inference-worker tracking-worker
```

## Finite mode versus continuous mode

Lesson commands still use `--max-messages` and stop after a known number. This is
useful for reproducible tests.

Compose uses `--continuous`. In this mode:

- an empty topic is normal;
- the worker does not fail after the idle timeout;
- processed records are not accumulated forever in RAM;
- an existing output directory is accepted after restart;
- the Kafka consumer group remembers committed progress.

## The commit rule

The tracking worker commits each source event only after:

1. tracking and temporal evaluation succeed;
2. Gold files are uploaded to MinIO;
3. output messages are confirmed by Kafka.

If processing fails earlier, the input offset remains uncommitted. Kafka can
redeliver the event instead of silently losing it.

## Configuration

`.env.example` documents configurable topic names, consumer groups, output
directories, and model paths. The same Compose file can therefore use isolated test
streams without changing Python code.

## Verified results

Both workers waited on empty isolated topics for more than 35 seconds:

```text
inference: running, restart count 0
tracking:  running, restart count 0
```

A separate one-frame finite regression produced:

```text
Bronze messages:       1
PPE events:            1
PPE detections:        4
tracking events:       1
track IDs:            11
boot associations:     1
candidate violations:  0
```

This proves finite mode still works and continuous mode waits correctly. It does not
prove production readiness or model accuracy.

## Why database delivery is not always-on yet

The simulated-video pipeline still calculates incident time from a manually supplied
base time. A real camera must carry an absolute capture timestamp in every source
event. Automatic database delivery before that contract is correct could store an
incident with the wrong time.

Candidate delivery therefore remains explicit and reviewable.

## Current limitation

Tracking still supports one ordered camera stream per consumer group. The next step
is continuous camera ingestion with absolute event time, then safe multi-camera
partition ownership and worker health metrics.

## Explain it aloud

Why must the tracking worker commit its Kafka offset after MinIO and Kafka outputs
succeed rather than immediately after receiving the input event?
