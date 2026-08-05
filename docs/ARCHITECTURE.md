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

## 7. MLOps and optional agent

MLflow records how a model was trained and evaluated. Data-quality and drift jobs monitor whether incoming data remains trustworthy. A text-to-SQL assistant is useful only after the schema and API produce reliable data; it must use a read-only database account and validated queries.

## Current versus final architecture

```text
CURRENT
manual fake event -> FastAPI -> PostgreSQL

WEEK 2
video -> YOLO + ByteTrack -> FastAPI -> PostgreSQL

WEEK 3
video -> ingestion -> Kafka -> YOLO + ByteTrack -> PostgreSQL
          |                       |
          +-> MinIO bronze        +-> MinIO silver

WEEK 4
PostgreSQL -> FastAPI -> Streamlit
     |          |
 quality/drift  +-> optional grounded assistant
```

Every stage keeps the same violation contract. That is what allows us to replace fake producers with real ones safely.

