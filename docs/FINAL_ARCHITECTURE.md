# SafeSite AI - Final Architecture

## Completion statement

The repository implements every layer in the target architecture: simulated video ingestion, Kafka streaming, MinIO Bronze/Silver/Gold storage, YOLO PPE inference, ByteTrack tracking, temporal violation rules, PostgreSQL, FastAPI, Streamlit, Airflow, Great Expectations, drift monitoring, MLflow, a read-only LangGraph assistant, and Ollama text/vision models.

The machine-readable completion audit is `data/final/final-architecture-proof.json`. It contains 12 passing architecture checks and the evidence used by each check.

## Final flow

```text
video / simulated cameras
        |
        v
camera ingestion ---- frame bytes ----> MinIO Bronze
        |
        +---- frame URI + metadata ----> Kafka raw topic
                                             |
                                             v
                                      YOLO PPE worker
                                      |             |
                               MinIO Silver     Kafka PPE
                                                       |
                                                       v
                                      ByteTrack + PPE association
                                                       |
                                               temporal rules
                                                       |
                               MinIO Gold <---- Kafka candidates
                                                       |
                                                       v
                                             candidate delivery
                                                       |
                                                       v
                                           FastAPI -> PostgreSQL
                                               |            |
                                               v            +-> read-only LangGraph agent
                                           Streamlit                 |
                                               ^                 Ollama Llama
                                               |                 Ollama Qwen-VL
                    drift + Great Expectations + worker health

MinIO Gold -> Airflow -> Parquet aggregation -> quality gate
training/evaluation -> MLflow runs -> comparison -> experimental registry candidate
```

## Architecture matrix

| Diagram layer | Implementation | Verified evidence |
|---|---|---|
| Video sources | `services/ingestion/app/stream_camera.py` | timestamped multi-camera fixtures and streaming summaries |
| Ingestion | `publish_frames.py`, `stream_camera.py` | 30 raw frame messages |
| Kafka | topics and consumer groups in `compose.yaml` | raw/PPE/track/candidate counts and lag reports |
| MinIO data lake | Bronze frame upload, Silver detections, Gold event JSON | streaming and Gold proof artifacts |
| CV inference | `infer_frame_events.py`, `worker_runtime.py` | 30 PPE frames processed |
| Tracking | ByteTrack in `process_ppe_stream.py` and workers | 30 tracked frames, 14 temporary IDs |
| Temporal rules | `temporal_violations.py` | repeated-evidence and cooldown tests |
| Serving | FastAPI plus PostgreSQL migrations | healthy DB and duplicate-safe publication |
| Dashboard | `services/dashboard/app.py` | violation-first run decision, evidence image, human-review records, and optional technical panels |
| Gold analytics | aggregation and 12-check validator | 3 frame, 6 worker, and 3 daily rows |
| Airflow | `safesite_gold_daily.py` | aggregation ordered before validation |
| Great Expectations | `validate_events.py` | 21 expectations, zero failures |
| Drift | `analyze_drift.py` | brightness, sharpness, confidence PSI |
| MLflow | tracking, comparison, model registry | two compared runs and candidate version 1 |
| Text agent | LangGraph approved-query graph | real read-only PostgreSQL and Ollama proof |
| Vision support | Qwen2.5-VL through Ollama | real evidence-frame description |

## Runtime profiles

`compose.yaml` contains 18 services and separates optional workloads into profiles:

- core: PostgreSQL, FastAPI, Kafka, MinIO;
- `streaming`: continuous ingestion, inference, tracking, delivery, and monitoring;
- `ui`: Streamlit dashboard;
- `agent`: LangGraph API connected to host Ollama;
- `mlops`: MLflow UI and tracking server;
- `monitoring`: drift and Great Expectations jobs;
- `analytics`: Gold Parquet aggregation;
- `orchestration`: Airflow;
- `test`: API integration tests.

## Start and inspect

```powershell
Copy-Item .env.example .env
.\scripts\run_final_architecture.ps1 -IncludeAirflow
```

Open:

- FastAPI: `http://localhost:8000/docs`
- Agent API: `http://localhost:8010/docs`
- Dashboard: `http://localhost:8502`
- MLflow: `http://localhost:5000`
- Airflow: `http://localhost:8080`
- MinIO console: `http://localhost:9001`

Run the evidence audit:

```powershell
services/mlops/.venv/Scripts/python.exe scripts/verify_final_architecture.py --full-compose-replay
```

Use `--full-compose-replay` only after `scripts/run_final_architecture.ps1 -IncludeAirflow` completes successfully in the current session. With this flag, the audit also requires all 13 long-running services to be active.

## Safety and trust boundaries

- Candidate writes pass through Pydantic validation and database constraints.
- A stable event key makes retries idempotent.
- Kafka offsets are committed only after successful processing or explicit dead-letter handling.
- Agent SQL is selected from an allowlist, validated, parameterized, and executed by a PostgreSQL role that cannot write.
- The vision-language model never creates authoritative violations.
- Model registry status remains experimental until evaluation supports promotion.

## Current runtime boundary

The full Compose topology is implemented and its components have verified proofs. The current session could not replay the complete Compose stack because the local Docker Desktop engine did not become ready, although its CLI is installed. The earlier Kafka/MinIO/CV/API run and the current isolated PostgreSQL/Ollama/MLflow/monitoring proofs are preserved in `data/`. This host-runtime condition does not change the source implementation, but a final live demo should begin by confirming `docker info` succeeds.

## Production work still required

- train and validate a stronger PPE model on representative labeled construction footage;
- add authentication, authorization, TLS, and managed secrets;
- replace local MLflow SQLite with shared PostgreSQL and object artifacts;
- add schema registry and formal Kafka compatibility rules;
- run sustained multi-camera load, recovery, and GPU capacity tests;
- define incident review and human-approval procedures.
