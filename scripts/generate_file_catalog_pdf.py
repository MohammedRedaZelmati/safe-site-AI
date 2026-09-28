from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "SafeSite_AI_File_Catalog.pdf"

PAGE_BREAK_BEFORE = {
    "database/init/001_schema.sql",
    "database/init/002_event_idempotency.sql",
    "database/init/003_agent_readonly.sql",
    "services/api/app/config.py",
    "services/ingestion/requirements.txt",
    "services/ingestion/app/__init__.py",
    "services/ingestion/app/consume_frames.py",
    "services/ingestion/app/infer_frame_events.py",
    "services/ingestion/app/process_ppe_stream.py",
    "services/ingestion/app/consume_candidate_events.py",
    "services/ingestion/app/stream_camera.py",
    "services/ingestion/app/monitor_streaming.py",
    "services/ingestion/app/aggregate_gold.py",
    "services/mlops/requirements.txt",
    "services/agent/requirements.txt",
    "services/monitoring/requirements.txt",
    "docs/DATA_SOURCES.md",
    "docs/REAL_DATASET_UPGRADE_PLAN.md",
    "docs/LESSON_03.md",
    "docs/LESSON_07.md",
    "docs/LESSON_08.md",
    "docs/LESSON_09.md",
    "docs/LESSON_10.md",
    "docs/LESSON_11.md",
    "docs/LESSON_12.md",
    "docs/LESSON_13.md",
    "docs/LESSON_14.md",
    "docs/LESSON_15.md",
    "docs/LESSON_16.md",
    "docs/LESSON_17.md",
    "docs/LESSON_18.md",
    "docs/LESSON_19.md",
    "docs/LESSON_20.md",
    "docs/LESSON_21.md",
    "docs/LESSON_22.md",
    "docs/LESSON_23.md",
    "docs/LESSON_24.md",
    "docs/LESSON_25.md",
    "docs/LESSON_26.md",
    "docs/LESSON_27.md",
    "docs/LESSON_28.md",
    "docs/LESSON_29.md",
    "docs/LESSON_30.md",
    "docs/LESSON_31.md",
    "docs/LESSON_32.md",
    "docs/FINAL_ARCHITECTURE.md",
    "docs/MVP_DEMO.md",
    "data/videos/external/pexels-32244795.mp4",
    "scripts/download_sample_video.py",
    "scripts/run_streaming_demo.ps1",
    "scripts/start_mlflow_ui.ps1",
    "scripts/run_final_architecture.ps1",
    "scripts/generate_file_catalog_pdf.py",
}

