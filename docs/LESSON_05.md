# Lesson 5: First YOLO Object Detection

## Goal

Run a generic pretrained detector on one real construction frame, inspect its visual and structured outputs, and understand what this smoke test proves and does not prove.

## 1. Detection concepts

Classification answers what appears in an image. Object detection additionally returns one bounding box for each localized object.

A detection contains:

```text
class + confidence + [x1, y1, x2, y2]
```

- `x1, y1` identify the top-left corner.
- `x2, y2` identify the bottom-right corner.
- confidence controls which predictions survive the selected threshold.
- IoU measures overlap between boxes.

During evaluation, IoU compares a prediction with a human label. During live processing, box overlap can instead help compare predictions, remove duplicates in traditional detectors, or associate detections across frames.

YOLO26 needs one extra distinction: its default one-to-one head is end-to-end and does not require NMS. Its optional one-to-many head follows the traditional path and does require NMS.

## 2. Evaluation vocabulary

- **True positive:** a real object is detected correctly.
- **False positive:** the model reports an object that is not present.
- **False negative:** a real object is missed.
- **Precision:** `TP / (TP + FP)`, or how many generated alerts are correct.
- **Recall:** `TP / (TP + FN)`, or how many real violations are found.
- **mAP:** summarizes precision across classes, confidence levels, and evaluation IoU settings.

SafeSite AI must inspect per-class precision and recall. A strong overall mAP can hide weak performance on a safety-critical class.

## 3. Reproducible runtime

The ingestion Dockerfile uses the versioned CPU image:

```text
ultralytics/ultralytics:8.4.107-python
```

CPU is intentional for the first smoke test. It proves the code and model artifact work before adding CUDA, GPU drivers, and performance tuning.

The model is downloaded on the host and verified by SHA256:

```powershell
python scripts/download_yolo_model.py
```

The model provenance and license boundary are recorded in `docs/MODEL_SOURCES.md`.

## 4. Run one prediction

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.detect_image --input /data/videos/processed/pexels-8965526-first-10s-5fps/frame_000025_t000005000ms.jpg --output-image /data/inference/yolo26n/frame-25-annotated.jpg --output-json /data/inference/yolo26n/frame-25.json
```

The command creates two different outputs:

- an annotated JPEG for human inspection;
- JSON containing classes, confidence scores, and box coordinates for software.

## 5. Observed result

The five-second frame produced two detections:

```text
person  confidence=0.9047  box=[301.16, 671.12, 382.99, 887.09]
person  confidence=0.8888  box=[430.39, 672.50, 512.83, 890.34]
```

Visual inspection confirmed that each box aligns with one of the two workers.

This proves:

- the pinned Docker runtime loads;
- the verified weights load;
- one real frame reaches YOLO;
- YOLO returns machine-readable boxes;
- the annotated evidence file is written correctly.

This does not prove:

- PPE detection works;
- helmets or vests are detected;
- model accuracy is high;
- other cameras or environments will work equally well.

The COCO baseline knows `person`, but its class vocabulary does not contain our PPE classes. A PPE-specific dataset and weights are still required.

## 6. Failure studied

The first build failed because Docker Desktop was stopped. After startup, package and model downloads inside Docker encountered a local TLS certificate boundary.

We did not disable TLS verification. Instead, we used an official versioned Ultralytics image and downloaded the official weight on Windows, where it could be verified with its recorded SHA256. This preserves transport security and reproducibility.

## 7. Batch inference over 50 frames

Running the model separately for every frame would reload the same weights 50 times. `app.detect_frames` loads YOLO once, reads the frame manifest, and streams all source images through that model instance.

```powershell
docker compose --profile tools run --rm ingestion python -m app.detect_frames --manifest /data/videos/processed/pexels-8965526-first-10s-5fps/frames.jsonl --output-dir /data/inference/yolo26n/pexels-first-10s-conf-025
```

The batch command produces:

```text
annotated/         -> 50 visual evidence images
predictions.jsonl  -> one structured prediction record per frame
summary.json       -> aggregate counts, settings, and elapsed time
```

Measured result at confidence `0.25`, image size `640`, and CPU execution:

```text
frames processed             = 50
frames with detections       = 50
person detections            = 100
detections per frame         = 2 in every frame
confidence range             = 0.8306 to 0.9399
mean confidence              = 0.9033
elapsed batch time           = 9.819 seconds
average processing per frame = 0.1964 seconds
observed processing rate     = about 5.09 frames/second
```

The mean person-box height increased from `195.65` pixels in the first frame to `269.51` pixels in the last frame because the workers approached the camera.

This result demonstrates detection consistency on this one clip. It does not measure model accuracy because the frames are highly correlated, there are no human labels for IoU comparison, and the generic model still lacks helmet and vest classes. The measured time also includes prediction iteration, annotation drawing, and JPEG/JSONL writing; it is not pure neural-network latency.

## Explain it aloud

Explain why two `person` detections in every frame demonstrate consistency but do not prove accuracy or PPE capability.
