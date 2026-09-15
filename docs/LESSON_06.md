# Lesson 6: Multi-Object Tracking with ByteTrack

## Goal

Connect person detections across the 50 ordered sample frames, assign temporary track IDs, and measure whether those IDs remain continuous through the clip.

## 1. Detection is not tracking

YOLO detects objects independently in each image. It can report two people in every frame without knowing whether they are the same two people over time.

ByteTrack associates nearby detections across consecutive frames and adds a temporary `track_id`:

```text
frame 0 -> person ID 1, person ID 2
frame 1 -> person ID 1, person ID 2
```

A track ID is not a name or biometric identity. It only represents the tracker's belief that detections belong to the same visible object within this sequence.

## 2. Association and recovery

The tracker uses box position, predicted movement, overlap, and detection confidence to associate new boxes with active tracks. ByteTrack first associates strong detections and then uses weaker detections to recover tracks that might otherwise disappear during blur or partial occlusion.

Tracks can be new, active, temporarily lost, or removed. A worker who leaves for long enough and later returns may receive a new ID.

## 3. Why tracking matters for violations

Without tracking, one four-second violation visible in 20 sampled frames could become 20 duplicate events. Tracking allows later logic to group those observations:

```text
track 2 + NO_HELMET + 20 consecutive frames -> one violation event
```

Tracking also supports violation duration, evidence selection, and per-worker alert cooldowns.

## 4. Run the 50-frame tracking experiment

The manifest order matters because tracking depends on time continuity.

```powershell
python scripts/download_tracking_dependency.py
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.track_frames --manifest /data/videos/processed/pexels-8965526-first-10s-5fps/frames.jsonl --output-dir /data/inference/yolo26n/pexels-first-10s-bytetrack --class-id 0
```

Class ID `0` is `person` in the COCO class vocabulary. The command creates:

```text
annotated/   -> frames with boxes and temporary IDs
tracks.jsonl -> one timestamped tracking record per frame
summary.json -> track counts, coverage, spans, and timing
```

ByteTrack requires the `lap` linear-assignment library. The download script retrieves the pinned Linux wheel on the host, verifies its SHA256, and lets Docker install it offline. This avoids disabling TLS verification inside the container.

## 5. Interpreting stability

For two workers visible in all 50 frames, the ideal observation is two unique IDs, two tracks per frame, and 100% frame coverage for each ID.

This is evidence of continuity on one short clip, not proof of tracking accuracy. Detecting ID switches requires labelled identity ground truth or careful visual review. Adjacent sampled frames are correlated, and harder scenes can include crossings, long occlusions, camera movement, and crowded workers.

## 6. Observed result

The CPU experiment produced:

```text
frames processed             = 50
frames with tracks           = 50
tracked person observations  = 100
unique track IDs             = 1 and 2
tracks per frame             = 2 in every frame
coverage for ID 1            = 50/50 frames
coverage for ID 2            = 50/50 frames
untracked detections         = 0
elapsed pipeline time        = 8.071 seconds
average processing per frame = 0.1614 seconds
```

Visual inspection of the first, middle, and last frames confirmed that the left worker remained ID `2` and the right worker remained ID `1`. This is stable continuity for this clip, but it does not prove the same performance under crossings or occlusions.

## Explain it aloud

Explain why `track_id=1` is useful for deduplicating events but does not reveal the worker's real identity.
