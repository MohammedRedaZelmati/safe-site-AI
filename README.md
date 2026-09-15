# SafeSite AI

SafeSite AI turns construction-site video into structured PPE-compliance events. The platform reads simulated camera streams, detects and tracks PPE violations, stores evidence, exposes analytics, and answers grounded questions about incidents.

This repository is intentionally built in layers. We start with a small working data path and replace each fake input with a real component only after understanding it.

## Current milestone: complete final architecture

```text
cameras -> Kafka + MinIO -> YOLO + ByteTrack -> temporal events
        -> FastAPI + PostgreSQL -> Streamlit
        -> Airflow + Great Expectations + drift + MLflow
        -> read-only LangGraph agent + Ollama text/vision support
```

The local MVP now combines the complete inspectable path:

1. A frame manifest preserves camera and video-time context.
2. COCO YOLO and ByteTrack give each visible person a temporary ID.
3. The trained PPE model finds helmet, vest, and boots boxes.
4. Spatial association attaches PPE evidence to one tracked worker without treating missing evidence as a violation.
5. A sliding window confirms repeated direct violation evidence and suppresses duplicate incidents with cooldown.
6. A dry-run-first publisher filters API types, converts video time, and explicitly sends supported candidates.
7. FastAPI and PostgreSQL calculate and enforce a unique event key for safe retries.
8. Streamlit combines saved pipeline-run health with API-backed violation evidence.
9. A one-command analytics job builds typed Gold Parquet tables and rejects bad totals before use.
10. MLflow records the PPE baseline, compares runs, and registers the exact packaged model as an experimental `candidate`.
11. Great Expectations validates event contracts while drift monitoring compares brightness, sharpness, and confidence distributions.
12. Airflow orders daily Gold aggregation before validation.
13. A read-only LangGraph service answers approved PostgreSQL questions through local Ollama and can ask Qwen-VL to describe evidence frames.

Start the final architecture with one command:

```powershell
.\scripts\run_final_architecture.ps1 -IncludeAirflow
```

Omit `-IncludeAirflow` for the lighter everyday stack. See `docs/FINAL_ARCHITECTURE.md` for the complete component matrix, trust boundaries, ports, and evidence.

Track and register the existing PPE baseline locally without Docker:

```powershell
python -m venv services/mlops/.venv
services/mlops/.venv/Scripts/python.exe -m pip install -r services/mlops/requirements.txt
services/mlops/.venv/Scripts/python.exe services/mlops/log_ppe_experiment.py
.\scripts\start_mlflow_ui.ps1
```

The MLflow UI opens at http://127.0.0.1:5000. The local setup uses SQLite for
tracking metadata and `data/mlflow/artifacts` for files.

## Large architecture: infrastructure foundation

Kafka and MinIO now run beside the MVP services:

- Kafka host listener: `localhost:9092`
- MinIO S3 API: http://localhost:9000
- MinIO console: http://localhost:9001
- First topic: `safesite.frames.raw` with three partitions

Kafka carries small ordered frame messages. MinIO stores the actual image and
video objects. The first producer now uploads sampled JPEGs to the
`safesite-bronze` bucket and publishes their URIs to `safesite.frames.raw`.

Publish one frame from the validated MVP manifest:

```powershell
python scripts/download_streaming_dependencies.py
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.publish_frames --manifest /data/demo/mvp-20260815-223655/frames/frames.jsonl --limit 1
```

Consume one frame event and download its MinIO object:

```powershell
docker compose --profile tools run --rm ingestion python -m app.consume_frames --group-id lesson-16-your-name --output-dir /data/streaming/lesson-16-your-name --max-messages 1
```

Run streamed YOLO inference and publish a Silver detection event:

```powershell
docker compose --profile tools run --rm ingestion python -m app.infer_frame_events --group-id lesson-17-your-name --output-dir /data/streaming/lesson-17-your-name --max-messages 1
```

Process the complete 30-frame stream with the experimental PPE model:

```powershell
docker compose --profile tools run --rm ingestion python -m app.publish_frames --manifest /data/demo/mvp-20260815-223655/frames/frames.jsonl --start-sample-index 1
docker compose --profile tools run --rm ingestion python -m app.infer_frame_events --input-topic safesite.frames.raw --output-topic safesite.ppe.detections --group-id lesson-18-your-name --output-dir /data/streaming/lesson-18-your-name --model /data/training/ppe-baseline-e10-full-img320/weights/best.pt --confidence 0.25 --image-size 320 --max-messages 30
```

Run the complete MVP in dry-run mode:

```powershell
.\scripts\run_mvp_demo.ps1
```

After reviewing the generated artifacts, use `.\scripts\run_mvp_demo.ps1 -Send`
to write supported events. The dashboard opens at http://localhost:8502.

## Run it

Prerequisites: Docker Desktop must be running.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Then open:

- API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Seeded violations: http://localhost:8000/violations
- Summary statistics: http://localhost:8000/stats/summary
- Grounded agent: http://localhost:8010/docs
- Streamlit dashboard: http://localhost:8502
- MLflow: http://localhost:5000
- Airflow: http://localhost:8080
- MinIO console: http://localhost:9001

Create an event from PowerShell:

```powershell
$body = @{
  occurred_at = (Get-Date).ToUniversalTime().ToString("o")
  camera_id = "camera-01"
  track_id = 42
  violation_type = "NO_HELMET"
  confidence = 0.91
  frame_uri = "bronze/camera-01/example.jpg"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:8000/violations -ContentType "application/json" -Body $body
```

Stop the stack with `docker compose down`. `docker compose down -v` also deletes the local database volume and should only be used when you intentionally want a fresh database.

## Learning path

- [Four-week roadmap](docs/ROADMAP.md)
- [Architecture explained](docs/ARCHITECTURE.md)
- [Lesson 1: follow one event](docs/LESSON_01.md)
- [Lesson 2: safe asynchronous API filtering](docs/LESSON_02.md)
- [Lesson 3: video frames, timing, and sampling](docs/LESSON_03.md)
- [Lesson 4: evaluating real footage](docs/LESSON_04.md)
- [Lesson 5: first YOLO object detection](docs/LESSON_05.md)
- [Lesson 6: multi-object tracking with ByteTrack](docs/LESSON_06.md)
- [Lesson 7: PPE dataset acquisition and audit](docs/LESSON_07.md)
- [Lesson 8: first PPE training smoke test](docs/LESSON_08.md)
- [Lesson 9: ten-epoch PPE baseline](docs/LESSON_09.md)
- [Lesson 10: real-video PPE baseline test](docs/LESSON_10.md)
- [Lesson 11: associating PPE with tracked workers](docs/LESSON_11.md)
- [Lesson 12: temporal candidate-violation rules](docs/LESSON_12.md)
- [Lesson 13: publishing candidate events safely](docs/LESSON_13.md)
- [Completed MVP demo guide](docs/MVP_DEMO.md)
- [Lesson 14: Kafka and MinIO foundations](docs/LESSON_14.md)
- [Lesson 15: publishing a frame through MinIO and Kafka](docs/LESSON_15.md)
- [Lesson 16: consuming a Kafka frame from MinIO](docs/LESSON_16.md)
- [Lesson 17: streaming a MinIO frame through YOLO](docs/LESSON_17.md)
- [Lesson 18: streaming 30 frames through the PPE model](docs/LESSON_18.md)
- [Lesson 19: tracking streamed PPE and temporal evidence](docs/LESSON_19.md)
- [Lesson 20: publishing Kafka candidates to FastAPI](docs/LESSON_20.md)
- [Lesson 21: running the streaming architecture with one command](docs/LESSON_21.md)
- [Lesson 22: monitoring streaming runs in Streamlit](docs/LESSON_22.md)
- [Lesson 23: independent continuous inference and tracking workers](docs/LESSON_23.md)
- [Lesson 24: continuous camera ingestion and absolute event time](docs/LESSON_24.md)
- [Lesson 25: multi-camera Kafka partitioning and tracking state](docs/LESSON_25.md)
- [Lesson 26: always-on candidate delivery with correct event time](docs/LESSON_26.md)
- [Lesson 27: worker health, Kafka lag, and alerts](docs/LESSON_27.md)
- [Lesson 28: Gold Parquet, data quality, and Airflow](docs/LESSON_28.md)
- [Lesson 29: MLflow experiments and model registry](docs/LESSON_29.md)
- [Lesson 30: data quality and drift](docs/LESSON_30.md)
- [Lesson 31: grounded agent and vision-language support](docs/LESSON_31.md)
- [Lesson 32: complete architecture walkthrough](docs/LESSON_32.md)
- [Final architecture and completion matrix](docs/FINAL_ARCHITECTURE.md)
- [External data sources and licenses](docs/DATA_SOURCES.md)
- [External model sources and licenses](docs/MODEL_SOURCES.md)
- [File catalog](docs/FILE_CATALOG.md)

