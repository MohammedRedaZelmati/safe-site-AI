# Real Dataset Upgrade Plan

**Goal:** move SafeSite AI from an MVP demo to a stronger violation detector with real visual proof.

## Current status

SafeSite AI already has the complete software pipeline:

1. Video/frame ingestion.
2. PPE inference.
3. Temporal decision rules.
4. PostgreSQL event storage.
5. Dashboard review.
6. Data lake, monitoring, MLOps, and agent layers.

The weak point is not the architecture. The weak point is model evidence: the current model and demo data are not strong enough to claim production-grade violation detection.

## What we improved now

### 1. Better violation proof in the dashboard

The dashboard now shows a real labelled missing-helmet proof set before the database events.

This helps because the user can see:

- the source visual evidence;
- the labelled `no_helmet` boxes;
- how many labelled violation boxes exist;
- whether the current trained model is ready for that class.

### 2. Clear model-readiness warning

The dashboard now separates:

- **visual ground truth:** what the labelled image says exists;
- **model performance:** whether our trained model detects it correctly;
- **database records:** events already stored by the API.

This is important because a database row is not automatically visual proof. A row can be fake seed data, test data, or an event without an image.

### 3. Candidate real dataset checked

We inspected SH17 as a stronger external PPE dataset candidate.

SH17 is useful because it has:

- 8,099 annotated images;
- 75,994 object instances;
- 17 PPE and body-part classes;
- pretrained YOLO weights for benchmarking;
- industrial/manufacturing safety context.

Sources:

- GitHub: https://github.com/ahmadmughees/SH17dataset
- Paper: https://arxiv.org/abs/2407.04590
- Kaggle dataset: https://www.kaggle.com/datasets/mugheesahmad/sh17-dataset-for-ppe-detection

## Important limitation

SH17 does not directly label `no_helmet`.

It labels:

- `head`;
- `helmet`;
- `safety-vest`;
- `person`;
- other PPE/body parts.

So a missing-helmet violation must be inferred like this:

```text
person/head exists + no matching helmet near that head = possible NO_HELMET
```

That is more realistic than a direct fake label, but it also means the decision rule must be tested carefully.

## Why this matters

For a final PFE/demo, the correct story is:

```text
The architecture is complete.
The MVP proves the end-to-end flow.
The current detector is experimental.
The next production step is stronger dataset training and labelled evaluation.
```

This is a solid engineering explanation because it separates software completion from ML accuracy.

## Upgrade path from MVP to stronger detector

### Step 1: Add SH17 as a candidate dataset

Do not mix it blindly with the current dataset.

First, audit:

- class names;
- label format;
- train/validation split;
- license;
- image availability;
- domain quality.

### Step 2: Train or test a SH17 PPE model

Use SH17 pretrained YOLO weights first if possible.

Reason: testing pretrained weights is faster than training from zero and gives a baseline.

### Step 3: Build missing-helmet logic

Because SH17 has `head` and `helmet`, SafeSite can infer:

```text
if a visible head has no helmet box nearby, raise possible NO_HELMET
```

This must be stored as `candidate`, not immediately as confirmed truth.

### Step 4: Evaluate with labelled examples

For each labelled image/video frame, measure:

- true positives;
- false positives;
- false negatives;
- precision;
- recall;
- mAP when direct labels exist;
- rule accuracy when the violation is inferred.

### Step 5: Show proof in the dashboard

The dashboard should show:

- source video or image;
- annotated boxes;
- model confidence;
- decision explanation;
- event saved in PostgreSQL;
- warning when proof is missing.

## What still blocks a production claim

SafeSite AI still needs:

- a stronger real violation dataset;
- real video clips with multiple workers and mixed compliance;
- manual review labels for evaluation;
- GPU training or longer experiments;
- better helmet/vest association logic;
- dashboard evidence for every stored event.

## Final technical position

SafeSite AI is currently a complete MVP architecture with visible proof support.

It is not yet a production-certified PPE detector. To reach that level, the next main work is dataset quality, model evaluation, and proof-linked dashboard records.
