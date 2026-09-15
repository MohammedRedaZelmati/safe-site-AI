# Lesson 9: Ten-Epoch PPE Baseline

## Goal

Train on the complete dataset long enough to observe learning trends, compare classes, and decide whether the model is ready for real SafeSite use.

## 1. Experiment configuration

```powershell
docker compose --profile tools run --rm ingestion python -m app.train_ppe_baseline --dataset /data/datasets/construction-ppe --run-name ppe-baseline-e10-full-img320 --epochs 10 --fraction 1.0 --image-size 320 --batch-size 8 --device cpu --workers 2
```

The experiment used:

- all 1,132 training images;
- 10 epochs;
- approximately 142 batches and model updates per epoch;
- 320-pixel inputs;
- batch size 8;
- seed 42;
- the complete validation split of 143 images and 1,172 objects.

The CPU training process took 0.387 hours, approximately 23 minutes. Final checkpoint validation took several additional seconds.

## 2. Did the model learn?

Yes. The evidence is much stronger than simply seeing that the command completed.

From epoch 1 to epoch 10:

```text
training box loss:       1.9678 -> 1.7562
training class loss:     4.2440 -> 1.7779
validation box loss:     1.8942 -> 1.8048
validation class loss:   3.3008 -> 1.7749
recall:                  0.1198 -> 0.4316
mAP50:                   0.1276 -> 0.4037
mAP50-95:                increased through epoch 10 to 0.2011
```

Training and validation losses generally decreased while mAP increased. There is no clear overfitting signal in these ten epochs. Epoch 10 produced the highest mAP50-95, so this experiment may still be undertrained rather than finished.

Precision moved up and down because it depends on the confidence threshold and its trade-off with recall. One fluctuating metric should not be interpreted alone.

## 3. Overall best-checkpoint result

Independent validation of `best.pt` produced:

```text
precision  = 0.5802
recall     = 0.4207
mAP50      = 0.4054
mAP50-95   = 0.2010
```

This is a major improvement over the one-epoch smoke test, but it is not a production-quality result.

## 4. Important per-class results

```text
Class        Recall   mAP50
Person       0.8285   0.8107
vest         0.7544   0.7131
helmet       0.7047   0.6212
no_helmet    0.1556   0.2701
no_goggle    0.0000   0.0545
no_gloves    0.0357   0.0536
no_boots     0.0000   0.0054
```

The model learned common positive classes much better than violation classes. This is a serious SafeSite limitation because detecting a person is not enough; the project must reliably detect missing PPE.

`no_helmet` recall of `0.1556` means the model finds only about 16% of labelled no-helmet cases at the selected operating point. Approximately 84% are missed. Those misses are false negatives.

Some rare classes report precision `1.0` together with recall `0.0`. This is not excellent performance. The model produced no useful detections for those classes, so the precision value is not meaningful by itself.

## 5. What the graphs show

- `results.png` shows training and validation losses generally moving downward.
- Recall, mAP50, and mAP50-95 generally move upward.
- The curves are still improving at epoch 10, so more training could help.
- The normalized confusion matrix shows strong `Person` recognition but many violation objects falling into background.

The background row represents labelled objects that the model missed. A large background value for a violation class signals false negatives.

## 6. What the validation images show

The predicted images now contain real boxes, unlike the one-epoch smoke test. The model often finds people and sometimes vests, helmets, and boots.

However, many correct `no_helmet`, `no_gloves`, and `no_goggle` labels are absent from the prediction images. The visual evidence therefore agrees with the weak per-class recall values.

The images also repeat the Lesson 7 warning: many validation scenes are not construction sites. A good score on this validation split would still not prove performance on real construction cameras.

## 7. Baseline decision

This run is a valid learning baseline:

- the model clearly learned;
- the experiment is reproducible;
- metrics and visual outputs agree;
- `best.pt` can be tested on real project footage.

It is not production-ready because the violation classes that matter most have poor recall and the dataset has domain mismatch. Lesson 10 tests `best.pt` on the real Pexels construction clip before we combine PPE inference with tracking.

## Explain it aloud

Explain why a model with good `Person` performance can still be a bad SafeSite violation detector.
