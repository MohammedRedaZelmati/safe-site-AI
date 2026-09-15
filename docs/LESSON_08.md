# Lesson 8: First PPE Training Smoke Test

## Goal

Verify that the complete training pipeline works before spending much more time on a real baseline experiment.

## 1. Smoke test versus real training

A smoke test asks: **Can every training step run successfully?**

It verifies that YOLO can:

- read the dataset configuration;
- find training and validation images;
- read the labels;
- adapt the model from 80 COCO classes to our 11 PPE classes;
- train and validate without crashing;
- save new weights, metrics, graphs, and prediction examples.

A smoke test does not ask: **Is the model accurate enough?** One epoch on a small fraction of the data cannot answer that question.

## 2. Reproducible command

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.train_ppe_baseline --dataset /data/datasets/construction-ppe --run-name ppe-smoke-e1-f010-img320 --epochs 1 --fraction 0.1 --image-size 320 --batch-size 8 --device cpu --workers 2
```

The training tool creates a temporary dataset configuration with an absolute container path. This avoids depending on the current working directory. It also refuses to overwrite an existing run directory.

## 3. Meaning of the main settings

- `epochs=1`: the model sees the selected training data one time.
- `fraction=0.1`: use 10% of the 1,132 training images, which gives 113 images.
- `image-size=320`: resize training inputs to 320 pixels for a faster CPU test.
- `batch-size=8`: process up to eight images before updating the model.
- `seed=42`: make random choices reproducible.
- `device=cpu`: train without CUDA because the current container has CPU-only PyTorch.

The complete validation split remains unchanged: 143 images containing 1,172 labelled objects.

## 4. Measured result

The smoke test completed successfully and saved `best.pt`, `last.pt`, `results.csv`, plots, labelled validation examples, predicted validation examples, and `safesite-run.json`.

```text
precision  = 0.000572
recall     = 0.008072
mAP50      = 0.000083
mAP50-95   = 0.000025
```

These scores are almost zero. That does not mean the training code failed. The output images show many ground-truth boxes but almost no predicted boxes, which agrees with the extremely low recall.

## 5. Why the score is expected to be poor

- The model trained for only one epoch.
- It used only 113 training images.
- Its detection head was changed from 80 COCO classes to 11 PPE classes.
- Most PPE class-specific weights still need to be learned.
- The dataset contains domain mismatch and questionable class semantics discovered in Lesson 7.

The goal was pipeline verification, and that goal passed. Model quality did not pass and was not expected to pass.

## 6. Important output files

- `weights/best.pt`: checkpoint with the best validation fitness observed during this run.
- `weights/last.pt`: checkpoint after the final epoch.
- `results.csv`: one metrics row per epoch.
- `results.png`: graphs generated from the metrics history.
- `val_batch*_labels.jpg`: correct ground-truth boxes.
- `val_batch*_pred.jpg`: boxes predicted by the trained model.
- `safesite-run.json`: SafeSite summary of settings, environment, and final metrics.

With one epoch, `best.pt` and `last.pt` are effectively the same training stage. Multiple epochs are required before a trend can appear in `results.png`.

## Explain it aloud

Explain why a successful training command and a saved `best.pt` file do not prove that the resulting model is good.
