# Lesson 10: Testing the PPE Model on Real Video

## Goal

Test the trained `best.pt` on 50 unseen construction frames and check whether detections remain useful and stable through time.

## 1. Why this test is different

The validation images come from the same dataset family used for training. Our Pexels clip comes from a different real video and was never used to train the PPE model.

This is therefore a **generalization test**: can the model use what it learned on a new construction scene?

The clip shows two workers wearing helmets, safety vests, and boots. It has no human ground-truth label files, so we can inspect predictions visually and measure stability, but we cannot calculate official precision, recall, or mAP from this clip.

## 2. Standard-threshold test

```powershell
docker compose --profile tools run --rm ingestion python -m app.detect_frames --manifest /data/videos/processed/pexels-8965526-first-10s-5fps/frames.jsonl --output-dir /data/inference/ppe-baseline-e10/pexels-first-10s-conf-025 --model /data/training/ppe-baseline-e10-full-img320/weights/best.pt --confidence 0.25 --image-size 320 --device cpu
```

Measured across 50 frames:

```text
total detections = 290
Person           = 119 detections, present in 47/50 frames
helmet           =  26 detections, present in 19/50 frames
vest             =  64 detections, present in 36/50 frames
boots            =  81 detections, present in 45/50 frames
violation classes = 0 detections
```

The model detected people in 94% of frames, but helmet in only 38% and vest in 72%. The workers continue wearing the equipment, so the missing boxes are detector flicker, not real PPE changes.

## 3. Duplicate boxes

The video contains two workers. At confidence `0.25`, the model produced:

```text
fewer than 2 Person boxes:  8 frames
exactly 2 Person boxes:    17 frames
more than 2 Person boxes:  25 frames
```

Several frames contain duplicate Person boxes around the same worker. Therefore, raw frame-level detections cannot be counted directly as unique workers or unique events.

Tracking and association are needed to connect boxes to the two real workers and suppress duplicates through time.

## 4. Lower-threshold comparison

We repeated the test with confidence `0.10`:

```text
total detections = 739
Person           = 240
helmet           =  86
vest             = 184
boots            = 225
none             =   4
```

The lower threshold accepts uncertain predictions. It finds more PPE boxes, but 49 of 50 frames contain more than two Person boxes even though only two workers exist.

Lower confidence can improve recall, but it also increases duplicate and false-positive detections. More boxes do not automatically mean a better result.

## 5. Violation interpretation

No `no_helmet`, `no_goggle`, `no_gloves`, or `no_boots` boxes appeared at either threshold.

That is reasonable for `no_helmet` because both visible workers wear helmets. However, this clip cannot prove that the weak `no_helmet` detector works: there is no real no-helmet example to find.

Also, the absence of a helmet box in one frame must not immediately create a `NO_HELMET` event. Lesson 9 showed that helmet detection can be missed, and this video shows helmet boxes flickering between frames.

## 6. Safe event rule

A safer future rule is:

```text
track a worker through time
        +
look for associated helmet evidence over several frames
        +
require repeated missing-helmet evidence
        =
create one possible NO_HELMET event
```

This temporal rule reduces false alerts caused by one weak frame. It still requires validation on labelled violation videos.

## 7. Conclusion

The model generalizes partially:

- it finds the two workers in most frames;
- it detects some helmets, vests, and boots;
- it produces no obvious missing-PPE alert on compliant workers;
- PPE boxes flicker heavily;
- duplicate Person boxes are common;
- this compliant clip cannot measure violation recall.

The next implementation step is to combine the trained PPE model with tracking and person-to-PPE association before creating database events.

## Explain it aloud

Explain why one missing helmet box in one frame does not prove that a worker has no helmet.
