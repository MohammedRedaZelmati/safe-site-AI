# Lesson 4: Evaluating Real Footage for Computer Vision

## Goal

Replace synthetic input with licensed construction footage, verify provenance, inspect real video metadata, and decide what the clip can and cannot prove about a PPE model.

## 1. Reproducible download

Run:

```powershell
python scripts/download_sample_video.py
```

The script verifies a SHA256 hash. A matching hash proves every teammate has exactly the same bytes, even if the local filename is identical.

## 2. Why record the source

A machine-learning result is not reproducible if nobody knows which data produced it. `docs/DATA_SOURCES.md` records:

- source page and creator;
- license and retrieval date;
- selected resolution and frame rate;
- local path, file size, and SHA256 hash;
- appropriate and inappropriate uses.

## 3. Measured video properties

The downloaded clip contains:

```text
resolution = 720 x 1280
source FPS = 25
duration = 12.6 seconds
frames = 315
```

The first ten seconds sampled at 5 FPS produce:

```text
10 seconds x 5 samples/second = 50 samples
```

The final sample is at 9.8 seconds because sample indexes run from 0 through 49.

## 4. Visual quality assessment

Strengths:

- two workers remain visible throughout the clip;
- helmets and reflective vests are visually distinct;
- workers approach the camera, creating multiple object scales;
- the scene is stable and well lit;
- the vertical frame preserves the workers' full bodies.

Limitations:

- both workers comply with helmet and vest requirements;
- there are no `NO_HELMET` or `NO_VEST` examples;
- only one site, camera angle, weather condition, and background appear;
- two people are insufficient for accuracy measurement;
- adjacent video frames are highly similar.

Therefore, this clip is useful for a smoke test, not a test-set score.

## 5. Data leakage warning

Never place adjacent frames from one video into different training, validation, and test sets. Nearly identical images would let the model memorize the scene and produce misleadingly strong metrics.

Split by source video or recording session:

```text
training videos   -> training frames
validation videos -> validation frames
test videos       -> test frames
```

## 6. Before running YOLO

Ask four questions:

1. Are the target objects large enough to see after resizing to 640 pixels?
2. Does the model's class vocabulary include helmet and safety vest?
3. Are we checking only whether inference runs, or measuring accuracy?
4. Do we have negative examples to test missing-PPE detection?

A generic pretrained YOLO model may detect `person`, but its standard dataset usually does not include PPE-specific helmet and vest classes. PPE detection requires PPE-specific weights or fine-tuning.

## Explain it aloud

Explain why a model detecting both workers correctly in all 50 sampled frames would still not prove that the model is accurate on real construction sites.

