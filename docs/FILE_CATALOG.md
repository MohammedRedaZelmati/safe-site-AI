# SafeSite AI File Catalog

**Last updated:** 2026-08-05  
**Current milestone:** Day 2 - safe time filtering and integration tests
**Purpose:** explain the responsibility of every maintained project file and record meaningful changes.

## How to maintain this catalog

Whenever a file is created, removed, or meaningfully changed:

1. Update its entry in this document.
2. Update the corresponding entry in `scripts/generate_file_catalog_pdf.py`.
3. Regenerate the PDF with the bundled Python runtime.
4. Render the PDF and visually verify every page.
5. Include the catalog update in the same Git commit as the code change.

Generated caches such as `__pycache__`, local secrets such as `.env`, Docker volumes, downloaded models, and temporary render files are not maintained project files and are intentionally excluded.

## Root configuration

### `.gitattributes`

**Role:** tells Git which project artifacts must be treated as binary files.

**Why it exists:** prevents whitespace checks, line-ending conversion, and unreadable text diffs for PDFs, images, videos, and model weights.

**Latest change:** added binary rules for PDF, image, video, and PyTorch model artifacts.

### `.env.example`

**Role:** documents the environment variables needed by PostgreSQL and FastAPI.  
**Why it exists:** developers can copy it to `.env` without committing real local credentials.  
**Latest change:** initial database name, user, password, and connection URL added.

### `.gitignore`

**Role:** tells Git which local or generated files must not be versioned.  
**Why it exists:** prevents secrets, caches, model weights, temporary files, and local data from polluting commits.  
**Latest change:** initial Python, editor, data, model, MLflow, and temporary-file exclusions added.

### `README.md`

**Role:** main entry point for understanding and running SafeSite AI.  
**Why it exists:** gives new developers the project goal, current milestone, startup commands, learning links, and working rules.  
**Latest change:** added the Day 2 lesson link and containerized integration-test command.

### `compose.yaml`

**Role:** defines and connects the PostgreSQL and FastAPI containers.  
**Why it exists:** starts the current system reproducibly with one command and preserves database data in a named volume.  
**Latest change:** added the API health check and optional `api-tests` service profile.

## Database

### `database/init/001_schema.sql`

**Role:** creates the `violations` table, validation constraints, indexes, and initial fake events.  
**Why it exists:** gives PostgreSQL a clear event contract and useful test data when a fresh database volume is initialized.  
**Latest change:** initial schema for camera, track, violation type, confidence, evidence URI, and timestamps added.

## API container

### `services/api/Dockerfile`

**Role:** describes how to build the FastAPI container image.  
**Why it exists:** packages Python, dependencies, and API source into a reproducible runtime.  
**Latest change:** split the image into reusable base, runtime, and test build stages.

### `services/api/requirements.txt`

**Role:** declares the Python libraries required by the API.  
**Why it exists:** makes dependency installation repeatable inside the container.  
**Latest change:** FastAPI, Uvicorn, Psycopg, connection-pool, and settings dependencies added.

### `services/api/requirements-dev.txt`

**Role:** declares dependencies used only by automated API tests.

**Why it exists:** keeps test tooling separate from the production runtime image.

**Latest change:** added Pytest and HTTPX for black-box integration testing.

## API application

### `services/api/app/__init__.py`

**Role:** marks the `app` directory as a Python package.  
**Why it exists:** allows imports such as `app.main` and `app.schemas` to work predictably.  
**Latest change:** initial package marker added.

### `services/api/app/config.py`

**Role:** loads the database connection URL from environment variables.  
**Why it exists:** separates deploy-time configuration from application logic and avoids hard-coding production settings.  
**Latest change:** initial Pydantic settings model and development default added.

### `services/api/app/database.py`

**Role:** creates and manages the asynchronous PostgreSQL connection pool.  
**Why it exists:** reuses database connections efficiently and opens or closes them with the API lifecycle.  
**Latest change:** initial Psycopg pool with dictionary rows, startup wait, and graceful shutdown added.

