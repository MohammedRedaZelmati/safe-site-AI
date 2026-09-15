# SafeSite Grounded Agent

The agent answers a small approved set of natural-language questions about stored
violation events.

## Safety boundaries

1. A deterministic planner selects SQL from a fixed catalog.
2. Every query is a parameterized `SELECT` against `violations` only.
3. PostgreSQL connects as `safesite_agent`, whose transactions are read-only.
4. LangGraph runs planning, validation, execution, and answer nodes in order.
5. Ollama receives only the question, approved SQL, and returned rows.
6. If Ollama is unavailable, a deterministic answer keeps the feature usable.
7. Unsupported questions and every write request are rejected before database use.

## Supported questions

- How many violations are there?
- Show violations by type.
- Show violations by camera.
- How many violations are there for camera-01?
- Show the latest 5 violations.
- What is the most common violation?

## Vision endpoint

`POST /vision/describe` accepts only a JPEG or PNG inside the mounted SafeSite data
directory. It sends the image to the configured Ollama vision model. The prompt
requires visible, uncertainty-aware PPE descriptions and forbids unsupported
violation claims.

The default text model is the locally available `llama3.2:latest`. The vision
provider defaults to `qwen2.5vl:3b`; install that Ollama model separately before
using image descriptions. SafeSite never downloads a large model automatically.

On Windows, start the host service with `python services/agent/run_windows.py`.
That launcher selects the event loop required by asynchronous Psycopg before
Uvicorn starts. Linux and the Docker image use the normal Uvicorn command.