SECTIONS = [
    (
        "Root configuration",
        [
            (
                ".gitattributes",
                "Marks generated PDFs, images, videos, and model weights as binary Git artifacts.",
                "Prevents line-ending conversion, whitespace checks, and unreadable text diffs for binary files.",
                "Added binary rules for PDF, image, video, and PyTorch model artifacts.",
            ),
            (
                ".env.example",
                "Documents local configuration for PostgreSQL, FastAPI, MinIO, and streaming workers.",
                "Lets developers create a local .env file without committing real credentials.",
                "Added read-only agent, Ollama text and vision models, dashboard, and final-stack endpoints.",
            ),
            (
                ".gitignore",
                "Excludes local, generated, cached, secret, and heavy files from Git.",
                "Keeps commits focused on maintained source files.",
                "Excluded the generated verified tracking wheel alongside local binary dependencies.",
            ),
            (
                "README.md",
                "Provides the project overview, startup commands, learning links, and working rules.",
                "Acts as the main entry point for every developer and reviewer.",
                "Added the final one-command architecture, service URLs, completion guide, and Lessons 30-32.",
            ),
            (
                "compose.yaml",
                "Defines the complete 18-service SafeSite architecture and its optional profiles.",
                "Starts the architecture reproducibly and preserves data in named volumes.",
                "Added agent, dashboard, MLflow, monitoring, and Airflow profiles with explicit dependencies.",
            ),
        ],
    ),
    (
        "Database",
        [
            (
                "database/init/001_schema.sql",
                "Creates the violations table, constraints, indexes, and fake seed events.",
                "Establishes the structured event contract inside PostgreSQL.",
                "Initial camera, track, violation, confidence, evidence, and timestamp fields added.",
            ),
            (
                "database/init/002_event_idempotency.sql",
                "Adds the event key column, SHA256 format constraint, and unique partial index.",
                "Makes retries and concurrent publication safe at the authoritative database layer.",
                "Added idempotent migration statements for fresh and existing PostgreSQL volumes.",
            ),
            (
                "database/init/003_agent_readonly.sql",
                "Creates the local SafeSite assistant role with read-only transactions and SELECT-only privileges.",
                "Provides database-enforced protection even if an application-layer agent check fails.",
                "Added a repeatable local role, CONNECT and schema access, table SELECT, and default read-only mode.",
            ),
        ],
    ),
    (
        "API container",
        [
            (
                "services/api/Dockerfile",
                "Builds the container image that runs the FastAPI application.",
                "Packages Python, dependencies, source code, and the startup command reproducibly.",
                "Split the image into reusable base, runtime, and test build stages.",
            ),
            (
                "services/api/requirements.txt",
                "Declares the Python dependencies required by the API.",
                "Makes dependency installation repeatable in the container.",
                "FastAPI, Uvicorn, Psycopg, pool, and settings dependencies added.",
            ),
            (
                "services/api/requirements-dev.txt",
                "Declares dependencies used only by automated API tests.",
                "Keeps Pytest and HTTPX separate from the production runtime image.",
                "Added Pytest and HTTPX for black-box integration testing.",
            ),
        ],
    ),
    (
        "API application",
        [
            (
                "services/api/app/__init__.py",
                "Marks the app directory as a Python package.",
                "Makes imports such as app.main and app.schemas predictable.",
                "Initial package marker added.",
            ),
            (
                "services/api/app/config.py",
                "Loads the PostgreSQL connection URL from environment configuration.",
                "Separates deployment configuration from application logic.",
                "Initial Pydantic settings model and development default added.",
            ),
            (
                "services/api/app/database.py",
                "Creates and manages the asynchronous PostgreSQL connection pool.",
                "Reuses connections efficiently and manages them with the API lifecycle.",
                "Initial dictionary-row pool, startup wait, and shutdown functions added.",
            ),
            (
                "services/api/app/schemas.py",
                "Defines Pydantic request and response contracts for violations and statistics.",
                "Validates JSON fields, types, ranges, and allowed violation values.",
                "Exposed the optional 64-character database event key in violation responses.",
            ),
            (
                "services/api/app/main.py",
                "Defines the FastAPI application lifecycle and HTTP routes.",
                "Exposes health, create, list, filter, and summary operations over PostgreSQL.",
                "Added canonical SHA256 keys and conflict-safe 201-new/200-duplicate semantics.",
            ),
        ],
    ),
    (
        "API tests",
        [
            (
                "services/api/tests/test_time_filters.py",
                "Tests time filtering, invalid ranges, and SQL-injection resistance against the running stack.",
                "Proves that HTTP, validation, SQL, and PostgreSQL work correctly together.",
                "Added a fourth integration test proving duplicate POSTs create exactly one row.",
            ),
        ],
    ),
    (
        "Ingestion container",
        [
            (
                "services/ingestion/Dockerfile",
                "Builds the reproducible CPU environment for video ingestion and YOLO inference.",
                "Pins the official Ultralytics OpenCV, PyTorch, and YOLO runtime.",
                "Added offline installation of pinned Kafka, MinIO, and ByteTrack client wheels.",
            ),
            (
                "services/ingestion/requirements.txt",
                "Pins the Python clients and packages used for Kafka, MinIO, and Parquet.",
                "Makes the producer image repeatable instead of resolving new client versions during each build.",
                "Added pinned PyArrow for typed, compressed Parquet tables.",
            ),
        ],
    ),
    (
        "Ingestion application",
        [
            (
                "services/ingestion/app/__init__.py",
                "Marks the ingestion app directory as a Python package.",
                "Allows tools to run consistently with python -m app.<module>.",
                "Initial package marker added.",
            ),
            (
                "services/ingestion/app/generate_demo_video.py",
                "Generates a controlled MP4 with known timing, resolution, and frame count.",
                "Provides deterministic input without relying on personal or downloaded footage.",
                "Added configurable generation and a moving PPE-equipped worker scene.",
            ),
            (
                "services/ingestion/app/generate_violation_fixture.py",
                "Turns one held-out real image into a deterministic short MP4 with slow camera motion.",
                "Provides repeatable temporal input without claiming real-motion evaluation.",
                "Added validation, protected output, metadata sidecar, and an evaluation warning.",
            ),
            (
                "services/ingestion/app/build_violation_review_reel.py",
                "Compiles labelled no-helmet construction images into a review MP4, first-frame proof, and JSON summary.",
                "Gives the dashboard real labelled violation evidence while clearly separating it from continuous camera footage.",
                "Added deterministic video generation from the Construction-PPE no-helmet visual review set.",
            ),
            (
                "services/ingestion/app/sample_frames.py",
                "Samples video frames by time and writes JPEG evidence plus JSONL metadata.",
                "Establishes the ingestion contract later consumed by Kafka, MinIO, and YOLO.",
                "Added validation, time-based sampling, traceable names, and metadata records.",
            ),
            (
                "services/ingestion/app/detect_image.py",
                "Runs YOLO on one image and writes annotated JPEG and structured JSON outputs.",
                "Exposes classes, confidence scores, and boxes for later inference and event logic.",
                "Extracted shared detection serialization for identical single-image and batch box contracts.",
            ),
            (
                "services/ingestion/app/detect_frames.py",
                "Loads YOLO once and streams every image referenced by a JSONL frame manifest.",
                "Preserves camera and timestamp context while writing scalable visual and structured outputs.",
                "Added manifest validation, batch inference, shared boxes, output protection, counts, and timing.",
            ),
            (
                "services/ingestion/app/track_frames.py",
                "Runs YOLO and ByteTrack over ordered manifest frames and writes temporary object identities.",
                "Connects detections through time so violation logic can measure duration and avoid duplicate alerts.",
                "Added persistent tracking, visual and JSONL outputs, track coverage, spans, and timing.",
            ),
            (
                "services/ingestion/app/associate_ppe_tracks.py",
                "Associates supported PPE detections with stable person track IDs and exports evidence histories.",
                "Connects tracking and PPE inference without rerunning models or treating missing boxes as violations.",
                "Added body-region matching, one-owner selection, duplicate suppression, visuals, and summaries.",
            ),
            (
                "services/ingestion/app/temporal_violations.py",
                "Converts direct per-track violation evidence into deduplicated temporal candidate events.",
                "Separates noisy frame predictions from incidents with windows, opposite evidence, and cooldown.",
                "Extracted a reusable stateful temporal engine shared by offline and Kafka processing.",
            ),
            (
                "services/ingestion/app/publish_candidate_events.py",
                "Validates temporal candidates and optionally publishes supported events to FastAPI.",
                "Adapts video candidates while protecting PostgreSQL with dry runs and type filtering.",
                "Preferred candidate occurred_at with historical base time as a compatibility fallback.",
            ),
            (
                "services/ingestion/app/publish_frames.py",
                "Uploads sampled JPEGs to MinIO and publishes their validated metadata to Kafka.",
                "Creates the first asynchronous frame path while keeping large image bytes outside the broker.",
                "Added a validated starting sample index for resumable publication without earlier records.",
            ),
            (
                "services/ingestion/app/consume_frames.py",
                "Consumes validated frame events from Kafka and downloads their JPEG objects from MinIO.",
                "Gives inference a replayable, offset-controlled input without coupling it to the producer.",
                "Added version-2 validation for timezone-aware camera captured_at timestamps.",
            ),
            (
                "services/ingestion/app/infer_frame_events.py",
                "Consumes raw frame events, runs YOLO, stores Silver outputs, and publishes detection events.",
                "Turns asynchronous frame notifications into reproducible inference without blocking producers.",
                "Propagated captured_at, added heartbeats, and preserved bounded continuous processing.",
            ),
            (
                "services/ingestion/app/process_ppe_stream.py",
                "Consumes ordered PPE events, runs ByteTrack, associates PPE, evaluates temporal rules, and publishes outputs.",
                "Connects Silver detections to worker evidence, MinIO Gold, track events, and confirmed candidates.",
                "Added isolated three-camera state, absolute time, heartbeats, and safe per-event commits.",
            ),
            (
                "services/ingestion/app/consume_candidate_events.py",
                "Consumes confirmed Kafka candidates and publishes supported violations through FastAPI.",
                "Bridges asynchronous events to PostgreSQL with retries, duplicate handling, DLQ, and commit-last offsets.",
                "Added continuous delivery, occurred_at, heartbeats, and missing-time dead letters.",
            ),
            (
                "services/ingestion/app/stream_camera.py",
                "Samples camera, RTSP, or video sources and publishes timestamped Bronze frame events.",
                "Provides a long-running producer with object evidence, Kafka keys, and absolute event time.",
                "Added version-2 events, JPEG encoding, looping, pacing, deterministic IDs, and heartbeats.",
            ),
            (
                "services/ingestion/app/worker_runtime.py",
                "Atomically writes throttled worker heartbeat records.",
                "Provides one consistent liveness contract for every long-running service.",
                "Added worker status, processed counts, timestamps, and extensible details.",
            ),
            (
                "services/ingestion/app/monitor_streaming.py",
                "Monitors Kafka lag, heartbeats, FastAPI health, and MinIO liveness.",
                "Detects stuck workers, growing queues, stale services, and unavailable dependencies.",
                "Added partition lag, alerts, atomic reports, continuous checks, and degraded exits.",
            ),
            (
                "services/ingestion/app/aggregate_gold.py",
                "Builds typed frame, worker-evidence, and daily-camera Parquet tables from Gold JSON.",
                "Makes repeated analytics efficient while preserving event and evidence traceability.",
                "Added strict validation, Arrow schemas, Zstandard compression, atomic files, and summaries.",
            ),
            (
                "services/ingestion/app/validate_gold_quality.py",
                "Validates Gold Parquet schemas, identities, times, counts, relationships, and totals.",
                "Stops duplicated or inconsistent analytics data from being accepted silently.",
                "Added 12 named checks, JSON reports, and a failing exit code.",
            ),
            (
                "services/ingestion/app/run_gold_analytics.py",
                "Runs Gold aggregation and its quality gate as one command.",
                "Gives Compose one success boundary for both data creation and validation.",
                "Added combined reporting and quality failure propagation.",
            ),
            (
                "services/ingestion/app/render_yolo_labels.py",
                "Renders deterministic YOLO ground-truth samples as annotated images and contact sheets.",
                "Exposes box quality, class semantics, and domain mismatch before training consumes labels.",
                "Added seeded selection, class filtering, pixel conversion, protected outputs, and JSON indexes.",
            ),
            (
                "services/ingestion/app/train_ppe_baseline.py",
                "Runs protected and reproducible YOLO PPE training and exports a SafeSite metrics summary.",
                "Separates pipeline verification from model-quality claims while preserving exact settings.",
                "Added validation, absolute data config, deterministic arguments, protection, and JSON metrics.",
            ),
        ],
    ),
    (
        "Dashboard",
        [
            (
                "services/dashboard/Dockerfile",
                "Packages the Streamlit dashboard as a reproducible container.",
                "Lets the complete Compose stack run the UI without a host Python environment.",
                "Added the pinned dashboard runtime, source copy, health check, and port 8502 command.",
            ),
            (
                "services/dashboard/app.py",
                "Presents one professional real-video evidence frame with the no-vest decision, review confidence, precision, recall, and mAP50.",
                "Gives a PFE reviewer a simple visual safety decision without technical tables or distracting video playback.",
                "Changed the final demo to a frame-only no-vest evidence screen backed by real Pexels footage.",
            ),
            (
                "services/dashboard/requirements.txt",
                "Declares the Streamlit dependency used by the host dashboard.",
                "Keeps UI dependencies reproducible and separate from the API image.",
                "Added the supported Streamlit 1.x version range.",
            ),
        ],
    ),
    (
        "MLOps",
        [
            (
                "services/mlops/Dockerfile",
                "Packages the local MLflow tracking and registry server.",
                "Runs the same project database and artifact layout through Compose.",
                "Replaced the fragile local pip build with the official MLflow 3.15.2 image pinned by digest.",
            ),
            (
                "services/mlops/requirements.txt",
                "Pins the MLflow version used by the local tracking environment.",
                "Keeps MLOps dependencies isolated from API and inference runtimes.",
                "Added MLflow 3.15.2 for Block 29.",
            ),
            (
                "services/mlops/log_ppe_experiment.py",
                "Logs PPE settings, metrics, evidence, and a packaged model into MLflow.",
                "Connects one exact training result to reproducible artifacts and a registry version.",
                "Added hashes, 12 parameters, 54 metrics, nine artifacts, and candidate registration.",
            ),
            (
                "services/mlops/safesite_yolo_pyfunc.py",
                "Defines the model-from-code interface for packaged YOLO inference.",
                "Makes model loading inspectable and avoids fragile live-object serialization.",
                "Added validated image inputs, lazy Ultralytics loading, and JSON detections.",
            ),
            (
                "services/mlops/compare_ppe_runs.py",
                "Logs or reuses PPE experiments and ranks completed MLflow runs by explicit metrics.",
                "Makes candidate selection evidence-based while ignoring failed partial runs.",
                "Added safe metric names, mAP50-95 and recall ranking, and an atomic comparison report.",
            ),
            (
                "services/mlops/test_compare_ppe_runs.py",
                "Tests MLflow metric sanitization and deterministic run-ranking rules.",
                "Prevents model selection from changing silently when metrics tie or contain unsafe names.",
                "Added three unit tests for ranking, recall tie-breaking, and MLflow-safe names.",
            ),
            (
                "services/mlops/README.md",
                "Documents the no-Docker MLflow workflow, stores, registry policy, and UI.",
                "Lets developers reproduce and understand the local MLOps proof.",
                "Added two-run comparison commands and the experimental promotion boundary.",
            ),
        ],
    ),
    (
        "Grounded agent",
        [
            (
                "services/agent/Dockerfile",
                "Packages the FastAPI and LangGraph assistant service.",
                "Keeps agent dependencies and its port separate from the safety-event API.",
                "Added the pinned image, health check, data mount contract, and port 8010 runtime.",
            ),
            (
                "services/agent/requirements.txt",
                "Pins FastAPI, LangGraph, Psycopg, HTTPX, Pillow, and Uvicorn for the agent.",
                "Makes text, database, and image interactions reproducible.",
                "Added exact versions verified by the local text, vision, and database proofs.",
            ),
            (
                "services/agent/run_windows.py",
                "Starts Uvicorn with a Windows selector event loop.",
                "Avoids the Psycopg incompatibility with the default Proactor loop during local proofs.",
                "Added an explicit SelectorEventLoop runner and programmatic Uvicorn startup.",
            ),
            (
                "services/agent/README.md",
                "Documents the assistant flow, safety layers, endpoints, models, and proof commands.",
                "Explains why the service is grounded and why the VLM cannot authorize violations.",
                "Added read-only database and Ollama text/vision instructions.",
            ),
            (
                "services/agent/app/__init__.py",
                "Marks the agent application directory as a Python package.",
                "Supports stable module imports in local and container runtimes.",
                "Added the agent package marker.",
            ),
            (
                "services/agent/app/schemas.py",
                "Defines request, answer, query-plan, and vision response contracts.",
                "Keeps LangGraph state and HTTP payloads explicit and validated.",
                "Added grounded-answer metadata including SQL, parameters, rows, and provider.",
            ),
            (
                "services/agent/app/query_catalog.py",
                "Maps supported natural-language intents to approved parameterized SELECT templates.",
                "Prevents unrestricted model-generated SQL and blocks write vocabulary before database access.",
                "Added six deterministic analytical intents, exact allowlist validation, and table restrictions.",
            ),
            (
                "services/agent/app/database.py",
                "Manages the assistant PostgreSQL pool and read-only query transactions.",
                "Enforces read-only execution at both connection-role and transaction levels.",
                "Added health evidence for the current role and transaction_read_only setting.",
            ),
            (
                "services/agent/app/ollama.py",
                "Calls local Ollama chat and vision endpoints.",
                "Separates model serving from agent orchestration and supports deterministic fallback behavior.",
                "Added model health, grounded row summaries, base64 images, and uncertainty-aware PPE prompts.",
            ),
            (
                "services/agent/app/graph.py",
                "Defines the LangGraph plan, validate, execute, and answer workflow.",
                "Makes every agent decision stage explicit, testable, and observable.",
                "Added approved-query execution and deterministic answers when Ollama is unavailable.",
            ),
            (
                "services/agent/app/main.py",
                "Exposes health, grounded question, and evidence-description HTTP endpoints.",
                "Provides one safe API around LangGraph, PostgreSQL, Ollama, and local evidence files.",
                "Added 422 rejection, verified JPEG/PNG path confinement, and supporting-context warnings.",
            ),
            (
                "services/agent/tests/test_agent.py",
                "Tests approved queries, rejections, fallback answers, HTTP contracts, and image-path safety.",
                "Proves unsafe requests stop before database execution and every catalog plan validates.",
                "Added seven passing agent tests.",
            ),
        ],
    ),
    (
        "Monitoring and data quality",
        [
            (
                "services/monitoring/Dockerfile",
                "Packages drift and Great Expectations jobs.",
                "Keeps monitoring dependencies separate and runnable through Compose profiles.",
                "Added the pinned Python monitoring runtime and mounted-project execution contract.",
            ),
            (
                "services/monitoring/requirements.txt",
                "Pins NumPy, Pillow, and Great Expectations.",
                "Makes image-distribution and event-quality checks reproducible.",
                "Added versions verified by the four monitoring tests and real reports.",
            ),
            (
                "services/monitoring/analyze_drift.py",
                "Compares image brightness, sharpness, and model-confidence distributions with PSI.",
                "Provides an early warning when current data differs from the reference data.",
                "Added stable, warning, and drift thresholds plus atomic JSON reporting.",
            ),
            (
                "services/monitoring/validate_events.py",
                "Runs Great Expectations against exported violation events.",
                "Stops downstream work when required fields, types, ranges, or uniqueness fail.",
                "Added 21 expectations and failure-propagating atomic reports.",
            ),
            (
                "services/monitoring/test_analyze_drift.py",
                "Tests stable and strongly shifted drift comparisons.",
                "Protects PSI behavior and classification thresholds from regression.",
                "Added two deterministic drift tests.",
            ),
            (
                "services/monitoring/test_validate_events.py",
                "Tests valid and invalid Great Expectations event batches.",
                "Proves bad confidence and unsupported violation types fail quality validation.",
                "Added two deterministic event-quality tests.",
            ),
            (
                "services/monitoring/README.md",
                "Documents drift interpretation, quality checks, commands, and limits.",
                "Prevents a drift signal from being misrepresented as measured model inaccuracy.",
                "Added the verified PSI and 21-expectation workflows.",
            ),
        ],
    ),
    (
        "Learning documentation",
        [
            (
                "docs/DATA_SOURCES.md",
                "Records provenance, licensing, retrieval details, measured metadata, and appropriate use for external data.",
                "Makes experiments legally traceable and reproducible without committing downloaded media.",
                "Added the SH17 PPE dataset candidate review, including its license boundary and missing-helmet inference limitation.",
            ),
            (
                "docs/REAL_DATASET_UPGRADE_PLAN.md",
                "Explains how to move from the current MVP proof to stronger real-data violation detection.",
                "Separates completed architecture work from remaining ML evidence work so the project story stays technically honest.",
                "Added the SH17 candidate assessment, dashboard proof status, model-readiness gap, and next upgrade steps.",
            ),
            (
                "docs/MODEL_SOURCES.md",
                "Records model provenance, runtime version, artifact hash, class limits, and license boundaries.",
                "Makes the baseline reproducible and prevents unknown weights from entering experiments.",
                "Added pinned lap wheel provenance, SHA256, platform, and offline installation rationale.",
            ),
            (
                "docs/ARCHITECTURE.md",
                "Explains the architecture by following one PPE violation event.",
                "Builds a mental model connecting every planned system layer.",
                "Added the final agent, VLM, quality, drift, Airflow, and architecture completion flow.",
            ),
            (
                "docs/FINAL_ARCHITECTURE.md",
                "Maps every final diagram layer to its source, runtime profile, proof, and trust boundary.",
                "Provides the authoritative completion and demo reference for the full project.",
                "Updated the dashboard proof to describe its violation-first decision and human-review workflow.",
            ),
            (
                "docs/LESSON_01.md",
                "Contains the first guided lesson and practical exercises.",
                "Teaches Docker, networking, validation, persistence, and event flow.",
                "Initial Day 1 exercises and explanation checkpoint added.",
            ),
            (
                "docs/LESSON_02.md",
                "Contains the second guided lesson and implementation exercise.",
                "Teaches HTTP, async waiting, pooling, safe SQL, time filters, and tests.",
                "Initial Day 2 lesson and explanation checkpoint added.",
            ),
            (
                "docs/LESSON_03.md",
                "Contains the video-fundamentals lesson and frame-sampling exercise.",
                "Teaches FPS, resolution, codecs, timestamps, sampling, and JSONL metadata.",
                "Added the Day 3 lesson, Docker commands, contract, and checkpoint.",
            ),
            (
                "docs/LESSON_04.md",
                "Documents real-footage provenance, visual assessment, limitations, and data leakage.",
                "Teaches the difference between a smoke test and valid model evaluation.",
                "Added the Pexels workflow, 50-frame result, YOLO checklist, and video-level split rule.",
            ),
            (
                "docs/LESSON_05.md",
                "Documents the first real YOLO inference and its prerequisite detection concepts.",
                "Connects boxes, confidence, IoU, precision, recall, and mAP to actual outputs.",
                "Added the 50-frame workflow, confidence and throughput results, box scaling, and accuracy warning.",
            ),
            (
                "docs/LESSON_06.md",
                "Documents multi-object tracking concepts and the first ByteTrack continuity experiment.",
                "Teaches temporary IDs, association, lifecycle, event deduplication, and stability limits.",
                "Added the conceptual lesson, command, output contracts, and honest interpretation guidance.",
            ),
            (
                "docs/LESSON_07.md",
                "Documents PPE dataset selection, acquisition, structural and visual audits, balance, and limitations.",
                "Teaches why verified structure and sampled boxes still require domain-specific validation.",
                "Added reproducible visual review, measured samples, domain mismatch, and baseline-only decision.",
            ),
            (
                "docs/LESSON_08.md",
                "Documents the first PPE training smoke test, settings, outputs, metrics, and interpretation.",
                "Teaches why pipeline success and saved weights do not prove that a model is accurate.",
                "Added the CPU command, 113-image run, full validation, outputs, and quality conclusion.",
            ),
            (
                "docs/LESSON_09.md",
                "Documents the ten-epoch PPE baseline, trends, class metrics, visuals, and readiness decision.",
                "Teaches how losses, mAP, recall, confusion matrices, and predictions support one conclusion.",
                "Linked the baseline conclusion to the completed real-video evaluation in Lesson 10.",
            ),
            (
                "docs/LESSON_10.md",
                "Documents trained PPE inference on 50 unseen construction frames at two thresholds.",
                "Teaches generalization, flicker, duplicates, threshold trade-offs, and temporal event rules.",
                "Added frame coverage, duplicate counts, compliant-worker interpretation, and safe next steps.",
            ),
            (
                "docs/LESSON_11.md",
                "Documents PPE-to-worker association and per-track evidence across 50 frames.",
                "Teaches stage separation, spatial matching, duplicate suppression, and unknown versus violation.",
                "Added the reproducible experiment, track measurements, architecture, limits, and safety rule.",
            ),
            (
                "docs/LESSON_12.md",
                "Documents temporal rules that convert repeated direct evidence into one candidate incident.",
                "Teaches windows, thresholds, opposite evidence, cooldown, independent keys, and contract limits.",
                "Added synthetic proofs, zero-event real-video result, outputs, API mismatch, and tuning limits.",
            ),
            (
                "docs/LESSON_13.md",
                "Documents the safe adapter from candidate JSONL to FastAPI and PostgreSQL.",
                "Teaches contract mapping, absolute time, dry runs, filtering, and database idempotency.",
                "Replaced race-prone pre-checks with event keys and PostgreSQL uniqueness.",
            ),
            (
                "docs/LESSON_14.md",
                "Explains the Kafka broker and MinIO object-storage infrastructure foundation.",
                "Teaches topics, partitions, offsets, lag, object tiers, listeners, KRaft, and persistence.",
                "Added the topic restart proof, MinIO health checks, addresses, and production limits.",
            ),
            (
                "docs/LESSON_15.md",
                "Explains the first real sampled-frame publication through MinIO and Kafka.",
                "Teaches object URIs, Kafka keys, upload ordering, delivery confirmation, and replay boundaries.",
                "Added the verified event contract, independent storage and broker proof, and consumer design.",
            ),
            (
                "docs/LESSON_16.md",
                "Explains the first Kafka consumer and its verified MinIO frame download.",
                "Teaches groups, offsets, lag, manual commits, at-least-once processing, and atomic files.",
                "Added the offset proof, zero lag, matching SHA256, reproduction command, and YOLO handoff.",
            ),
            (
                "docs/LESSON_17.md",
                "Explains the first complete Kafka, MinIO, and YOLO streaming inference event.",
                "Teaches Bronze-to-Silver processing, deterministic identity, model reuse, topics, and commits.",
                "Added the 11-person smoke test, Silver objects, event readback, limits, and reproduction command.",
            ),
            (
                "docs/LESSON_18.md",
                "Explains the complete 30-frame stream through the trained experimental PPE model.",
                "Teaches resumable publication, partition order, full-stream proof, classes, and missing evidence.",
                "Added 30-event and 60-object proof, 145-box results, zero lag, limits, and tracking handoff.",
            ),
            (
                "docs/LESSON_19.md",
                "Explains streamed tracking, PPE association, temporal evaluation, and Gold evidence.",
                "Teaches stateful processing, track continuity, unknown evidence, commits, and measured outputs.",
                "Added the 30-event run, 14 IDs, 80 associations, 60 Gold objects, and zero candidates.",
            ),
            (
                "docs/LESSON_20.md",
                "Explains how confirmed Kafka candidates reach FastAPI and PostgreSQL safely.",
                "Teaches HTTP adaptation, absolute time, retries, idempotency, DLQ, and offset boundaries.",
                "Added new-event, replay, and unsupported-type proofs with one row and zero source lag.",
            ),
            (
                "docs/LESSON_21.md",
                "Explains the complete isolated streaming run and its final checkpoint report.",
                "Teaches orchestration, topic isolation, candidate approval, verification, and failure boundaries.",
                "Added the ten-stage command, 30/30/30 Kafka proof, 30/60/60 storage proof, and guards.",
            ),
            (
                "docs/LESSON_22.md",
                "Explains monitoring saved streaming runs beside API-backed violation events.",
                "Teaches pipeline completeness, model accuracy, candidate approval, and persistence as separate ideas.",
                "Added run selection, stage and Kafka checkpoints, CV metrics, safety meaning, and limits.",
            ),
            (
                "docs/LESSON_23.md",
                "Explains independent continuous PPE inference and tracking worker services.",
                "Teaches service lifecycle, waiting, isolation, bounded memory, restart behavior, and commit safety.",
                "Added streaming services, 35-second idle proof, one-frame regression, and the delivery boundary.",
            ),
            (
                "docs/LESSON_24.md",
                "Explains continuous camera ingestion and absolute event time.",
                "Teaches Bronze publication, version 2, captured_at, monotonic time, and loop-safe simulation.",
                "Added the three-camera timestamp proof and hardware-time limitation.",
            ),
            (
                "docs/LESSON_25.md",
                "Explains multi-camera Kafka partitioning and isolated tracking state.",
                "Teaches key order, shared partitions, scaling, and camera-scoped identities.",
                "Added the three-camera, six-identity, zero-collision proof.",
            ),
            (
                "docs/LESSON_26.md",
                "Explains always-on candidate delivery with correct absolute event time.",
                "Teaches timestamp propagation, retries, idempotency, commits, and missing-time DLQ safety.",
                "Added exact PostgreSQL time and missing-time dead-letter proofs.",
            ),
            (
                "docs/LESSON_27.md",
                "Explains heartbeats, Kafka lag, dependency checks, and alerts.",
                "Teaches why process liveness alone cannot prove pipeline health.",
                "Added five-service health, zero-restart, 1/1/0 lag, and stale-alert proofs.",
            ),
            (
                "docs/LESSON_28.md",
                "Explains Gold Parquet aggregation, data quality, and daily Airflow orchestration.",
                "Teaches evidence versus analytics, quality gates, and workflow scheduling.",
                "Added the three-table design, 12-check proof, duplicate rejection, and commands.",
            ),
            (
                "docs/LESSON_29.md",
                "Explains MLflow runs, stores, model versions, aliases, and promotion boundaries.",
                "Teaches model traceability using the verified SafeSite baseline.",
                "Added the local SQLite proof, packaging workflow, counts, and honest limitations.",
            ),
            (
                "docs/LESSON_30.md",
                "Explains Great Expectations event validation and PSI-based distribution drift.",
                "Teaches the difference between structural data quality, input change, and measured accuracy.",
                "Added the real 21-check quality result and three-distribution drift interpretation.",
            ),
            (
                "docs/LESSON_31.md",
                "Explains the read-only LangGraph agent and Ollama text/vision support.",
                "Teaches grounding, SQL allowlists, database permissions, fallback answers, and VLM limits.",
                "Added real SELECT/DELETE, HTTP 422, Llama answer, and Qwen frame-description proofs.",
            ),
            (
                "docs/LESSON_32.md",
                "Walks one event through the complete architecture in simple language.",
                "Provides a final mental model and a five-minute interview explanation structure.",
                "Added the 13-step flow, authority boundaries, completion evidence, and honest limitations.",
            ),
            (
                "docs/MVP_DEMO.md",
                "Provides the one-command demo, checkpoints, results, limits, and interview explanation.",
                "Turns the local components into a reproducible and honest portfolio demonstration.",
                "Added the validated 30-frame run, duplicate replay, dashboard, and quality warning.",
            ),
            (
                "docs/ROADMAP.md",
                "Defines the realistic 28-day learning and implementation plan.",
                "Protects the deadline using must-have, should-have, and stretch priorities.",
                "Initial plan adapted for a GTX 1650 with 4 GB VRAM.",
            ),
            (
                "docs/FILE_CATALOG.md",
                "Provides the human-readable source catalog for maintained project files.",
                "Keeps file responsibilities and meaningful changes understandable.",
                "Added MLflow services, the UI launcher, Lesson 29, and Block 29 proof.",
            ),
        ],
    ),
    (
        "Orchestration",
        [
            (
                "orchestration/airflow/Dockerfile",
                "Builds the Airflow runtime used by the daily Gold workflow.",
                "Pins the scheduler image and adds the Parquet dependency required by SafeSite tasks.",
                "Added the Airflow 3.1 Python 3.12 base and requirements installation.",
            ),
            (
                "orchestration/airflow/requirements.txt",
                "Pins the PyArrow dependency used inside Airflow.",
                "Allows scheduled Gold tasks to read and write Parquet consistently.",
                "Added PyArrow 21.0.0.",
            ),
            (
                "orchestration/airflow/dags/safesite_gold_daily.py",
                "Defines daily Gold aggregation followed by quality validation in Airflow.",
                "Schedules analytics in the correct order and stops after task failure.",
                "Added a no-catchup, single-active-run DAG with compatible Bash imports.",
            ),
            (
                "orchestration/airflow/README.md",
                "Documents the environment, paths, and data mount required by the Gold DAG.",
                "Separates the deployment contract from the lighter local execution proof.",
                "Added task flow, runtime requirements, and the local Airflow boundary.",
            ),
        ],
    ),
    (
        "Data acquisition",
        [
            (
                "data/videos/external/pexels-32244795.mp4",
                "Stores the validated real Pexels construction-worker source video used for final evidence.",
                "Provides real footage for the no-vest dashboard proof instead of generated or image-built media.",
                "Downloaded the free Pexels scaffolding inspection video validated by the user.",
            ),
            (
                "data/final-demo/real-pexels-32244795/proof-no-vest.jpg",
                "Shows the professional frame-only no-vest evidence used by the final dashboard.",
                "Makes the real construction violation visually understandable without requiring video playback.",
                "Added a highlighted 2.0-second frame showing the worker with a helmet but no safety vest.",
            ),
            (
                "data/final-demo/summary.json",
                "Stores the real Pexels source, proof frame path, no-vest decision, and vest-class model metrics.",
                "Lets the dashboard render the professional evidence screen without hard-coded values.",
                "Changed the final demo metadata from no-helmet image-built video to real no-vest evidence.",
            ),
            (
                "data/evaluation/no-helmet-construction-proof/no-helmet-ground-truth-review.mp4",
                "Shows a curated labelled PPE missing-helmet example as the dashboard's primary violation proof reel.",
                "Gives the interface real ground-truth violation evidence while making clear it is not continuous camera footage.",
                "Added an 8-second MP4 from image1162 with 8 labelled no_helmet boxes.",
            ),
            (
                "data/evaluation/no-helmet-construction-proof/summary.json",
                "Records the curated proof reel source, selected image ID, label count, output paths, and limitation.",
                "Lets the dashboard load proof metadata without hard-coding sample counts or file names.",
                "Added traceable metadata for the dashboard's primary no-helmet proof.",
            ),
            (
                "data/evaluation/no-helmet-construction-proof/first-frame.jpg",
                "Provides a still fallback for the curated no-helmet proof reel.",
                "Keeps visual proof visible even when video playback is unavailable.",
                "Added the first rendered frame from the curated proof video.",
            ),
            (
                "data/evaluation/no-helmet-review/no-helmet-ground-truth-review.mp4",
                "Shows labelled real no-helmet dataset examples as a broader review reel.",
                "Gives the dashboard visible violation proof without relying on fake database records.",
                "Added a 24-second MP4 from 12 labelled Construction-PPE images with 21 no_helmet boxes.",
            ),
            (
                "data/evaluation/no-helmet-review/summary.json",
                "Records the review reel source, sample count, labels, output paths, and limitation.",
                "Makes the proof traceable and prevents confusion with continuous camera footage.",
                "Added the generated no-helmet review metadata used by the dashboard.",
            ),
            (
                "data/evaluation/no-helmet-review/first-frame.jpg",
                "Provides a still visual fallback from the no-helmet review reel.",
                "Keeps proof visible when browser video playback fails or is slow.",
                "Added the first rendered ground-truth review frame.",
            ),
            (
                "data/videos/synthetic/mixed-ppe-six-workers-source.png",
                "Provides a controlled source scene with exactly six workers and three visible PPE violations.",
                "Gives demonstrations obvious ground truth without presenting generated media as real footage.",
                "Added three compliant workers, two without helmets, and one without a vest.",
            ),
            (
                "data/videos/synthetic/mixed-ppe-six-workers-10s.mp4",
                "Animates the controlled scene as a ten-second, 10 FPS video for full-pipeline tests.",
                "Exercises sampling, Kafka, MinIO, inference, tracking, and temporal decisions with known violations.",
                "Added the controlled video; six tracks were maintained but zero candidates were confirmed.",
            ),
            (
                "data/videos/synthetic/mixed-ppe-six-workers-10s.json",
                "Records synthetic provenance, video properties, worker count, and ground-truth violations.",
                "Prevents the fixture from being mistaken for real footage or an accuracy benchmark.",
                "Added counts for three compliant workers, two NO_HELMET cases, and one NO_VEST case.",
            ),
            (
                "scripts/download_sample_video.py",
                "Downloads the licensed Pexels sample video and verifies its SHA256 hash.",
                "Reproduces the exact external input without storing the media itself in Git.",
                "Added idempotent download, hash verification, temporary output, and provenance reporting.",
            ),
            (
                "scripts/download_construction_ppe_dataset.py",
                "Downloads, fingerprints, and safely extracts the official Construction-PPE archive.",
                "Makes PPE training input reproducible while rejecting corrupt files and unsafe ZIP paths.",
                "Added trusted retrieval, size and hash checks, traversal protection, and idempotence.",
            ),
            (
                "scripts/audit_yolo_dataset.py",
                "Audits YOLO pairing, normalized boxes, class balance, and exact split duplicates.",
                "Catches structural defects before training and writes machine-readable audit evidence.",
                "Added dependency-free config parsing, statistics, orphan checks, and SHA256 comparison.",
            ),
            (
                "scripts/download_yolo_model.py",
                "Downloads the pinned YOLO26n baseline and verifies its SHA256 hash.",
                "Reproduces the exact model without committing or trusting an unverified binary.",
                "Added idempotent download, temporary output, checksum validation, and provenance reporting.",
            ),
            (
                "scripts/download_tracking_dependency.py",
                "Downloads the pinned Linux lap wheel and verifies its SHA256 before image builds.",
                "Supplies ByteTrack reproducibly without disabling TLS verification inside Docker.",
                "Added Windows trust-store download, cleanup, platform pinning, and checksum validation.",
            ),
            (
                "scripts/download_streaming_dependencies.py",
                "Downloads Linux wheels for pinned Kafka, MinIO, and Parquet packages with SHA256 verification.",
                "Supports reproducible offline Docker installation without disabling TLS inside the container.",
                "Added PyArrow to the exact 11-file checksum allowlist.",
            ),
            (
                "scripts/build_final_demo_video.py",
                "Builds the final frame-only no-vest evidence image and summary from the validated real Pexels video.",
                "Keeps the final presentation proof reproducible instead of manually edited.",
                "Replaced the image-built demo generator with real-video evidence-frame extraction and annotation.",
            ),
            (
                "scripts/run_mvp_demo.ps1",
                "Runs every local MVP stage and optionally launches Streamlit with one command.",
                "Provides a reproducible entry point while preserving intermediate artifacts.",
                "Replaced Path.GetRelativePath with Windows PowerShell-compatible path normalization.",
            ),
            (
                "scripts/run_streaming_demo.ps1",
                "Runs one isolated Kafka, MinIO, CV, API, and PostgreSQL demonstration.",
                "Replaces manual sequencing with validated inputs, isolated topics, safety gates, and one report.",
                "Replaced Path.GetRelativePath with Windows PowerShell-compatible path normalization.",
            ),
            (
                "scripts/test_streaming_e2e.ps1",
                "Runs the complete streaming path and verifies every boundary with strict assertions.",
                "Provides professional evidence for video sampling, MinIO, Kafka, YOLO, tracking, FastAPI, PostgreSQL, and duplicate protection.",
                "Added an isolated real-stream phase, deterministic positive delivery probe, idempotent replay, cleanup, and machine-readable report.",
            ),
            (
                "scripts/start_mlflow_ui.ps1",
                "Starts local MLflow against the project SQLite database and artifact directory.",
                "Provides one Windows command that requires no Docker and supports spaced paths.",
                "Added a configurable localhost port and local-environment validation.",
            ),
            (
                "scripts/prove_agent_locally.ps1",
                "Runs an isolated PostgreSQL and agent proof without Docker.",
                "Verifies the real read-only role, write rejection, HTTP grounding, and cleanup.",
                "Added timestamped clusters, migrations, Llama call, 422 check, and atomic proof JSON.",
            ),
            (
                "scripts/run_final_architecture.ps1",
                "Starts the complete SafeSite profiles and waits for their public HTTP endpoints.",
                "Provides the requested one-command final architecture entry point.",
                "Creates all five three-partition Kafka topics before starting consumers, then launches every architecture profile.",
            ),
            (
                "scripts/verify_final_architecture.py",
                "Audits saved evidence for every final architecture layer.",
                "Creates one machine-readable completion report instead of relying on undocumented claims.",
                "Verifies all 13 live services and the dashboard's decision, evidence, missing-proof, technical, and assistant sections.",
            ),
        ],
    ),
    (
        "Documentation tooling and output",
        [
            (
                "scripts/generate_file_catalog_pdf.py",
                "Generates this polished catalog PDF from maintained metadata.",
                "Makes future PDF updates consistent and repeatable.",
                "Recorded the LinkedIn-ready full architecture image and kept the register on a clean page.",
            ),
            (
                "output/linkedin/safesite-ai-full-architecture.png",
                "Provides a LinkedIn-ready full architecture diagram for SafeSite AI.",
                "Summarizes the complete system visually for portfolio and PFE communication.",
                "Added a 1920x1200 dark architecture image covering video source, ingestion, Kafka, MinIO, YOLO/ByteTrack, API, PostgreSQL, dashboard, Airflow, MLflow, data quality, agent layer, and final evidence.",
            ),
            (
                "data/final/test-results.json",
                "Records the latest automated unit-test results used by the portfolio dashboard.",
                "Keeps the displayed test counts traceable to a machine-readable project artifact.",
                "Recorded 14 passing tests across the grounded assistant, MLflow comparison, drift monitoring, and data-quality suites.",
            ),
            (
                "data/final/e2e-streaming-{run-id}.json",
                "Records every assertion and artifact from a full streaming end-to-end execution.",
                "Separates integration proof from model-accuracy evaluation and makes the result auditable.",
                "Added per-stage expected and actual values, delivery evidence, replay evidence, duration, and failure details.",
            ),
            (
                "output/linkedin/dashboard-proof/01-safety-proof.png",
                "Shows the Streamlit safety decision with the real annotated no-vest evidence frame.",
                "Provides visual proof that the dashboard connects a decision, evidence, and model metrics.",
                "Captured the final 1440x1000 Safety Proof tab for the LinkedIn carousel.",
            ),
            (
                "output/linkedin/dashboard-proof/02-gold-analytics.png",
                "Shows Gold Parquet row counts and Great Expectations quality results.",
                "Demonstrates the project analytics and data-quality layers with real saved outputs.",
                "Captured the final 1440x1000 Analytics tab for the LinkedIn carousel.",
            ),
            (
                "output/linkedin/dashboard-proof/03-ai-assistant.png",
                "Shows the grounded assistant answer, approved SQL, Ollama provider, and read-only protection.",
                "Demonstrates that natural-language answers remain traceable and database-safe.",
                "Captured the final 1440x1000 AI Assistant tab for the LinkedIn carousel.",
            ),
            (
                "output/linkedin/dashboard-proof/04-tests.png",
                "Shows the real verbose terminal output from the current SafeSite automated tests.",
                "Provides direct verification evidence with every test name, its ok status, elapsed time, and final pass count.",
                "Replaced the dashboard test card with a professional terminal-style proof showing 14 passed and 0 failed.",
            ),
            (
                "output/linkedin/dashboard-proof/04-tests.txt",
                "Stores the text represented in the terminal test screenshot.",
                "Keeps the visual proof readable, searchable, and independently reviewable.",
                "Generated alongside the final terminal screenshot from the same fresh 14-test execution.",
            ),
            (
                "scripts/create_test_terminal_proof.py",
                "Runs the portfolio test suites and renders their verified terminal output as a PNG.",
                "Makes the LinkedIn test proof reproducible instead of manually edited.",
                "Added guarded rendering that produces the screenshot only when all 14 expected tests pass.",
            ),
            (
                "output/linkedin/dashboard-proof/05-e2e-streaming-test.png",
                "Shows the real full streaming pipeline E2E result as a terminal-style proof image.",
                "Provides professional evidence that Kafka, MinIO, YOLO, tracking, FastAPI, PostgreSQL, and duplicate protection work together.",
                "Generated from a passed E2E JSON report with 14 assertions passed and 0 failed.",
            ),
            (
                "output/linkedin/dashboard-proof/05-e2e-streaming-test.txt",
                "Stores the text represented in the full streaming E2E proof screenshot.",
                "Keeps the LinkedIn test evidence searchable and easy to verify.",
                "Generated from the same passed E2E report used for the PNG proof.",
            ),
            (
                "scripts/create_e2e_terminal_proof.py",
                "Reads a passed E2E JSON report and renders a terminal-style proof screenshot.",
                "Prevents fake success evidence by refusing to render when the report did not pass.",
                "Added for the final professional LinkedIn proof package.",
            ),
            (
                "output/pdf/SafeSite_AI_File_Catalog.pdf",
                "Provides the printable and shareable form of the file catalog.",
                "Supports project reviews, learning, and PFE interview preparation.",
                "Regenerated after adding the full streaming E2E proof screenshot and renderer.",
            ),
        ],
    ),
]


def footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
    canvas.line(20 * mm, 15 * mm, 190 * mm, 15 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#52616B"))
    canvas.drawString(20 * mm, 10 * mm, "SafeSite AI - Maintained File Catalog")
    canvas.drawCentredString(105 * mm, 10 * mm, str(document.page))
    canvas.restoreState()


def build_pdf() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = OUTPUT.with_name(f"{OUTPUT.stem}.building{OUTPUT.suffix}")
    document = SimpleDocTemplate(
        str(temporary_output),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=28 * mm,
        title="SafeSite AI File Catalog",
        author="SafeSite AI Project",
        subject="Project file roles and change register",
    )

    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "CatalogTitle",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=34,
        textColor=colors.HexColor("#102A43"),
        alignment=TA_CENTER,
        spaceAfter=10 * mm,
    )
    subtitle = ParagraphStyle(
        "CatalogSubtitle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=18,
        textColor=colors.HexColor("#486581"),
        alignment=TA_CENTER,
    )
    section = ParagraphStyle(
        "CatalogSection",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#0B6E75"),
        spaceBefore=5 * mm,
        spaceAfter=4 * mm,
        keepWithNext=True,
    )
    path_style = ParagraphStyle(
        "CatalogPath",
        parent=base["Heading2"],
        fontName="Courier-Bold",
        fontSize=9.2,
        leading=12,
        textColor=colors.HexColor("#102A43"),
        spaceAfter=2 * mm,
        splitLongWords=True,
    )
    body = ParagraphStyle(
        "CatalogBody",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=9.4,
        leading=13.5,
        textColor=colors.HexColor("#243B53"),
        spaceAfter=1.6 * mm,
    )
    small = ParagraphStyle(
        "CatalogSmall",
        parent=body,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#52616B"),
        spaceAfter=1 * mm,
    )

    story = [
        Spacer(1, 28 * mm),
        Paragraph("SafeSite AI", title),
        Paragraph("Maintained File Catalog", subtitle),
        Spacer(1, 12 * mm),
        Table(
            [
                ["Edition", "Complete final architecture"],
                ["Updated", date(2026, 9, 1).isoformat()],
                ["Maintained files", str(sum(len(entries) for _, entries in SECTIONS))],
                ["Current milestone", "Complete final architecture"],
            ],
            colWidths=[42 * mm, 92 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#D9F0F0")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#102A43")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BCCCDC")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        ),
        Spacer(1, 12 * mm),
        Paragraph(
            "This document explains the role, reason, and latest meaningful change for every maintained SafeSite AI project file. Generated caches, local secrets, Docker volumes, downloaded models, and temporary render files are intentionally excluded.",
            subtitle,
        ),
        PageBreak(),
        Paragraph("Maintenance protocol", section),
        Paragraph(
            "Whenever a file is created, removed, or meaningfully changed, update the Markdown catalog and the generator metadata, regenerate this PDF, render every page, and include the documentation update in the same Git commit.",
            body,
        ),
        Spacer(1, 3 * mm),
    ]

    for section_name, entries in SECTIONS:
        for entry_index, (file_path, role, reason, latest_change) in enumerate(entries):
            if file_path in PAGE_BREAK_BEFORE:
                story.append(PageBreak())
            card = [
                Paragraph(file_path, path_style),
                Paragraph(f"<b>Role:</b> {role}", body),
                Paragraph(f"<b>Why it exists:</b> {reason}", body),
                Paragraph(f"<b>Latest change:</b> {latest_change}", small),
            ]
            if file_path != "services/ingestion/app/render_yolo_labels.py":
                card.append(Spacer(1, 3.2 * mm))
            if entry_index == 0:
                card.insert(0, Paragraph(section_name, section))
            story.extend(card)

    story.extend(
        [
            PageBreak(),
            Paragraph("Change register", section),
            Paragraph(
                "<b>2026-09-06:</b> Added a controlled ten-second video with six workers and three visible ground-truth violations. The complete 30-frame run maintained six tracks but confirmed zero candidates, documenting a current model limitation rather than claiming compliance.",
                small,
            ),
            Paragraph(
                "<b>2026-09-03:</b> Replaced the unreliable local MLflow dependency build with the official MLflow 3.15.2 image pinned by digest, made the launcher create all five three-partition Kafka topics before consumers start, added truthful full-Compose replay recording with live verification of all 13 long-running services, fixed Docker-safe dashboard data-root resolution, reorganized the dashboard around a clear safety decision with honest visual-proof status, and updated the final audit to enforce the new interface contract.",
                small,
            ),
            Paragraph(
                "<b>2026-09-01:</b> Completed the 18-service architecture with the read-only LangGraph agent, Ollama Llama and Qwen-VL, Great Expectations, drift monitoring, two-run MLflow comparison, Airflow container, final launcher, 12-check completion audit, Lessons 30-32, and the final architecture matrix.",
                small,
            ),
            Paragraph(
                "<b>2026-08-27:</b> Logged the existing PPE baseline with 12 parameters, 54 metrics, and nine run artifacts; packaged its exact weight with model-from-code; registered SafeSite-PPE-Detector version 1 as the experimental candidate; verified SQLite integrity and the local MLflow UI; and added Lesson 29.",
                small,
            ),
            Paragraph(
                "<b>2026-08-27:</b> Added Gold frame, worker, and daily-camera Parquet tables, a 12-check quality gate, duplicate-event rejection, one-command analytics execution, the daily Airflow DAG contract, and Lesson 28.",
                small,
            ),
            Paragraph(
                "<b>2026-08-21:</b> Added worker heartbeats, Kafka lag, FastAPI and MinIO checks, alerts, stale-report protection, and a five-service healthy proof with zero restarts, lag 1/1/0, and a degraded stopped-worker proof in Lesson 27.",
                small,
            ),
            Paragraph(
                "<b>2026-08-21:</b> Added always-on candidate delivery using propagated occurred_at, exact PostgreSQL time preservation, retry and idempotency boundaries, and missing-time DLQ safety in Lesson 26.",
                small,
            ),
            Paragraph(
                "<b>2026-08-21:</b> Added camera-key partitioning, isolated per-camera YOLO and temporal state, camera-scoped track identities, and a three-camera zero-collision proof in Lesson 25.",
                small,
            ),
            Paragraph(
                "<b>2026-08-21:</b> Added continuous camera, RTSP, and video ingestion with MinIO Bronze, Kafka schema-version-2 events, absolute captured_at, monotonic stream time, and a three-camera proof in Lesson 24.",
                small,
            ),
            Paragraph(
                "<b>2026-08-21:</b> Added configurable continuous PPE inference and tracking services, bounded worker memory, restartable output paths, per-event commit-after-output safety, a 35-second idle proof with zero restarts, and a one-frame regression in Lesson 23.",
                small,
            ),
            Paragraph(
                "<b>2026-08-21:</b> Added Streamlit monitoring for selectable run reports, stage health, Kafka frame counts, CV measurements, candidate and database outcomes, technical JSON inspection, and honest safety interpretation in Lesson 22.",
                small,
            ),
            Paragraph(
                "<b>2026-08-21:</b> Added and ran one isolated ten-stage streaming command; verified 30 raw, 30 PPE, and 30 track events, 30 Bronze, 60 Silver, and 60 Gold objects, zero lag, healthy API and database, zero unconfirmed writes, opt-in candidate delivery, and protected reruns in Lesson 21.",
                small,
            ),
            Paragraph(
                "<b>2026-08-20:</b> Connected confirmed Kafka candidates to FastAPI and PostgreSQL with retries, HTTP 201/200 idempotency, commit-last offsets, and a confirmed dead-letter topic; proved one new row, one safe replay, one unsupported event in the DLQ, and zero source lag in Lesson 20.",
                small,
            ),
            Paragraph(
                "<b>2026-08-20:</b> Processed 30 ordered PPE events through persistent ByteTrack, worker-level PPE association, sliding-window rules, MinIO Gold, and Kafka outputs; verified 30 unique track events, 60 non-empty Gold objects, zero lag, and zero unsupported safety accusations in Lesson 19.",
                small,
            ),
        ]
    )

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    temporary_output.replace(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
