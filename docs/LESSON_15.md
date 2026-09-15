# Lesson 15: Publish a Frame Through MinIO and Kafka

## Goal

Send one sampled frame through the first real large-architecture data path:

```text
frames.jsonl -> producer -> MinIO JPEG
                         -> Kafka metadata message
```

The producer is `services/ingestion/app/publish_frames.py`.

## Why two destinations?

A JPEG is a large binary object. MinIO is designed to store that object.
Kafka is designed to transport a small event that tells another service what
happened and where the object can be found.

The producer therefore uploads the JPEG first. Only after MinIO confirms the
upload does it publish the Kafka message. This order prevents a consumer from
receiving an object URI before the object exists.

## The frame event

The first tested message was:

```json
{
  "schema_version": 1,
  "event_id": "728f22dc939e10a9b87865ca7802653516a363bc4f4717ffcb02e379e914da8a",
  "camera_id": "camera-mvp-01",
  "sample_index": 0,
  "source_frame_index": 0,
  "video_timestamp_ms": 0,
  "source_fps": 10.0,
  "object_uri": "s3://safesite-bronze/raw-frames/camera-mvp-01/frame_000000_t000000000ms.jpg",
  "content_type": "image/jpeg"
}
```

`published_at` is also included, but it changes on every publication.

The important separation is:

- `video_timestamp_ms` says when the frame occurred inside the video;
- `published_at` says when the producer sent the event;
- `object_uri` says where the JPEG is stored.

## Kafka key

The message key is `camera-mvp-01`, the camera ID. Kafka hashes this key to
choose a partition. Messages from the same camera therefore go to the same
partition and preserve their order within that partition.

## Delivery safety

The Kafka producer uses:

- `acks=all`, so Kafka confirms the write;
- idempotent producer mode, so Kafka can suppress duplicates caused by its own
  network retries;
- `flush`, so the command waits until queued messages are delivered.

This does not make the complete application exactly-once. Running the command
again can publish another event. The deterministic `event_id` lets a future
consumer recognize a replay and avoid processing the same logical frame twice.

## Reproduce the one-frame test

Docker Desktop must be running. If the ignored dependency wheels are missing,
download and verify them first:

```powershell
python scripts/download_tracking_dependency.py
python scripts/download_streaming_dependencies.py
```

Build the ingestion image and publish one frame:

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.publish_frames `
  --manifest /data/demo/mvp-20260815-223655/frames/frames.jsonl `
  --limit 1
```

Open `http://localhost:9001`, then inspect:

```text
safesite-bronze/raw-frames/camera-mvp-01/
```

The verified object was a `186640`-byte JPEG. Kafka independently returned one
message whose key was `camera-mvp-01` and whose URI pointed to that object.

## What comes next?

The next service will be a Kafka consumer. It will:

1. read the frame event;
2. parse the `s3://` URI;
3. download the JPEG from MinIO;
4. run YOLO;
5. publish structured detections to a second Kafka topic.

## Explain it aloud

Why must the producer upload the JPEG to MinIO before publishing its Kafka
message?
