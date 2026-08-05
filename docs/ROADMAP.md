# SafeSite AI: 28-Day Roadmap

## The realistic target

At the end of one month, the required demo is:

```text
video file -> sampled frames -> PPE detection + tracking -> violation event
           -> PostgreSQL -> FastAPI -> dashboard
```

Kafka, MinIO, MLflow, data-quality checks, and a small grounded text-to-SQL assistant are added around that core only after the vertical path works. Airflow and a vision-language model are stretch goals.

The detected GPU is a GeForce GTX 1650 with 4 GB VRAM. Use a nano-sized YOLO model, small batches, and one GPU workload at a time. Do not make an 8B LLM or 7B vision-language model a dependency of the demo.

## Daily method

Plan for 3 to 5 focused hours per day:

- 45 minutes: learn one concept and write five sentences in your own words.
- 90 minutes: complete a tiny isolated exercise.
- 90 minutes: integrate it into SafeSite AI.
- 30 minutes: inspect logs/data and explain the flow aloud.
- 15 minutes: commit one coherent change and write what you learned.

## Week 1 - Foundations and a working data slice

**Outcome:** fake violations flow through an API into PostgreSQL, with tests and clear documentation.

### Day 1 - System mental model

- Draw the path of one violation from camera to dashboard.
- Learn process, port, container, image, volume, and network.
- Run the initial Postgres + FastAPI stack.
- Complete `docs/LESSON_01.md`.

### Day 2 - PostgreSQL and SQL

- Learn tables, rows, primary keys, constraints, and indexes.
- Read `database/init/001_schema.sql` line by line.
- Write queries using `WHERE`, `GROUP BY`, `ORDER BY`, and time filters.
- Explain why event data belongs in PostgreSQL while video does not.

### Day 3 - HTTP and FastAPI

- Learn request, response, method, route, status code, and JSON.
- Trace `POST /violations` from Pydantic validation to SQL insertion.
- Add one useful filter to `GET /violations`.
- Use Swagger at `/docs` instead of treating the API as a black box.

### Day 4 - Contracts and testing

- Learn unit tests versus integration tests.
- Write API tests for valid input, invalid confidence, and filtering.
- Intentionally break a schema constraint and study the failure.
- Freeze version 1 of the violation event contract.

### Day 5 - Docker deeply

- Explain every line of `compose.yaml` and the API `Dockerfile`.
- Inspect `docker compose ps`, `logs`, and the Postgres volume.
- Rebuild the API and observe what changes and what persists.
- Practice diagnosing one failed health check.

### Day 6 - Video fundamentals

- Learn frame, FPS, resolution, codec, and sampling.
- Read a local video with OpenCV and save one frame per second.
- Measure how resolution and sampling rate change processing cost.

### Day 7 - Review and interview drill

- Rebuild the week from a blank diagram.
- Answer the Week 1 questions at the end of this file.
- Record a two-minute explanation of the current architecture.
- Fix documentation gaps, not new features.

## Week 2 - Computer vision core

**Outcome:** a local video produces deduplicated PPE violation events.

### Days 8-9 - Object detection

- Learn classification versus detection, bounding boxes, confidence, IoU, precision, recall, and mAP.
- Run a pretrained nano YOLO model on images and video.
- Inspect false positives and false negatives manually.

### Days 10-11 - PPE fine-tuning

- Prepare a small, clean dataset with train/validation/test splits.
- Fine-tune a nano model with image size and batch size chosen for 4 GB VRAM.
- Save parameters, metrics, confusion matrix, and example predictions.
- Prefer a measured baseline over chasing a perfect score.

### Day 12 - Tracking

- Learn tracking-by-detection and why detections alone overcount incidents.
- Run ByteTrack and inspect stable IDs and ID switches.
- Define a violation episode: same camera + track + type over consecutive frames.

### Days 13-14 - CV integration

- Convert model outputs into the versioned violation contract.
- Add debouncing so one worker creates one event, not hundreds.
- Save evidence frames locally, then store their URI in PostgreSQL.
- Demonstrate video -> database -> API end to end.

## Week 3 - Streaming and data engineering

**Outcome:** ingestion and inference are separate services connected by a broker; evidence is organized as a data lake.

### Days 15-16 - Messaging

- Learn producer, consumer, topic, partition, offset, and consumer group.
- First send tiny JSON messages through Kafka.
- Send frame references and metadata, not large encoded frames, unless measurement proves otherwise.
- If Kafka consumes more than two days, use Redis Streams and document the trade-off.

### Days 17-18 - Ingestion service

- Separate video reading from inference.
- Sample frames, attach camera ID and timestamps, and publish messages.
- Add structured logs and graceful reconnection behavior.

### Day 19 - MinIO and medallion layers

- Learn object storage, buckets, keys, and immutable raw data.
- Store raw clips/frames in bronze and annotated evidence + JSON in silver.
- Keep PostgreSQL as the structured event source of truth.

### Days 20-21 - Reliability review

- Test a slow consumer, broker restart, invalid event, and duplicate event.
- Measure throughput, queue lag, inference time, and dropped frames.
- Update the architecture diagram to match reality.

## Week 4 - Product, MLOps, and interview preparation

**Outcome:** a stable, explainable demo with monitoring and strong documentation.

### Days 22-23 - Dashboard

- Build Streamlit cards for total violations and compliance trends.
- Add filters by camera, time, and violation type.
- Show recent evidence frames and API errors clearly.

### Day 24 - MLflow

- Log training parameters, metrics, model artifact, and dataset version.
- Compare at least two runs and select a model using evidence.
- Explain reproducibility and model registry in plain language.

### Day 25 - Data quality and drift

- Validate nulls, allowed violation types, confidence range, and timestamps.
- Compare brightness, blur, and confidence distributions across videos.
- Distinguish data drift from model-quality degradation.

### Day 26 - Grounded assistant, optional

- Use a small local model or a rule-based fallback for text-to-SQL.
- Allow read-only `SELECT` queries only and display generated SQL.
- Test a fixed set of questions and reject unsupported requests.
- Skip the vision-language model if it threatens demo stability.

### Day 27 - Hardening

- Start the whole MVP from a clean machine state.
- Run a 30-minute demo and record CPU, RAM, GPU, and failures.
- Fix only demo-critical issues.

### Day 28 - PFE package

- Record a three-to-five-minute demo.
- Finish README, architecture, metrics, limitations, and future work.
- Prepare a resume project paragraph and ten interview answers.
- Practice a five-minute whiteboard explanation without notes.

## Scope priorities

### Must work

- One video source.
- Helmet and vest violation detection.
- Tracking and violation deduplication.
- PostgreSQL, FastAPI, and dashboard.
- Reproducible Docker setup and measured model evaluation.

### Should work

- Kafka or a documented Redis Streams fallback.
- MinIO bronze and silver storage.
- MLflow experiment tracking.
- Basic data-quality and drift report.

### Stretch

- Two simultaneous camera streams.
- Airflow scheduling.
- Local text-to-SQL assistant.
- Vision-language frame description.

## Interview questions you must answer

1. Why is the system event-driven instead of one large Python script?
2. Why does Kafka carry metadata or references instead of being the data lake?
3. Why are video evidence and structured events stored differently?
4. How does tracking prevent duplicate violations?
5. What does mAP measure, and what can it hide?
6. What happens when inference is slower than ingestion?
7. How do database constraints protect data quality?
8. How would this architecture change for 100 real cameras?
9. How do you prevent a text-to-SQL agent from modifying data?
10. What failed during the project, and what evidence guided your fix?

