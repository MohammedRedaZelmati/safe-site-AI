# Lesson 19: Track the PPE Stream and Build Temporal Evidence

## Goal

Connect the 30 ordered PPE events to the next architecture stages:

```text
safesite.ppe.detections
    -> download Bronze frame
    -> YOLO person detection + ByteTrack
    -> associate PPE boxes with track IDs
    -> sliding-window violation rules
    -> MinIO Gold evidence
    -> safesite.tracks
    -> safesite.candidate-violations only when confirmed
```

The processor loads the tracking model once and preserves ByteTrack state while
the camera frames arrive in order.

## Why one PPE topic is enough

Each PPE event already contains `camera_id`, `sample_index`,
`video_timestamp_ms`, `source_object_uri`, and `detections`. The URI points back
to the exact Bronze frame, so the processor does not need to join the raw-frame
topic again.

## What happens for every frame

1. Validate the Kafka JSON and confirm its key matches `camera_id`.
2. Confirm sample indexes are strictly increasing.
3. Download the referenced Bronze JPEG from MinIO.
4. Detect people and update ByteTrack with `persist=True`.
5. Attach helmet, vest, and boots boxes to the most plausible tracked person.
6. Mark missing PPE evidence as `unknown`, never automatically as a violation.
7. Update one sliding window per camera, track, and violation class.
8. Upload the annotated frame and structured record to MinIO Gold.
9. Publish the enriched frame to `safesite.tracks`.
10. Publish a candidate only if direct violation evidence reaches the threshold.

The Kafka micro-batch is committed only after all Gold uploads and output-topic
deliveries succeed.

## Verified 30-frame result

```text
input PPE events consumed:  30
source consumer lag:         0
track events published:     30
unique track event IDs:     30
sample indexes:             0 through 29 exactly once
local raw frames:           30
local annotated frames:     30
local structured records:   30
MinIO Gold JPEG objects:    30
MinIO Gold JSON objects:    30
empty Gold objects:          0
candidate events:            0
```

The 60 Gold objects contain `8,789,220` bytes in total.

## Tracking observations

ByteTrack produced 14 IDs. IDs `1` through `7` and `9` appeared in all 30 frames.
IDs `8` and `10` appeared in 29 and 28 frames. A few short-lived IDs appeared when
the person detector temporarily created or lost a track.

A track ID is a temporary video identity, not a permanent worker identity and not
face recognition.

## PPE association result

```text
boots associated:  58
helmet associated: 19
vest associated:    3
boots unassociated: 1
```

Visual inspection confirmed that major worker IDs stayed stable across reviewed
frames. Some labels overlap because many distant people occupy a small image area;
this is a visualization limitation, not a change in the JSON contract.

## Why zero candidates is correct

The PPE model produced no direct `no_helmet`, `no_goggle`, `no_gloves`, or
`no_boots` detections in these 30 frames. The temporal layer correctly refused to
turn missing detections into accusations.

```text
zero candidates = no confirmed violation evidence
zero candidates != proof that everyone is compliant
```

This test proves architecture and state flow. It does not prove production model
quality, especially because the fixture is a slowly transformed image rather than
independent real camera motion.

## Reproduce the processor

Use a new consumer group and an empty output directory when intentionally replaying
the 30 PPE events:

```powershell
docker compose --profile tools run --rm ingestion python -m app.process_ppe_stream `
  --input-topic safesite.ppe.detections `
  --track-topic safesite.tracks `
  --candidate-topic safesite.candidate-violations `
  --group-id lesson-19-your-name `
  --output-dir /data/streaming/lesson-19-your-name `
  --tracking-model /data/models/yolo26n.pt `
  --max-messages 30 `
  --tracking-confidence 0.25 `
  --image-size 640 `
  --device cpu `
  --window-size 5 `
  --evidence-threshold 3 `
  --cooldown-ms 10000 `
  --maximum-opposite-evidence 0
```

## Current MVP limit

One processor instance accepts one ordered camera stream per consumer group. A
production version should keep separate tracker and temporal state per camera and
checkpoint that state so it can recover exactly after a crash.

## Explain it aloud

Why is `unknown PPE` different from a confirmed `NO_HELMET` violation?
