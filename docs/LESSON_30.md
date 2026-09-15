# Lesson 30 - Data Quality and Drift

## The simple idea

Two different questions must be answered after the pipeline starts producing data:

1. **Is each event structurally valid?** Great Expectations checks this.
2. **Does today's input look different from the reference input?** The drift job checks this.

These checks protect different things. A perfectly formatted event can still come from a dark or blurry camera, and a visually different camera can still produce valid JSON.

## Great Expectations

`services/monitoring/validate_events.py` loads violation events and applies 21 expectations. Examples are:

- required columns exist;
- IDs are unique and not null;
- timestamps can be parsed;
- `camera_id` is not empty;
- `track_id` is zero or greater;
- violation types belong to the supported list;
- confidence stays between 0 and 1.

The verified report is `data/monitoring/event-quality-report.json`. It checked three events, passed all 21 expectations, and reported zero failures.

If one check fails, the command exits with an error. This is important because Airflow or Docker Compose can stop the next step instead of silently publishing bad analytics.

## Distribution drift

`services/monitoring/analyze_drift.py` compares a reference video with a current video. It measures three distributions:

- **brightness:** did lighting change?
- **sharpness:** did focus or blur change?
- **confidence:** did the model's detection confidence change?

The comparison uses Population Stability Index, or PSI:

- PSI below `0.10`: stable;
- PSI from `0.10` to below `0.25`: warning;
- PSI `0.25` or higher: drift.

The verified report is `data/monitoring/drift-report.json`. It detected drift in brightness, sharpness, and confidence between the two tested videos.

## The most important limitation

**Drift does not automatically mean the model is inaccurate.** It means the input or model-output distribution changed enough to deserve investigation.

To prove accuracy changed, we need labels and evaluation metrics such as precision, recall, and mAP. Drift is an early warning, not a final verdict.

## Run the checks

```powershell
docker compose --profile monitoring run --rm drift-monitor
docker compose --profile monitoring run --rm event-quality
```

## Explain it aloud

> Great Expectations checks whether each event respects our data contract. The drift job compares distributions to detect changes in camera conditions or model confidence. A drift alert tells us to investigate; it does not prove that model accuracy decreased.

