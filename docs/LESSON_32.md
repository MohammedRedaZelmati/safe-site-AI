# Lesson 32 - The Complete SafeSite Architecture

## One event from camera to dashboard

Imagine camera 2 sees one worker without a helmet.

1. **Camera ingestion** samples a frame and records `camera_id` plus absolute capture time.
2. **MinIO Bronze** stores the image bytes.
3. **Kafka** publishes a small message containing metadata and the MinIO URI.
4. **YOLO PPE inference** downloads the frame, finds PPE objects, stores annotated evidence in MinIO Silver, and publishes detections.
5. **ByteTrack** gives each visible worker a temporary track ID scoped to that camera.
6. **Association rules** connect PPE detections to the correct worker box.
7. **Sliding-window rules** require repeated direct evidence and apply cooldown, preventing one noisy frame or one long episode from creating many alerts.
8. **Candidate delivery** sends supported events to FastAPI and retries safely.
9. **FastAPI and PostgreSQL** validate the contract, generate the database ID, and reject duplicate event keys.
10. **Streamlit** reads the API and shows incidents, evidence, health, lag, quality, drift, and grounded answers.
11. **Gold analytics and Airflow** build daily Parquet tables, then run quality checks in the correct order.
12. **MLflow** records model settings, metrics, artifacts, comparisons, and registry versions.
13. **LangGraph plus Ollama** answer approved read-only questions; Qwen describes selected evidence frames.

## Why the system is separated

Each service has one main responsibility. If inference slows down, Kafka keeps pending work. If the dashboard stops, ingestion can continue. If Ollama is unavailable, safety detection still works. This separation improves scaling, failure isolation, and debugging.

## What is authoritative

- PostgreSQL is the structured event source of truth.
- MinIO is the source of image and video evidence.
- Kafka transports ordered work and events; it is not the permanent data lake.
- YOLO plus deterministic temporal rules create candidates.
- The VLM explains evidence but does not decide incidents.
- MLflow records experiments but does not automatically promote a weak model.

## What the project proves

- a 30-frame Kafka/MinIO/CV/API streaming run completed;
- PPE and tracking workers each processed all 30 frames;
- duplicate-safe candidate publication reached FastAPI and PostgreSQL;
- three Gold Parquet tables passed a 12-check quality gate;
- Great Expectations passed 21 event checks;
- drift monitoring compared brightness, sharpness, and confidence;
- MLflow compared two runs and registered an experimental candidate;
- the agent's real database role allowed `SELECT` and rejected `DELETE`;
- Llama answered a grounded database question;
- Qwen described a real evidence frame;
- one Compose file and one PowerShell launcher connect the complete architecture.

## What the project does not claim

The current PPE model is an experimental baseline, not a production safety system. The proofs demonstrate architecture, traceability, and engineering controls. Production deployment still requires stronger labeled construction data, better violation recall, longer load tests, authentication, secrets management, TLS, and operational review.

## One-command start

```powershell
.\scripts\run_final_architecture.ps1 -IncludeAirflow
```

Without the heavier Airflow service:

```powershell
.\scripts\run_final_architecture.ps1
```

## Five-minute interview structure

1. State the problem: convert construction video into traceable PPE incidents.
2. Follow one event through the 13 steps above.
3. Explain Kafka versus MinIO versus PostgreSQL.
4. Explain tracking, the sliding window, and idempotency.
5. Show evidence: tests, JSON reports, Parquet quality, MLflow, and read-only agent proof.
6. End honestly: architecture complete, model quality still experimental.

