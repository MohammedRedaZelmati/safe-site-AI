# Lesson 17: Stream a MinIO Frame Through YOLO

## Goal

Connect Kafka, MinIO, and YOLO in one safe processing unit:

```text
safesite.frames.raw
        -> inference consumer
        -> Bronze JPEG from MinIO
        -> YOLO
        -> Silver annotated JPEG + prediction JSON
        -> safesite.detections
```

The service is `services/ingestion/app/infer_frame_events.py`.

## Why this is a separate consumer

The producer should not wait for YOLO. It only stores a frame and announces that
the frame is ready. The inference consumer can run at its own speed, restart, and
scale independently.

This separation also gives Kafka a measurable backlog. If cameras produce frames
faster than YOLO can process them, consumer lag shows how much work is waiting.

## Complete processing order

For each raw-frame event, the inference service:

1. reads and validates the Kafka event;
2. downloads its Bronze JPEG from MinIO;
3. runs YOLO on the local JPEG;
4. writes an annotated JPEG and prediction JSON atomically;
5. uploads both outputs to the `safesite-silver` bucket;
6. publishes a detection event to `safesite.detections`;
7. waits for Kafka delivery confirmation;
8. commits the original raw-frame offset.

The commit remains last. If YOLO, MinIO Silver, or detection-event publication
fails, the source frame can be delivered again instead of being silently lost.

## Bronze and Silver

Bronze preserves raw input:

```text
s3://safesite-bronze/raw-frames/camera-mvp-01/<frame>.jpg
```

Silver preserves machine-processed output:

```text
s3://safesite-silver/detections/camera-mvp-01/<detection-id>/annotated.jpg
s3://safesite-silver/detections/camera-mvp-01/<detection-id>/prediction.json
```

Keeping both means we can reproduce or audit an inference result without changing
the original evidence.

## Deterministic detection ID

The detection ID is derived from:

- the source frame event ID;
- the model SHA256;
- the confidence threshold;
- the inference image size.

The same frame processed with the same model and settings receives the same ID.
Changing the model or an important inference setting creates a different ID.

This lets several model versions process one frame without overwriting each
other's outputs.

## Why load YOLO once?

Loading model weights is expensive. The service creates the YOLO model before its
message loop:

```text
load model once
    -> frame 1
    -> frame 2
    -> frame 3
```

It does not reload the weights for every Kafka event. This becomes important for
continuous video streams.

## Detection event

The new topic is:

```text
safesite.detections
```

It has three partitions. The message key remains `camera_id`, preserving
per-camera order.

The event contains:

- source frame ID and URI;
- annotated-image and prediction-JSON URIs;
- model SHA256 and inference settings;
- detection count, classes, confidence scores, and boxes;
- camera ID and video timestamp.

A later tracking consumer can use this event without knowing where the producer
stored local files.

## Verified run

The service consumed raw partition `2`, offset `0`, then committed next offset
`1`. Kafka reported source lag `0`.

YOLO produced `11` `person` boxes at confidence `0.25`. Silver contained:

```text
annotated.jpg   233524 bytes
prediction.json  2646 bytes
```

The detection event was independently read back from `safesite.detections`.

## Important quality boundary

This run used the verified COCO `yolo26n.pt` model. It detects general objects
such as `person`; it does not classify helmet or vest violations.

The frame also contains small and overlapping background people. Eleven returned
boxes do not prove eleven perfectly detected people, and they certainly do not
prove eleven safety violations.

This experiment proves that the streaming inference architecture works. It is not
a PPE model-quality evaluation.

## Reproduce the run

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.infer_frame_events `
  --group-id lesson-17-your-name `
  --output-dir /data/streaming/lesson-17-your-name `
  --model /data/models/yolo26n.pt `
  --confidence 0.25 `
  --image-size 640 `
  --max-messages 1
```

Use a new group ID only when you intentionally want to process the earliest raw
frame event again.

## What comes next?

Next we will consume detection events and connect tracking or PPE-specific
inference while preserving the same event contract and commit rule.

## Explain it aloud

Why must the inference consumer commit the raw-frame offset only after Silver
objects and the detection event have been saved successfully?
