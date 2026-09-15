# Lesson 20: Send Confirmed Kafka Violations to FastAPI

## Goal

Connect the final event path:

```text
safesite.candidate-violations
    -> candidate API consumer
    -> FastAPI POST /violations
    -> PostgreSQL
```

The consumer is the bridge between asynchronous Kafka events and the synchronous
HTTP API.

## Why we do not write directly to PostgreSQL

The consumer sends an HTTP request to FastAPI instead of executing SQL itself.
FastAPI remains responsible for:

- validating the public violation contract;
- calculating the authoritative database event key;
- inserting the row;
- returning the existing row when the same event is replayed.

This prevents Kafka consumers, dashboards, and other services from each inventing
different database rules.

## Processing order

For each Kafka candidate:

1. Read the message without automatically committing it.
2. Validate its JSON fields and Kafka camera key.
3. Reject violation types the current API cannot represent.
4. Convert relative video time into absolute occurrence time.
5. Send `POST /violations` to FastAPI.
6. Interpret HTTP `201` as a new row and HTTP `200` as a safe duplicate.
7. Save a local processing result.
8. Commit the Kafka offset only after the final outcome is durable.

## Relative time conversion

The test used:

```text
base time:          2026-08-20T10:00:00+00:00
video timestamp:   2400 ms
database time:     2026-08-20T10:00:02.400000+00:00
```

The calculation is:

```text
occurred_at = base time + video_timestamp_ms
```

Recorded camera streams should eventually carry their real capture start time in
the source contract. The CLI base time is suitable for reproducible video files
and this integration test.

## Why commit happens last

If the consumer commits before calling FastAPI and then crashes, Kafka thinks the
message is finished even though PostgreSQL never received it.

The safe order is:

```text
API success or confirmed duplicate -> save result -> commit offset
```

Network and HTTP server failures are retried. If all attempts fail, the command
stops without committing, so Kafka can deliver the message again.

## Dead-letter topic

Some messages cannot succeed by retrying. Examples include malformed JSON and a
violation type missing from the API contract.

Those messages are published to:

```text
safesite.candidate-violations.dlq
```

The dead-letter event preserves the original topic, partition, offset, key, raw
value, error, and failure time. The source offset is committed only after Kafka
confirms the DLQ publication.

## Verified result

Three messages tested the three important outcomes:

```text
1. Valid NO_HELMET candidate
   API response:       201
   consumer status:    published
   PostgreSQL rows:    1

2. Exact replay
   API response:       200
   consumer status:    skipped_duplicate
   PostgreSQL rows:    still 1

3. Unsupported NO_GOGGLE candidate
   consumer status:    dead_letter_unsupported_type
   DLQ messages:       1
   PostgreSQL rows:    still 1
```

After every test, the source consumer lag returned to `0`.

The test camera is explicitly synthetic:

```text
camera-synthetic-lesson20-20260820
```

It proves the transport and idempotency contract; it is not a real detected
violation.

## Reproduce the consumer

First ensure the dead-letter topic exists:

```powershell
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh `
  --bootstrap-server localhost:9092 `
  --create --if-not-exists `
  --topic safesite.candidate-violations.dlq `
  --partitions 3 `
  --replication-factor 1
```

Then consume one confirmed candidate:

```powershell
docker compose --profile tools run --rm ingestion python -m app.consume_candidate_events `
  --topic safesite.candidate-violations `
  --dead-letter-topic safesite.candidate-violations.dlq `
  --group-id lesson-20-your-name `
  --output-dir /data/streaming/lesson-20-your-name `
  --base-occurred-at 2026-08-20T10:00:00+00:00 `
  --api-url http://api:8000 `
  --max-messages 1 `
  --max-attempts 3 `
  --retry-backoff-seconds 1
```

Use a new group only when you intentionally want to replay old Kafka candidates.

## What comes next?

The next block will make the architecture easier to operate with one command. It
will create required topics, start services in the correct order, run the pipeline,
and verify each checkpoint automatically.

## Explain it aloud

Why must the consumer wait for API success, duplicate confirmation, or confirmed
DLQ delivery before committing the Kafka offset?
