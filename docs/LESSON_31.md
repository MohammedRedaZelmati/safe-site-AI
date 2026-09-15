# Lesson 31 - Grounded Agent and Vision-Language Support

## Why the agent comes last

An agent cannot repair unreliable data. SafeSite first needs a working database, API, CV pipeline, event contract, and quality checks. Only then can a language model answer useful questions about trusted events.

## The text question flow

```text
user question
    -> approved intent catalog
    -> validated parameterized SELECT
    -> read-only PostgreSQL transaction
    -> small result rows
    -> Ollama/Llama explanation
    -> answer + visible SQL + rows
```

LangGraph coordinates four explicit nodes:

1. `plan`: map the question to one approved query.
2. `validate`: prove the SQL matches the allowlist and is read-only.
3. `execute`: run it through the database pool.
4. `answer`: ask Ollama to explain only the returned rows, or use a deterministic fallback.

This is **not unrestricted text-to-SQL**. The model cannot invent arbitrary SQL. `services/agent/app/query_catalog.py` owns the approved templates.

## Three safety layers

1. The question planner rejects write requests and unsupported questions.
2. SQL validation accepts only exact approved `SELECT` templates against `violations`.
3. PostgreSQL connects as `safesite_agent`, a role with `SELECT` permission and read-only transactions.

The real proof used an isolated PostgreSQL database. A `SELECT` returned three rows, while `DELETE` failed with `cannot execute DELETE in a read-only transaction`. The HTTP endpoint also rejected the write request with status 422.

## Why return SQL and rows

The dashboard shows the generated SQL, parameters, and rows beside the natural-language answer. This makes grounding inspectable. A reviewer can check that the answer really follows from the database result.

## Vision-language model

The `/vision/describe` endpoint sends one verified local JPEG or PNG to `qwen2.5vl:3b` through Ollama. It can describe visible workers and PPE in simple language.

The verified frame description was:

> Two construction workers are visible. Both are wearing high-visibility vests and hard hats.

The VLM is **supporting context only**. YOLO, ByteTrack, temporal rules, and the API event contract remain authoritative. A fluent VLM sentence is not enough to create a safety incident.

## Why Ollama

Ollama runs the language and vision models locally. SafeSite sends requests to its HTTP API, so model execution stays separate from FastAPI and can be replaced later without changing the event database.

## Run it without Docker

Ensure Ollama is running and the two models exist, then use:

```powershell
.\scripts\prove_agent_locally.ps1
```

The proof is stored in:

- `data/agent/block31-database-proof.json`
- `data/agent/block31-vision-proof.json`

## Explain it aloud

> The agent does not create arbitrary SQL. LangGraph selects an approved query, validates it, runs it with a read-only PostgreSQL role, and gives only the result rows to Ollama. Qwen can describe evidence frames, but deterministic CV rules remain responsible for violation events.

