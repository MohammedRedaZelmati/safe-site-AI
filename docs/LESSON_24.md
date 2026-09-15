# Lesson 24: Continuous Camera Ingestion and Absolute Event Time

## Goal

Turn a camera, RTSP URL, or video simulation into a continuous stream of Bronze
frame events.

## Start the complete streaming profile

```powershell
docker compose --profile streaming up -d --build
```

The `camera-ingestion-worker` opens the configured source, samples frames, encodes
JPEG images, uploads them to MinIO Bronze, and publishes small Kafka messages.

## The two times

Every version 2 frame event contains:

- `captured_at`: an absolute UTC timestamp used for the real incident time;
- `video_timestamp_ms`: monotonic milliseconds since this ingestion process started.

For a simulated file, `source_video_timestamp_ms` also preserves the original
position inside the video.

Absolute time answers **when did this happen?** Monotonic stream time preserves
ordering and keeps increasing when a demonstration video loops.

## Why images stay outside Kafka

MinIO stores the JPEG bytes. Kafka carries the camera ID, timestamps, event ID, and
MinIO URI. This keeps messages small while preserving replayable evidence.

## Verified result

Three simulated cameras each published one schema-version-2 event with a timezone-
aware `captured_at` value and a Bronze object URI.

## Current limitation

For RTSP, `captured_at` is the time SafeSite receives and samples the frame. A future
camera integration can preserve a hardware timestamp supplied by the camera itself.

## Explain it aloud

Why do we need both an absolute capture timestamp and a monotonic stream timestamp?
