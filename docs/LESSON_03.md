# Lesson 3: Video Frames, Timing, and Sampling

## Goal

Understand FPS, resolution, codecs, containers, decoding, and time-based frame sampling. Generate a controlled demo video, sample it at 5 FPS, and verify that every JPEG has traceable metadata.

## 1. Video mental model

A video is an ordered sequence of frames with timing information. A 6-second video at 30 FPS contains approximately:

```text
6 seconds x 30 frames/second = 180 frames
```

The frame index identifies position in the file. The timestamp identifies when that frame occurs in video time.

## 2. Codec and container

MP4 is a container. It can hold compressed video, audio, timestamps, and metadata. H.264, H.265, and MPEG-4 Part 2 are codecs that describe how video pixels are compressed.

OpenCV decodes compressed video into arrays of pixels. YOLO receives those arrays, not compressed MP4 bytes.

## 3. Why sample frames

PPE state usually changes more slowly than the camera frame rate. Processing 5 frames per second instead of 30 reduces inference work by a factor of six:

```text
30 source FPS / 5 target FPS = process every sixth frame
```

That means one frame is processed and five frames are skipped between selections.

## 4. Generate the controlled video

```powershell
docker compose --profile tools run --rm ingestion python -m app.generate_demo_video `
  --output /data/demo/source.mp4 `
  --duration-seconds 6 `
  --fps 30 `
  --width 640 `
  --height 360
```

Expected metadata:

```text
duration = 6 seconds
fps = 30
total frames = 180
resolution = 640 x 360
```

## 5. Sample at 5 FPS

Use a new output directory each time:

```powershell
docker compose --profile tools run --rm ingestion python -m app.sample_frames `
  --input /data/demo/source.mp4 `
  --output-dir /data/demo/sample-5fps `
  --target-fps 5 `
  --camera-id camera-demo
```

Expected result:

```text
6 seconds x 5 samples/second = 30 JPEG files
```

## 6. Metadata contract

Each line of `frames.jsonl` is one independent JSON object:

```json
{
  "camera_id": "camera-demo",
  "sample_index": 10,
  "source_frame_index": 60,
  "video_timestamp_ms": 2000,
  "source_fps": 30.0,
  "image_path": "/data/demo/sample-5fps/frame_000010_t000002000ms.jpg"
}
```

JSON Lines is useful for streaming because a producer can write one event at a time without loading or rewriting one large JSON array.

## 7. Sampling by time

The sampler calculates each source frame's video time:

```text
timestamp = frame_index / source_fps
```

It saves a frame whenever that timestamp reaches the next target sample time. This works when source FPS is not perfectly divisible by target FPS, such as 29.97 FPS sampled at 5 FPS.

## Explain it aloud

Explain why `source_frame_index`, `video_timestamp_ms`, and `camera_id` are all required even though they describe the same JPEG.

