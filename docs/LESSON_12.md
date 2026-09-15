# Lesson 12: Temporal Candidate-Violation Rules

## Goal

Transform repeated direct violation evidence from many frames into one candidate incident per worker and violation type.

This lesson does not send events to FastAPI yet. It first proves that the temporal decision is safe and understandable.

## 1. The state key

The engine keeps separate memory for:

```text
(camera_id, track_id, violation_type)
```

Examples:

```text
(camera-01, 2, NO_HELMET)
(camera-01, 2, NO_BOOTS)
(camera-01, 1, NO_HELMET)
```

Therefore, a `NO_HELMET` cooldown for worker 2 does not block `NO_BOOTS`, worker 1, or another camera.

## 2. Three evidence states

For every worker and violation type, one frame has one state:

```text
violation -> direct no_helmet box exists
opposite  -> direct helmet box exists
unknown   -> neither direct box exists
```

Unknown is neutral. It neither confirms nor cancels a violation.

The engine never converts a missing helmet, vest, or boots box into a violation. This protects the system from detector flicker.

## 3. Sliding-window rule

Our first rule uses:

```text
window size              = 5 observations
required direct evidence = 3 observations
allowed opposite evidence = 0 observations
cooldown                 = 10 seconds
```

Example:

```text
no_helmet, no_helmet, unknown, no_helmet, unknown
```

The window contains three direct `no_helmet` detections and no helmet detection, so it creates one candidate `NO_HELMET` event.

Example with conflicting evidence:

```text
no_helmet, no_helmet, helmet, no_helmet, unknown
```

It has three violation detections, but also direct helmet evidence. With `maximum_opposite_evidence = 0`, this window is rejected.

This is deliberately conservative for the first baseline.

## 4. Cooldown and deduplication

Without cooldown, overlapping windows could create the same incident repeatedly:

```text
frames 1-5 -> confirmed
frames 2-6 -> confirmed again
frames 3-7 -> confirmed again
```

After the first event, the exact `(camera, track, violation type)` key enters cooldown. The engine continues observing but does not create another event for that key until cooldown ends.

Three detections are evidence for one continuous incident, not three database incidents.

## 5. Synthetic proof

We tested a controlled ten-frame sequence with two workers:

- worker 1 had three `no_helmet` detections but also one helmet detection in the window;
- worker 2 had repeated `no_helmet` detections;
- worker 2 also had three `no_boots` detections;
- repeated `no_helmet` windows continued during cooldown.

Measured result:

```text
worker 1 NO_HELMET -> blocked by opposite helmet evidence
worker 2 NO_HELMET -> one candidate event
worker 2 NO_BOOTS  -> one separate candidate event
later NO_HELMET windows -> blocked by cooldown
```

This proves that opposite evidence, independent violation types, and cooldown work as designed.

## 6. Run on the real 50-frame clip

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.temporal_violations --associations /data/inference/ppe-baseline-e10/pexels-first-10s-associated/associations.jsonl --output-dir /data/inference/ppe-baseline-e10/pexels-first-10s-temporal-w5-t3 --window-size 5 --evidence-threshold 3 --cooldown-ms 10000 --maximum-opposite-evidence 0
```

There are 50 frames and two tracked workers, so each violation rule receives 100 worker observations.

Measured result:

```text
direct no_helmet evidence = 0
helmet opposite evidence  = 26
unknown helmet state      = 74

direct no_boots evidence  = 0
boots opposite evidence   = 69
unknown boots state       = 31

candidate events          = 0
```

The compliant workers generated no candidate violations. Most importantly, 74 unknown helmet states did not become 74 false `NO_HELMET` alerts.

## 7. Output files

```text
timeline.jsonl         -> every state, window, threshold, and cooldown decision
candidate_events.jsonl -> only newly confirmed candidate incidents
summary.json           -> settings and aggregate counts
```

`candidate_events.jsonl` is empty for the compliant real clip, which is the expected result.

## 8. Current limitations

The Construction-PPE dataset has no `no_vest` class. Therefore, this engine cannot safely create `NO_VEST` from this model. A missing vest detection remains unknown.

The current FastAPI/PostgreSQL contract accepts `NO_HELMET`, `NO_VEST`, and `NO_MASK`, while this PPE model can directly predict `no_helmet`, `no_goggle`, `no_gloves`, and `no_boots`.

Before sending candidates to the API, we must deliberately align these event types. Lesson 12 leaves candidates local so an incompatible event cannot enter PostgreSQL.

The values `5`, `3`, and `10 seconds` are baseline rules, not scientifically validated production thresholds. Labelled violation videos are required to tune them.

## Architecture

```text
associations.jsonl
        v
state per worker and violation type
        v
latest five observations
        v
threshold + opposite-evidence check
        v
per-key cooldown
        v
candidate_events.jsonl
        v
future API contract alignment and POST
```

## Explain it aloud

Explain why three direct `no_helmet` detections can become one incident, while 74 unknown helmet observations become zero incidents.
