# SafeSite Drift Monitoring

This service compares a trusted baseline window with a newer camera window.

It measures:

- mean image brightness;
- Laplacian sharpness, used as a blur proxy;
- every model detection confidence.

Population Stability Index (PSI) compares each distribution. Values below `0.1`
are treated as stable, values from `0.1` to `0.25` as warnings, and values at or
above `0.25` as drift.

Run the verified real-artifact comparison from the repository root:

```powershell
python services/monitoring/analyze_drift.py `
  --baseline-manifest data/videos/processed/pexels-8965526-first-10s-5fps/frames.jsonl `
  --baseline-predictions data/inference/ppe-baseline-e10/pexels-first-10s-conf-025/predictions.jsonl `
  --current-manifest data/demo/mvp-20260815-223655/frames/frames.jsonl `
  --current-predictions data/demo/mvp-20260815-223655/ppe/predictions.jsonl `
  --minimum-confidence 0.25
```

Drift is not accuracy. A changed brightness, blur, or confidence distribution says
that production input differs from the baseline. Only newly labeled data can prove
whether precision or recall became worse.

Validate live API events with Great Expectations:

```powershell
services/monitoring/.venv/Scripts/python.exe services/monitoring/validate_events.py `
  --api-url http://localhost:8000
```

The suite checks required columns, nulls, unique IDs, timestamp formats, camera-ID
length, non-negative tracks, allowed violation types, and confidence range.
