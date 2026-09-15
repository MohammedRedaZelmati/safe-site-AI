# Lesson 7: PPE Dataset Acquisition and Audit

## Goal

Acquire a traceable PPE dataset, verify the exact archive, and inspect its image-label contract before training a model.

## 1. Selected baseline

The first training baseline is the official Ultralytics Construction-PPE dataset. It is small enough for a controlled experiment, already uses YOLO labels, and contains `Person`, `helmet`, `vest`, and `no_helmet` among its 11 classes.

The dataset does not contain `no_vest`. SafeSite AI must initially infer a possible missing vest when a tracked person has no associated vest detection. This rule can create false alerts when the detector misses a real vest, so it requires separate validation.

## 2. Reproducible acquisition

Run:

```powershell
python scripts/download_construction_ppe_dataset.py
```

The downloader uses the official release URL, validates the 178,415,813-byte archive against the recorded SHA256, checks ZIP paths before extraction, and never overwrites an unrelated non-empty output directory.

```text
SHA256: BEF8DCB599AA4E9D9F5E602CB6FA7143D3C84D7F6A0FF40463D7F2A4C2632CCC
```

## 3. Dataset audit

Run:

```powershell
python scripts/audit_yolo_dataset.py --dataset data/datasets/construction-ppe --output-json data/datasets/reports/construction-ppe-audit.json
```

The audit verifies:

- each image has a matching label;
- orphan labels are reported;
- every non-empty label line has five fields;
- class IDs exist in `data.yaml`;
- normalized coordinates are finite and within valid ranges;
- exact duplicate image files do not cross train, validation, and test splits;
- class instances and images per class are counted separately.

## 4. Observed structure

```text
train = 1,132 images and 1,142 labels
val   =   143 images and   143 labels
test  =   141 images and   141 labels
```

All 11,614 boxes have valid five-field YOLO records and normalized coordinates. Every image has a label, and no exact image duplicates cross the predefined splits.

The training directory contains ten orphan labels whose stems end in `(1)`. They have no matching images. We preserve the original source dataset and record this limitation instead of silently deleting source files. Ultralytics will not train from those orphan labels because there are no corresponding images.

## 5. Relevant class balance

Across the three splits:

```text
Person     = 2,265 boxes
helmet     = 1,750 boxes
vest       = 1,632 boxes
no_helmet  =   485 boxes
```

`no_helmet` is much less frequent than `Person`, helmet, and vest. This imbalance can reduce recall for the violation class and must be examined in per-class validation metrics.

## 6. Visual ground-truth review

Render a deterministic general sample:

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.render_yolo_labels --dataset /data/datasets/construction-ppe --split train --output-dir /data/datasets/reports/construction-ppe-visual/general --samples 12 --seed 42
```

Render a second sample that only includes images containing class `7`, `no_helmet`:

```powershell
docker compose --profile tools run --rm ingestion python -m app.render_yolo_labels --dataset /data/datasets/construction-ppe --split train --output-dir /data/datasets/reports/construction-ppe-visual/no-helmet --samples 12 --seed 42 --required-class-id 7
```

The tool converts normalized YOLO labels into pixel boxes, writes one annotated image per source, creates a contact sheet, and records the exact selection in `index.json`. Seed `42` means another developer reviewing the same dataset receives the same images.

The general review selected 12 images from 1,132 eligible training images. The targeted review selected 12 images from 232 training images containing `no_helmet`.

### Observed visual findings

- The PPE demonstration images generally contain sensible `Person`, helmet, vest, glove, goggle, and boot regions.
- The dataset also contains many images outside the construction domain, including offices, conferences, sports, kitchens, and an elephant scene.
- `no_helmet` usually labels the head region rather than the entire person. This is important when interpreting model output and associating PPE with a person.
- The broad `none` boxes appear semantically ambiguous and often cover torso or clothing regions.
- Some boxes and labels overlap heavily, making small-object annotations difficult to review and potentially difficult to learn.

This 24-image sample does not prove that every remaining annotation is correct or incorrect. It does prove that the dataset has meaningful domain mismatch and semantic limitations. We will treat it as an experimental baseline, not as production-quality ground truth, and later evaluate on construction-only footage.

## 7. What these audits do not prove

A structural audit plus a 24-image visual sample still does not prove full annotation quality. Unreviewed boxes may be too loose, too tight, missing, or semantically inconsistent. Exact-hash duplicate checking also does not detect visually near-identical resized or recompressed images.

## Explain it aloud

Explain why this dataset can pass structural validation but still require construction-specific validation before deployment.
