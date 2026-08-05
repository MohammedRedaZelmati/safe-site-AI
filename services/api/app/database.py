from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import settings


pool = AsyncConnectionPool(
    conninfo=settings.database_url,
    kwargs={"autocommit": True, "row_factory": dict_row},
    open=False,
)


async def open_pool() -> None:
    await pool.open()
    await pool.wait()


async def close_pool() -> None:
    await pool.close()

