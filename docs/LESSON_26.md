# Lesson 26: Always-On Candidate Delivery With Correct Event Time

## Goal

Run candidate-to-API delivery continuously without inventing incident timestamps.

## Event-time propagation

The path now preserves absolute time:

```text
camera captured_at
  -> raw event
  -> PPE event
  -> tracking record
  -> candidate occurred_at
  -> FastAPI occurred_at
  -> PostgreSQL occurred_at
```

The `candidate-api-worker` no longer needs a manually supplied base time for live
events.

## Safety behavior

The worker:

1. validates the candidate and supported API type;
2. requires `occurred_at` when no historical base time exists;
3. retries temporary network or server failures;
4. accepts HTTP `201` as created and `200` as an idempotent replay;
5. sends permanent failures to the dead-letter topic;
6. commits Kafka only after API success, duplicate confirmation, or confirmed DLQ.

A live candidate missing absolute event time is not guessed. It is routed to the
DLQ with `dead_letter_missing_event_time`.

## Verified result

A synthetic live candidate was consumed without `--base-occurred-at`. FastAPI
returned `201`, and PostgreSQL stored exactly:

```text
camera: camera-proof-delivery
track: 24
type: NO_HELMET
confidence: 0.93
occurred_at: 2026-08-21T15:43:52.481843+00:00
```

## Explain it aloud

Why is sending a missing-time event to the DLQ safer than using the current server
time?
