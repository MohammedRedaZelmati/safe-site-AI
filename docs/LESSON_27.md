# Lesson 27: Worker Health, Kafka Lag, and Alerts

## Goal

Know whether a running pipeline is alive and keeping up with incoming frames.

## Heartbeats

Each long-running worker atomically writes a small JSON heartbeat containing:

- worker name and status;
- processed event count;
- last update time;
- last event and camera when available.

The monitor reports a missing, stopped, or stale heartbeat as an alert.

## Kafka lag

Lag is the distance between the newest partition offset and the consumer group's
committed offset.

```text
lag = newest available offset - next committed offset
```

Small temporary lag is normal. Continuously increasing lag means the producer is
faster than its consumer and the worker may need optimization or more replicas.

## Endpoint checks

The monitor also checks:

- FastAPI `/health`, including PostgreSQL reachability;
- MinIO liveness and response time.

It writes `data/workers/health-report.json`, logs alerts, and runs every ten seconds.
Streamlit displays the report and marks it stale after 30 seconds if the monitor has
stopped.

## Verified live result

Five services ran together for more than 30 seconds:

```text
camera ingestion: restart 0, 20 frames
PPE inference:    restart 0, 20 frames
tracking:         restart 0, 19 frames
API delivery:     restart 0, waiting
monitor:          restart 0
Kafka lag:        raw 1, PPE 1, candidates 0
API:              HTTP 200
MinIO:            HTTP 200
alerts:           0
status:           healthy
```

## Explain it aloud

Why can a worker process be running while the pipeline is still unhealthy?
