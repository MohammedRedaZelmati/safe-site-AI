# Lesson 13: Publishing Candidate Events Safely

## Goal

Convert temporal candidates into valid FastAPI payloads and publish only supported events to PostgreSQL.

The default mode is a dry run. Sending requires the explicit `--send` flag.

## 1. Why another stage is needed

The temporal engine creates internal candidate records containing video-specific fields:

```text
video_timestamp_ms
window_size
evidence_count
source_violation_class
```

FastAPI accepts the `ViolationCreate` contract:

```text
occurred_at
camera_id
track_id
violation_type
confidence
frame_uri
```

The publisher is an adapter between these two contracts. It validates, transforms, filters, and optionally sends each candidate.

## 2. Supported event types

The PPE model can currently produce candidate types such as:

```text
NO_HELMET
NO_GOGGLE
NO_GLOVES
NO_BOOTS
```

The current API accepts:

```text
NO_HELMET
NO_VEST
NO_MASK
```

Only `NO_HELMET` is shared by both contracts. Therefore, the first publisher allows only:

```text
SUPPORTED_API_TYPES = {"NO_HELMET"}
```

Unsupported candidates are recorded as `skipped_unsupported_type`. They are never sent and cannot cause an API `422` response.

## 3. Converting video time

`video_timestamp_ms` is relative to the beginning of a video. PostgreSQL needs an absolute `occurred_at` timestamp.

The command receives the real start time of the video:

```text
base_occurred_at = 2026-08-15T10:00:00+00:00
video_timestamp_ms = 800
```

The publisher calculates:

```text
occurred_at = base_occurred_at + 800 milliseconds
            = 2026-08-15T10:00:00.800000+00:00
```

The base timestamp must include a timezone. A timestamp without `Z` or an offset such as `+00:00` is rejected.

## 4. Dry-run mode

Without `--send`, the publisher:

1. reads candidate JSONL;
2. validates required fields and value ranges;
3. skips unsupported event types;
4. builds the exact FastAPI payload;
5. writes the result locally;
6. makes no HTTP request.

Example:

```powershell
docker compose --profile tools run --rm ingestion python -m app.publish_candidate_events --candidates /data/inference/ppe-baseline-e10/pexels-first-10s-temporal-w5-t3/candidate_events.jsonl --output-dir /data/inference/ppe-baseline-e10/pexels-first-10s-publish-dry-run --base-occurred-at 2026-08-15T10:00:00+00:00 --api-url http://api:8000
```

This prevents accidental test data from entering PostgreSQL.

## 5. Explicit send mode

After reviewing the dry-run payload, use a new empty output directory and append:

```text
--send
```

The publisher then:

```text
candidate
    v
supported type?
    v
build payload
    v
POST /violations
    v
FastAPI validation
    v
calculate deterministic event_key
    v
PostgreSQL unique index + INSERT
```

FastAPI returns HTTP `201 Created` for a new row or HTTP `200 OK` with the
existing row when the event was already stored.

## 6. Duplicate check

FastAPI hashes the canonical event fields into a 64-character `event_key`:

```text
camera_id
track_id
violation_type
occurred_at
confidence
frame_uri
```

PostgreSQL owns a unique partial index on this key. Two concurrent publishers
can therefore race safely: only one row can be inserted.

The publisher interprets HTTP `200` as `skipped_duplicate`. PostgreSQL, not the
publisher, is the authoritative duplicate guard.

## 7. Output files

```text
publish_results.jsonl -> one dry-run, skipped, duplicate, or published result per candidate
summary.json          -> mode, API URL, base time, supported types, and status counts
```

The output directory must be empty. This prevents one run from silently mixing with another.

## 8. Tests performed

We used two controlled candidates:

```text
NO_HELMET -> accepted in dry run and published once
NO_BOOTS  -> skipped as unsupported
```

Measured end-to-end result:

```text
first send  -> one PostgreSQL row created
second send -> same NO_HELMET candidate skipped as duplicate
NO_BOOTS    -> skipped during both runs
cleanup     -> only the scoped test row deleted
```

The compliant real clip has an empty `candidate_events.jsonl`, so its dry run processed zero candidates and wrote nothing to PostgreSQL.

## 9. Current boundary

The publisher now proves the complete technical path:

```text
candidate JSONL -> publisher -> FastAPI -> PostgreSQL
```

However, we must not claim production-ready safety detection yet:

- the real clip contains no violations;
- violation-class model recall is weak;
- the temporal thresholds are baseline values;
- only `NO_HELMET` is aligned end to end;
- the event key is exact-event idempotency, not semantic episode matching.

## Explain it aloud

Explain why dry-run mode and API-type filtering are necessary before adding `--send`.
