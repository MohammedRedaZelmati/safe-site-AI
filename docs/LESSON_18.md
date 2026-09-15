# Lesson 18: Stream 30 Frames Through the PPE Model

## Goal

Move from a one-frame architecture proof to an ordered 30-frame PPE inference
stream:

```text
30 sampled frames
    -> MinIO Bronze
    -> safesite.frames.raw
    -> trained PPE model
    -> MinIO Silver
    -> safesite.ppe.detections
```

This gives later tracking and temporal rules a complete sequence instead of one
isolated image.

## Resume without duplicating frame 0

Frame `0` was already published in Lesson 15. Publishing the complete manifest
again would add another Kafka message for that frame.

`publish_frames.py` therefore now accepts:

```text
--start-sample-index 1
```

It validates the complete manifest but publishes only records whose sample index
is at least `1`. The existing topic changed from one event to exactly 30 events:

```text
before: partition 2 end offset = 1
after:  partition 2 end offset = 30
```

The first event plus the remaining 29 events give sample indexes `0` through `29`
exactly once.

## Why all messages used partition 2

Every message used the same key:

```text
camera-mvp-01
```

Kafka hashes the key to partition `2`. Keeping one camera in one partition
preserves its frame order:

```text
sample 0 -> sample 1 -> ... -> sample 29
```

Other cameras can hash to other partitions and be processed in parallel.

## PPE inference configuration

The stream used the trained experimental model:

```text
/data/training/ppe-baseline-e10-full-img320/weights/best.pt
```

Settings matched the earlier evaluation:

```text
confidence = 0.25
image size = 320
device = cpu
```

The output topic was created with three partitions:

```text
safesite.ppe.detections
```

The inference consumer loaded the model once and processed all 30 ordered events.

## Verified transport result

The output checks proved:

```text
Kafka PPE messages:       30
unique detection IDs:     30
sample indexes complete:  true
annotated MinIO objects:  30
prediction MinIO objects: 30
verified Silver objects:  60
empty Silver objects:      0
source consumer lag:       0
```

Local evidence also contained 30 annotated images, 30 prediction files, and 30
processing records.

This proves that every source frame completed the full asynchronous inference
path.

## Measured model output

Every frame had at least one prediction. Across 30 frames, the model returned 145
boxes:

```text
Person: 64
boots:  59
helmet: 19
vest:    3
```

Confidence ranged from `0.2517` to `0.8810`.

No direct violation class appeared:

```text
no_helmet: 0
no_vest:   0
no_boots:  0
```

## Why zero violation boxes does not prove compliance

The model frequently missed visible people and PPE. It also changed helmet, vest,
and boots predictions between very similar frames.

Therefore, this reasoning is invalid:

```text
no no_helmet box -> everyone has a helmet
```

Absence of a prediction is unknown evidence. A violation requires a direct
violation-class prediction or another explicitly validated rule.

The temporal layer must not transform model silence into a safety accusation.

## Visual interpretation

Four reviewed frames contained four or five boxes each. The model usually found
two large people, sometimes found boots or a helmet, and missed several other
visible people.

The fixture is also a slowly transformed image, not 30 independent real camera
observations. Stable predictions can partly come from almost identical frames.

This is useful for pipeline integration, but it is not a valid deployment-quality
test.

## Reproduce publication

```powershell
docker compose --profile tools run --rm ingestion python -m app.publish_frames `
  --manifest /data/demo/mvp-20260815-223655/frames/frames.jsonl `
  --start-sample-index 1
```

Only use this command on a topic where frame 0 already exists and frames 1 through
29 do not. Kafka publication is at-least-once; repeating it intentionally creates
new messages even though deterministic event IDs remain the same.

## Reproduce PPE streaming inference

```powershell
docker compose --profile tools run --rm ingestion python -m app.infer_frame_events `
  --input-topic safesite.frames.raw `
  --output-topic safesite.ppe.detections `
  --group-id lesson-18-your-name `
  --output-dir /data/streaming/lesson-18-your-name `
  --model /data/training/ppe-baseline-e10-full-img320/weights/best.pt `
  --confidence 0.25 `
  --image-size 320 `
  --device cpu `
  --max-messages 30
```

Use a new group only when you intentionally want to replay all 30 input events.

## What comes next?

The next service will preserve state between these ordered frames. It will assign
temporary worker track IDs and connect PPE evidence to each track before temporal
violation rules run.

## Explain it aloud

Why does receiving zero `no_helmet` boxes not prove that every visible person is
wearing a helmet?
