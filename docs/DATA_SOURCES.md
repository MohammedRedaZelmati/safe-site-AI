# Data Sources

Every external dataset, image, and video used by SafeSite AI must be recorded here before it enters the pipeline. The record must include provenance, license, retrieval date, selected file, and a cryptographic hash.

## Pexels construction workers clip

| Field | Value |
|---|---|
| Source page | https://www.pexels.com/video/construction-workers-walking-at-the-construction-site-8965526/ |
| Creator | Mikael Blomkvist |
| Description | Two workers walking at a construction site while wearing helmets and reflective safety vests |
| License | Pexels License - https://www.pexels.com/license/ |
| Retrieved | 2026-08-07 |
| Selected asset | HD vertical MP4, `720 x 1280`, `25 FPS` |
| Local path | `data/videos/external/pexels-8965526.mp4` |
| File size | `3,171,923` bytes |
| SHA256 | `1B6755FCEAAC5DED99B023AE4786C15FE9E7C99DD9BE75FC1739352FE19C53E4` |

### Measured metadata

The ingestion service measured:

```text
duration = 12.6 seconds
frame count = 315
source FPS = 25.0
resolution = 720 x 1280
```

The first ten seconds sampled at 5 FPS produced 50 JPEG frames and 50 JSONL records.

### Appropriate use

This clip is suitable for pipeline smoke tests and qualitative detection checks. It is not suitable for measuring model accuracy because it contains only two visible workers, one camera angle, one lighting condition, and positive helmet/vest examples.

The original downloaded media remains under `data/`, which Git intentionally ignores. SafeSite AI versions only the provenance record and reproducible downloader.

## Ultralytics Construction-PPE dataset

| Field | Value |
|---|---|
| Source page | https://docs.ultralytics.com/datasets/detect/construction-ppe/ |
| Publisher | Ultralytics |
| Description | Construction images labelled for people, worn PPE, and selected missing-PPE states |
| License | AGPL-3.0 |
| Retrieved | 2026-08-11 |
| Selected asset | Official `construction-ppe.zip` release archive |
| Local archive | `data/datasets/external/construction-ppe.zip` |
| Extracted path | `data/datasets/construction-ppe` |
| File size | `178,415,813` bytes |
| SHA256 | `BEF8DCB599AA4E9D9F5E602CB6FA7143D3C84D7F6A0FF40463D7F2A4C2632CCC` |

### Measured structure

```text
train = 1,132 images, 1,142 labels, 9,191 boxes
val   =   143 images,   143 labels, 1,172 boxes
test  =   141 images,   141 labels, 1,251 boxes
```

The audit found no missing image labels, malformed records, invalid normalized boxes, or exact cross-split image duplicates. It found ten orphan training labels with no matching image. The original source is preserved unchanged; the orphan files are recorded as a dataset-quality limitation.

### Relevant classes and limitations

The dataset has 11 classes. SafeSite AI initially cares about `Person`, `helmet`, `vest`, and `no_helmet`. Across all splits these classes contain 2,265, 1,750, 1,632, and 485 boxes respectively.

There is no `no_vest` class. A missing vest must initially be inferred from the absence of an associated vest detection, which can create false alerts when the model misses visible PPE. The predefined splits also require visual and near-duplicate review because exact-hash checks cannot prove scene independence.

### No-helmet dashboard proof reel

| Field | Value |
|---|---|
| Source | Curated labelled `no_helmet` sample from the Construction-PPE dataset visual review |
| Source index | `data/evaluation/no-helmet-boots-candidates/index.json` |
| Output video | `data/evaluation/no-helmet-construction-proof/no-helmet-ground-truth-review.mp4` |
| Summary | `data/evaluation/no-helmet-construction-proof/summary.json` |
| First frame | `data/evaluation/no-helmet-construction-proof/first-frame.jpg` |
| Contact sheet | `data/evaluation/no-helmet-boots-candidates/contact-sheet.jpg` |
| Labelled proof | 1 image containing 8 ground-truth `no_helmet` boxes |

This reel is useful for dashboard proof and human review because it shows a real labelled missing-helmet example. It is not a continuous camera video, and the wider dataset contains visible domain mismatch, so it must not be used as a claim of temporal production accuracy.

## Controlled six-worker PPE scene

| Field | Value |
|---|---|
| Source type | Synthetic controlled scene generated with OpenAI image generation |
| Description | Six construction workers: three compliant, two without helmets, and one without a vest |
| Source image | `data/videos/synthetic/mixed-ppe-six-workers-source.png` |
| Test video | `data/videos/synthetic/mixed-ppe-six-workers-10s.mp4` |
| Metadata | `data/videos/synthetic/mixed-ppe-six-workers-10s.json` |
| Ground truth | 6 workers, 2 `NO_HELMET`, 1 `NO_VEST` |

### Appropriate use

This controlled video makes the expected answer obvious and is useful for demonstrating the difference between visual ground truth and model predictions. It is a ten-second animated still, not natural camera footage, so it must not be used to claim real-world accuracy.

The complete streaming pipeline processed 30 sampled frames, maintained six track IDs, and confirmed zero violation candidates. That result does not mean the scene is compliant: it shows that the current experimental detector and temporal rules missed the three visible ground-truth violations.

## SH17 PPE dataset candidate

| Field | Value |
|---|---|
| Source repository | https://github.com/ahmadmughees/SH17dataset |
| Paper | https://arxiv.org/abs/2407.04590 |
| Kaggle dataset | https://www.kaggle.com/datasets/mugheesahmad/sh17-dataset-for-ppe-detection |
| Description | Industrial/manufacturing PPE dataset with people, body parts, helmets, vests, gloves, shoes, and related safety classes |
| License | CC BY-NC-SA 4.0 plus source-image restrictions from Pexels |
| Local metadata clone | `tmp/external/sh17dataset` |
| Retrieved for review | 2026-09-07 |
| Current SafeSite status | Candidate only; not yet merged into model training or production inference |

### Why it is useful

SH17 is a stronger candidate than the current small missing-PPE proof set because it includes 8,099 annotated images, 75,994 instances, 17 classes, and pretrained YOLO benchmark weights.

### Limitation for SafeSite

SH17 does not directly label `no_helmet`. It labels `head` and `helmet`, so SafeSite must infer a possible missing-helmet violation when a visible head has no associated helmet nearby. That rule needs labelled evaluation before it can be trusted.

### Appropriate use

Use SH17 first for offline research, benchmark comparison, and rule prototyping. Do not claim commercial or production readiness from it without reviewing the noncommercial license, Pexels restrictions, and validation performance on SafeSite-specific camera footage.
