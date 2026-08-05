# Lesson 2: Safe Asynchronous API Filtering

## Goal

Understand the HTTP request lifecycle, asynchronous database waiting, connection pooling, parameterized SQL, and automated integration tests. Then use those concepts to filter violations by occurrence time safely.

## 1. HTTP lifecycle

For `GET /health`, the request travels through:

```text
curl -> Windows port 8000 -> Docker forwarding -> Uvicorn
     -> FastAPI route -> PostgreSQL -> JSON response
```

`200 OK` describes the HTTP result. `content-type: application/json` describes the response-body format. The health route executes `SELECT 1`, so it verifies that the API can reach PostgreSQL rather than merely proving that the Python process exists.

## 2. Async and await

`async def` allows a route to pause at an `await` operation. While one request waits for PostgreSQL, Uvicorn's event loop can advance another request.

```text
request A waits for SQL -> event loop handles request B -> SQL A returns -> request A continues
```

The `async` keyword alone does not make blocking CPU work concurrent. YOLO inference must not block the API event loop and will later run in a dedicated inference service.

## 3. Connection pool

Opening a database connection requires network setup and authentication. The pool opens reusable connections during FastAPI startup:

```text
borrow connection -> execute SQL -> return connection
```

If every connection is busy, another request waits asynchronously until one is returned. The lifespan function opens the pool at startup and closes it cleanly at shutdown.

## 4. Parameterized queries

User values must never be inserted directly into SQL strings.

Unsafe:

```python
query = f"SELECT * FROM violations WHERE camera_id = '{camera_id}'"
```

Safe:

```python
query = "SELECT * FROM violations WHERE camera_id = %s"
await connection.execute(query, [camera_id])
```

Psycopg sends the SQL structure and values separately. Input such as `camera-01' OR '1'='1` remains plain text instead of becoming executable SQL.

## 5. Time-range contract

`GET /violations` now accepts:

- `occurred_from`: include events at or after this timestamp.
- `occurred_to`: include events at or before this timestamp.

Both boundaries are inclusive. If `occurred_from` is later than `occurred_to`, the API returns `422 Unprocessable Entity`.

Example:

```text
GET /violations?camera_id=camera-01&occurred_from=2026-08-05T10:00:00Z&occurred_to=2026-08-05T12:00:00Z
```

## 6. Integration tests

The test container calls the running API over Docker's network and verifies the real PostgreSQL behavior. The tests cover:

- correct inclusive time filtering;
- rejection of a reversed range;
- SQL-injection text being treated as an ordinary camera ID.

Run:

```powershell
docker compose --profile test run --rm api-tests
```

The test fixture creates a unique camera ID and deletes its test rows afterward, keeping the development database clean.

## Explain it aloud

Explain why these two statements are both true:

1. The query uses an f-string to assemble its `WHERE` clause safely.
2. User-provided camera IDs and timestamps must still use placeholders.

The answer is that the f-string combines only fixed SQL fragments written by the developer; every external value remains a separate bound parameter.