### `services/api/app/schemas.py`

**Role:** defines Pydantic request and response contracts for violation data.  
**Why it exists:** validates JSON types, required fields, allowed violation types, ranges, and response structure.  
**Latest change:** initial violation type, creation, response, count, and summary models added.

### `services/api/app/main.py`

**Role:** defines the FastAPI application, lifecycle, and HTTP routes.  
**Why it exists:** exposes health, event creation, event listing, filtering, and summary statistics over PostgreSQL.  
**Latest change:** added inclusive `occurred_from` and `occurred_to` filters plus reversed-range validation.

## API tests

### `services/api/tests/test_time_filters.py`

**Role:** verifies time filtering, invalid ranges, and SQL-injection resistance against the running API and database.

**Why it exists:** proves the HTTP, validation, SQL, and PostgreSQL layers work together rather than testing them only in isolation.

**Latest change:** initial three black-box integration tests and automatic test-data cleanup added.

## Learning documentation

### `docs/ARCHITECTURE.md`

**Role:** explains the complete architecture by following one violation event.  
**Why it exists:** connects video ingestion, messaging, CV inference, storage, API, dashboard, MLOps, and the optional agent into one mental model.  
**Latest change:** initial current, Week 2, Week 3, and Week 4 architecture stages documented.

### `docs/LESSON_01.md`

**Role:** provides the first guided lesson and practical exercises.  
**Why it exists:** teaches containers, ports, services, schemas, persistence, logs, and the request-to-database flow.  
**Latest change:** initial Day 1 exercises and explanation checkpoint added.

### `docs/LESSON_02.md`

**Role:** documents the second guided lesson and its implementation exercise.

**Why it exists:** teaches HTTP flow, async waiting, connection pooling, parameterized SQL, time filters, and integration tests.

**Latest change:** initial Day 2 lesson and explanation checkpoint added.

### `docs/ROADMAP.md`

**Role:** defines the realistic 28-day learning and implementation plan.  
**Why it exists:** protects the one-month deadline by separating must-have, should-have, and stretch features.  
**Latest change:** initial four-week plan adapted for the detected GTX 1650 with 4 GB VRAM.

### `docs/FILE_CATALOG.md`

**Role:** human-readable source catalog for every maintained project file.  
**Why it exists:** helps the learner understand file ownership and keeps documentation synchronized with implementation changes.  
**Latest change:** added Day 2 files and recorded all filtering, testing, container, and lesson changes.

## Documentation tooling and output

### `scripts/generate_file_catalog_pdf.py`

**Role:** generates the polished file-catalog PDF from maintained catalog metadata.  
**Why it exists:** makes PDF regeneration consistent after future project changes.  
**Latest change:** added Day 2 file entries, updated change descriptions, and regenerated pagination.

### `output/pdf/SafeSite_AI_File_Catalog.pdf`

**Role:** shareable and printable version of the file catalog.  
**Why it exists:** provides an easy reference during learning, reviews, and PFE interview preparation.  
**Latest change:** regenerated after the Day 2 API, tests, container, README, and lesson changes.

## Change register

### 2026-08-05 - Safe time filtering and tests

- Added inclusive occurrence-time filters and reversed-range validation.
- Added a multi-stage API image and optional integration-test service.
- Added tests for time ranges and SQL-injection resistance.
- Added `docs/LESSON_02.md` and updated the maintained catalog.
- Added `.gitattributes` so generated artifacts are handled as binary files.

### 2026-08-05 - File catalog introduced

- Added `docs/FILE_CATALOG.md`.
- Added `scripts/generate_file_catalog_pdf.py`.
- Added `output/pdf/SafeSite_AI_File_Catalog.pdf`.
- Updated `README.md` with the synchronization rule.

### 2026-08-04 - Initial vertical slice

- Added Docker Compose with PostgreSQL and FastAPI.
- Added the violation schema and seed data.
- Added health, create, list, filter, and summary endpoints.
- Added the architecture, Day 1 lesson, and 28-day roadmap.
