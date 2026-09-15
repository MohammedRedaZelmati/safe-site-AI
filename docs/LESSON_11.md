# Lesson 11: Associating PPE with Tracked Workers

## Goal

Connect helmet, vest, and boots detections to the correct tracked worker through the 50-frame video.

## 1. Why detection alone is not enough

The PPE model tells us that a helmet or vest exists in a frame. It does not tell us which worker owns that equipment.

ByteTrack gives each person a temporary identity:

```text
worker on the right -> track ID 1
worker on the left  -> track ID 2
```

Association combines these two results:

```text
person box with track ID
          +
PPE box in the same body region
          =
PPE evidence attached to that track ID
```

## 2. Why we reuse two output files

We already calculated:

- stable person tracks in `tracks.jsonl`;
- PPE detections in `predictions.jsonl`.

The association script reads both files instead of running the models again. This is faster and separates errors clearly:

- a missing person is a tracking problem;
- a missing helmet box is a PPE-model problem;
- a helmet attached to the wrong worker is an association problem.

## 3. The association rule

For every supported PPE box, the script checks:

1. Is the center of the PPE box inside or very close to a tracked person box?
2. Is it in a reasonable vertical body region?
3. If two people are possible, which person contains more of the PPE box?

Examples of body regions:

```text
helmet -> upper part of person box
vest   -> middle part
boots  -> lower part
```

Only one worker receives each PPE detection. If several boxes of the same PPE class match one worker in one frame, the script keeps the highest-confidence box.

This rule is simple and explainable. It is not a learned pose model, so crowded or overlapping people will require a stronger method later.

## 4. Run the experiment

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.associate_ppe_tracks --tracks /data/inference/yolo26n/pexels-first-10s-bytetrack/tracks.jsonl --predictions /data/inference/ppe-baseline-e10/pexels-first-10s-conf-025/predictions.jsonl --output-dir /data/inference/ppe-baseline-e10/pexels-first-10s-associated
```

The tool creates:

```text
associations.jsonl -> one structured association record per frame
summary.json       -> PPE coverage for each track ID
annotated/         -> visual result for every frame
```

## 5. Measured result

Both workers were observed in all 50 frames:

| Track | Helmet | Vest | Boots | Frames with no supported PPE |
| --- | ---: | ---: | ---: | ---: |
| ID 1 | 10/50 (20%) | 34/50 (68%) | 28/50 (56%) | 5/50 |
| ID 2 | 16/50 (32%) | 19/50 (38%) | 41/50 (82%) | 5/50 |

Across both workers, the script associated:

```text
helmet = 26 boxes
vest   = 53 boxes
boots  = 69 boxes
direct violation evidence = 0 boxes
```

It rejected 11 vest boxes and 12 boots boxes that did not safely match a tracked worker under the spatial rules.

## 6. The most important safety rule

The workers visibly wear helmets, but the model finds helmet evidence in only 20% and 32% of their frames.

Therefore:

```text
no helmet detection != NO_HELMET violation
```

No detection means **unknown**. A real violation event should require repeated direct violation evidence or a separately validated temporal rule. Otherwise, detector flicker would create many false alarms.

## 7. What this step proves

This experiment proves that we can:

- keep two worker identities through all 50 frames;
- attach PPE evidence separately to each identity;
- remove same-class duplicates per worker and frame;
- preserve the frame timestamp and camera ID;
- avoid creating false violations from missing positive boxes.

It does not prove that the PPE model detects real violations well. We still need labelled violation footage to measure that.

## Architecture of this test

```text
50 sampled frames
      |------------------------------|
      v                              v
COCO person detection          trained PPE detection
      v                              v
ByteTrack IDs                  helmet/vest/boots boxes
      |                              |
      |-------------> association <--|
                           v
                 PPE evidence per track ID
                           v
              temporal rule in a future lesson
```

## Explain it aloud

Explain why a missing helmet detection is stored as unknown instead of immediately creating a `NO_HELMET` event.
