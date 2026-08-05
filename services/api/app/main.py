from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, status

from app.database import close_pool, open_pool, pool
from app.schemas import Summary, Violation, ViolationCreate, ViolationType


@asynccontextmanager
async def lifespan(_: FastAPI):
    await open_pool()
    yield
    await close_pool()


app = FastAPI(
    title="SafeSite AI API",
    description="Structured access to PPE violation events.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    async with pool.connection() as connection:
        await connection.execute("SELECT 1")
    return {"status": "healthy", "database": "reachable"}


@app.post("/violations", response_model=Violation, status_code=status.HTTP_201_CREATED)
async def create_violation(payload: ViolationCreate) -> Violation:
    query = """
        INSERT INTO violations (
            occurred_at,
            camera_id,
            track_id,
            violation_type,
            confidence,
            frame_uri
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    values = (
        payload.occurred_at,
        payload.camera_id,
        payload.track_id,
        payload.violation_type.value,
        payload.confidence,
        payload.frame_uri,
    )
    async with pool.connection() as connection:
        cursor = await connection.execute(query, values)
        row = await cursor.fetchone()
    return Violation.model_validate(row)


@app.get("/violations", response_model=list[Violation])
async def list_violations(
    camera_id: str | None = None,
    violation_type: ViolationType | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Violation]:
    if occurred_from is not None and occurred_to is not None and occurred_from > occurred_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="occurred_from must be earlier than or equal to occurred_to",
        )

    conditions: list[str] = []
    values: list[object] = []

    if camera_id is not None:
        conditions.append("camera_id = %s")
        values.append(camera_id)
    if violation_type is not None:
        conditions.append("violation_type = %s")
        values.append(violation_type.value)
    if occurred_from is not None:
        conditions.append("occurred_at >= %s")
        values.append(occurred_from)
    if occurred_to is not None:
        conditions.append("occurred_at <= %s")
        values.append(occurred_to)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT *
        FROM violations
        {where_clause}
        ORDER BY occurred_at DESC
        LIMIT %s
    """
    values.append(limit)

    async with pool.connection() as connection:
        cursor = await connection.execute(query, values)
        rows = await cursor.fetchall()
    return [Violation.model_validate(row) for row in rows]


@app.get("/stats/summary", response_model=Summary)
async def summary() -> Summary:
    query = """
        SELECT violation_type, COUNT(*) AS count
        FROM violations
        GROUP BY violation_type
        ORDER BY violation_type
    """
    async with pool.connection() as connection:
        cursor = await connection.execute(query)
        rows = await cursor.fetchall()

    by_type = [
        {"violation_type": row["violation_type"], "count": row["count"]}
        for row in rows
    ]
    return Summary(total=sum(item["count"] for item in by_type), by_type=by_type)
