# SafeSite AI

SafeSite AI turns construction-site video into structured PPE-compliance events. The final platform will read simulated camera streams, detect and track PPE violations, store evidence, expose analytics, and answer grounded questions about incidents.

This repository is intentionally built in layers. We start with a small working data path and replace each fake input with a real component only after understanding it.

## Current milestone: event storage and API

```text
fake violation -> FastAPI -> PostgreSQL -> JSON response
```

This first slice teaches four ideas used by every later component:

1. A **data contract** defines what a violation event means.
2. PostgreSQL is the **source of truth** for structured events.
3. FastAPI is the controlled door through which clients access data.
4. Docker Compose gives services a repeatable environment and network.

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

## Project rule

For every component, follow this loop:

```text
understand -> tiny exercise -> implement -> observe -> explain aloud
```

If you cannot explain a component without reading the code, it is not finished yet.