Run the API integration tests with:

```powershell
docker compose --profile test run --rm api-tests
```

Build and validate the Gold analytics tables with:

```powershell
docker compose --profile analytics run --rm --no-deps gold-analytics
```

Run the video-sampling exercise with:

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.generate_demo_video --output /data/demo/source.mp4
docker compose --profile tools run --rm ingestion python -m app.sample_frames --input /data/demo/source.mp4 --output-dir /data/demo/sample-5fps --target-fps 5 --camera-id camera-demo
```

Download and sample the licensed real construction clip with:

```powershell
python scripts/download_sample_video.py
docker compose --profile tools run --rm ingestion python -m app.sample_frames --input /data/videos/external/pexels-8965526.mp4 --output-dir /data/videos/processed/pexels-8965526-first-10s-5fps --target-fps 5 --camera-id camera-pexels-01 --max-seconds 10
```

Run the first CPU-only YOLO smoke test on one sampled frame with:

```powershell
python scripts/download_yolo_model.py
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.detect_image --input /data/videos/processed/pexels-8965526-first-10s-5fps/frame_000025_t000005000ms.jpg --output-image /data/inference/yolo26n/frame-25-annotated.jpg --output-json /data/inference/yolo26n/frame-25.json
```

Run YOLO once over all 50 sampled frames while preserving manifest timestamps with:

```powershell
docker compose --profile tools run --rm ingestion python -m app.detect_frames --manifest /data/videos/processed/pexels-8965526-first-10s-5fps/frames.jsonl --output-dir /data/inference/yolo26n/pexels-first-10s-conf-025
```

Track people across the ordered frames with ByteTrack using:

```powershell
python scripts/download_tracking_dependency.py
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.track_frames --manifest /data/videos/processed/pexels-8965526-first-10s-5fps/frames.jsonl --output-dir /data/inference/yolo26n/pexels-first-10s-bytetrack --class-id 0
```

Download and audit the first PPE training dataset with:

```powershell
python scripts/download_construction_ppe_dataset.py
python scripts/audit_yolo_dataset.py --dataset data/datasets/construction-ppe --output-json data/datasets/reports/construction-ppe-audit.json
```

Render reproducible ground-truth samples for visual review with:

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.render_yolo_labels --dataset /data/datasets/construction-ppe --split train --output-dir /data/datasets/reports/construction-ppe-visual/general --samples 12 --seed 42
docker compose --profile tools run --rm ingestion python -m app.render_yolo_labels --dataset /data/datasets/construction-ppe --split train --output-dir /data/datasets/reports/construction-ppe-visual/no-helmet --samples 12 --seed 42 --required-class-id 7
```

