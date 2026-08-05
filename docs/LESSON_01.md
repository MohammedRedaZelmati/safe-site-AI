# Lesson 1: Follow One Violation Event

## Goal

By the end of this lesson, you should be able to explain how a JSON request becomes a durable database row and then returns as JSON.

## Vocabulary

- **Process:** a running program.
- **Port:** a numbered network door used to reach a process.
- **Container:** an isolated process with packaged dependencies.
- **Image:** the read-only recipe used to create a container.
- **Volume:** storage that survives container replacement.
- **Service:** one responsibility exposed over a network, such as the API or database.
- **Schema:** rules describing valid data and relationships.
- **Data contract:** the agreed shape and meaning of data exchanged between components.

## Exercise A - Predict before running

Open `compose.yaml` and answer in your own words:

1. Which two services start?
2. Why can the API use hostname `postgres` instead of `localhost`?
3. Which port belongs to FastAPI?
4. What is stored in `postgres_data`?
5. Why does the API wait for the database health check?

## Exercise B - Observe the containers

Run:

```powershell
docker compose up --build
docker compose ps
docker compose logs api
docker compose logs postgres
```

Do not just check that it works. Find evidence for the following statements in the logs:

- PostgreSQL became ready before the API started accepting traffic.
- Uvicorn listens on port 8000 inside the API container.
- Database initialization created the schema and seed events.

## Exercise C - Trace a write

Use Swagger at http://localhost:8000/docs to call `POST /violations`.

Trace the request through these checkpoints:

1. JSON arrives at the route in `services/api/app/main.py`.
2. `ViolationCreate` rejects malformed data before SQL runs.
3. The SQL `INSERT` uses placeholders, not string concatenation.
4. PostgreSQL checks confidence and violation type constraints.
5. `RETURNING` gives the inserted row back to the API.
6. FastAPI serializes the validated response as JSON.

## Exercise D - Prove persistence

1. Create an event and remember its ID.
2. Run `docker compose restart api`.
3. Fetch the event again. It remains because the database did not stop.
4. Run `docker compose down`, then `docker compose up`.
5. Fetch it again. It remains because the named volume persists.

## Explain it aloud

Without reading, complete this sentence:

> A PPE violation begins as JSON. FastAPI first..., then PostgreSQL..., and the event survives restarts because...

If the explanation is unclear, repeat the trace with API and database logs visible side by side.

