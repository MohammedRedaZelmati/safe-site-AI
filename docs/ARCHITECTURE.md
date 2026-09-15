# Architecture Explained From One Event

The easiest way to understand SafeSite AI is to follow one worker who is not wearing a helmet.

## 1. Video source

A video file behaves like a simulated camera. Later, MediaMTX can expose looped files as RTSP streams, but inference should not care whether frames came from a file or a physical camera.

**Output:** pixels plus camera identity and capture time.

## 2. Ingestion

The ingestion service decodes the stream and samples frames. A 25 FPS camera does not require 25 PPE checks every second; sampling reduces compute while preserving useful evidence.

**Output contract:** frame ID, camera ID, capture timestamp, and frame location.

## 3. Message broker

Kafka separates ingestion speed from inference speed. The producer publishes work, and the inference consumer processes it independently. Kafka is a durable queue and event log, not permanent video storage.

**Key question:** what happens to queue lag when inference is slower than ingestion?

## 4. Detection and tracking

YOLO answers: "what objects are visible, where are they, and with what confidence?" ByteTrack answers: "is this the same detected person as in the previous frame?"

A policy layer then decides whether missing PPE is a real violation. Requiring the condition for several consecutive frames reduces noisy one-frame alerts.

**Output contract:** one violation episode with camera, anonymous track ID, type, time, confidence, and evidence URI.

## 5. Storage

Different data has different storage needs:

| Data | Store | Reason |
|---|---|---|
| Raw clips and frames | MinIO bronze | Large immutable objects |
| Annotated frames and detection JSON | MinIO silver | Reproducible evidence |
| Violation events | PostgreSQL | Filters, joins, constraints, analytics |
| Daily aggregates | Parquet gold | Fast columnar analytics |

The URI in PostgreSQL connects an event to its evidence without putting image bytes inside analytical rows.

## 6. API and dashboard

FastAPI validates requests and exposes stable endpoints. Streamlit calls those endpoints to display KPIs and recent incidents. The dashboard should not connect directly to every internal service.

## 7. MLOps, monitoring, orchestration, and agent

MLflow records how a model was trained and evaluated. Great Expectations checks event contracts, and the drift job compares brightness, sharpness, and confidence distributions. Airflow schedules Gold aggregation before its quality gate. The LangGraph assistant uses only approved parameterized `SELECT` queries and a PostgreSQL role that cannot write. Ollama provides local Llama text answers and Qwen-VL frame descriptions; neither language model is allowed to create authoritative incidents.

The current local MLOps block records the ten-epoch PPE baseline in an MLflow
experiment. SQLite stores run metadata, a local artifact directory stores reports
and the packaged weight, and the model registry assigns immutable version `1` the
`candidate` alias. It intentionally has no `champion` alias because its violation
recall is not production-ready. A shared deployment should replace the local
stores with PostgreSQL and object storage while preserving the same run and model
contracts.

The current analytics block converts detailed Gold JSON records into Parquet frame,
worker, and daily-camera tables. A 12-check quality gate must pass before those
tables are trusted. The daily Airflow DAG orders aggregation before validation and
stops when either task fails.

## Completed MVP architecture

```text
real-image video fixture
        |
        v
timestamped frame sampling (5 FPS)
        |
        +--------------------+
        v                    v
YOLO person tracking     PPE YOLO detection
        |                    |
        +----------+---------+
                   v
          person-to-PPE association
                   |
                   v
       sliding-window candidate events
                   |
                   v
      dry-run-first publisher -> FastAPI
                                    |
                                    v
                     PostgreSQL unique event key
                                    |
                                    v
                    Streamlit API-only dashboard
```

One PowerShell command runs the complete local path. Intermediate JSONL files
make every decision inspectable instead of hiding the pipeline in one function.

## MVP boundary

The MVP proves software integration, event traceability, safe retries, and a
usable monitoring interface. It does not prove production detection quality.
The current PPE baseline has weak violation recall and the deterministic test
video is derived from one held-out real image, not continuous camera footage.

## Final large architecture

```text
RTSP cameras -> ingestion -> Kafka frame/event topics -> GPU inference workers
      |            |                    |                    |
      |            +-> MinIO bronze     |                    +-> MinIO silver
      |                                 v
      +-------------------------- schema-managed events
                                        |
                        PostgreSQL + Parquet gold aggregates
                                        |
                        FastAPI -> Streamlit -> alerts
                                        |
                 Airflow + MLflow + data quality + model registry
                                        |
                       read-only grounded assistant + VLM context
```

The final architecture preserves the MVP contracts while replacing local file
handoffs with durable messaging and object storage. Every box is mapped to source
and proof in `docs/FINAL_ARCHITECTURE.md`.

## Current long-running architecture

```text
camera/video simulation -- captured_at --> MinIO Bronze + Kafka raw
                                                |
                                                v
                                  continuous PPE inference
                                   MinIO Silver + Kafka PPE
                                                |
                                                v
                           camera-isolated ByteTrack + temporal rules
                                    MinIO Gold + Kafka candidates
                                                |
                                                v
                         continuous FastAPI delivery -> PostgreSQL

MinIO Gold JSON -> Parquet frame/worker/daily tables -> quality gate
                         ^
                         |
                   daily Airflow DAG

heartbeats + committed offsets -> lag monitor -> Streamlit alerts
```

Kafka uses `camera_id` as the key. This preserves per-camera partition order while
consumer groups distribute partitions across worker replicas. Absolute `captured_at`
time travels through every stage and becomes PostgreSQL `occurred_at`; missing live
event time is dead-lettered rather than guessed.

The Parquet job currently reads the tracking worker's mounted Gold JSON mirror.
The DAG contract is ready for Airflow deployment, and the lighter Compose
`analytics` profile exposes the same commands. The Block 28 proof ran those Python
modules directly after the Docker image built because the local Docker engine
stopped accepting new container-creation requests.

The Block 29 proof runs independently of Docker. It reads the existing baseline
artifacts, records 12 parameters and 54 metrics, stores nine run artifacts,
registers `SafeSite-PPE-Detector` version `1` as `candidate`, verifies SQLite
integrity, and serves the local MLflow UI successfully.