Run the short CPU-only PPE training smoke test with:

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.train_ppe_baseline --dataset /data/datasets/construction-ppe --run-name ppe-smoke-e1-f010-img320 --epochs 1 --fraction 0.1 --image-size 320 --batch-size 8 --device cpu --workers 2
```

Run the full ten-epoch CPU baseline with:

```powershell
docker compose --profile tools run --rm ingestion python -m app.train_ppe_baseline --dataset /data/datasets/construction-ppe --run-name ppe-baseline-e10-full-img320 --epochs 10 --fraction 1.0 --image-size 320 --batch-size 8 --device cpu --workers 2
```

Test `best.pt` on the 50 real construction frames with:

```powershell
docker compose --profile tools run --rm ingestion python -m app.detect_frames --manifest /data/videos/processed/pexels-8965526-first-10s-5fps/frames.jsonl --output-dir /data/inference/ppe-baseline-e10/pexels-first-10s-conf-025 --model /data/training/ppe-baseline-e10-full-img320/weights/best.pt --confidence 0.25 --image-size 320 --device cpu
```

Associate those PPE detections with the two stable person tracks using:

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.associate_ppe_tracks --tracks /data/inference/yolo26n/pexels-first-10s-bytetrack/tracks.jsonl --predictions /data/inference/ppe-baseline-e10/pexels-first-10s-conf-025/predictions.jsonl --output-dir /data/inference/ppe-baseline-e10/pexels-first-10s-associated
```

Convert direct per-worker violation evidence into deduplicated candidate events using:

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.temporal_violations --associations /data/inference/ppe-baseline-e10/pexels-first-10s-associated/associations.jsonl --output-dir /data/inference/ppe-baseline-e10/pexels-first-10s-temporal-w5-t3 --window-size 5 --evidence-threshold 3 --cooldown-ms 10000 --maximum-opposite-evidence 0
```

Validate supported candidate payloads without writing to PostgreSQL using:

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.publish_candidate_events --candidates /data/inference/ppe-baseline-e10/pexels-first-10s-temporal-w5-t3/candidate_events.jsonl --output-dir /data/inference/ppe-baseline-e10/pexels-first-10s-publish-dry-run --base-occurred-at 2026-08-15T10:00:00+00:00 --api-url http://api:8000
```

Only after inspecting the dry-run output, repeat with a new output directory and append `--send` to publish supported candidates.

Process the complete PPE topic through ByteTrack, worker association, temporal rules, and MinIO Gold with:

```powershell
docker compose --profile tools run --rm ingestion python -m app.process_ppe_stream --input-topic safesite.ppe.detections --track-topic safesite.tracks --candidate-topic safesite.candidate-violations --group-id lesson-19-your-name --output-dir /data/streaming/lesson-19-your-name --tracking-model /data/models/yolo26n.pt --max-messages 30 --tracking-confidence 0.25 --image-size 640 --device cpu --window-size 5 --evidence-threshold 3 --cooldown-ms 10000 --maximum-opposite-evidence 0
```

Publish confirmed Kafka candidates safely through FastAPI to PostgreSQL with:

```powershell
docker compose --profile tools run --rm ingestion python -m app.consume_candidate_events --topic safesite.candidate-violations --dead-letter-topic safesite.candidate-violations.dlq --group-id lesson-20-your-name --output-dir /data/streaming/lesson-20-your-name --base-occurred-at 2026-08-20T10:00:00+00:00 --api-url http://api:8000 --max-messages 1 --max-attempts 3 --retry-backoff-seconds 1
```

Run the complete isolated streaming architecture with one command:

```powershell
.\scripts\run_streaming_demo.ps1
```

Candidate delivery is disabled by default. Use `-SendCandidates` only after reviewing confirmed candidates.

Run the complete live streaming profile:

```powershell
docker compose --profile streaming up -d --build
```

This starts timestamped camera ingestion, PPE inference, multi-camera tracking,
candidate-to-API delivery, and health/lag monitoring. Configure the camera source,
camera ID, topic names, groups, thresholds, and model paths in `.env`.

## Documentation synchronization rule

Whenever a project file is added, removed, or meaningfully changed:

1. Update `docs/FILE_CATALOG.md` with the file's role and latest change.
2. Update the matching entry in `scripts/generate_file_catalog_pdf.py`.
3. Regenerate `output/pdf/SafeSite_AI_File_Catalog.pdf`.
4. Render and visually inspect the PDF before committing.

## Project rule

For every component, follow this loop:

```text
understand -> tiny exercise -> implement -> observe -> explain aloud
```

If you cannot explain a component without reading the code, it is not finished yet.
