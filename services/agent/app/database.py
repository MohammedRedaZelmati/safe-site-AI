from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


class ReadOnlyDatabase:
    def __init__(self, database_url: str):
        self.pool = AsyncConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=4,
            open=False,
            kwargs={"row_factory": dict_row},
        )

    async def open(self) -> None:
        await self.pool.open()
        await self.pool.wait()

    async def close(self) -> None:
        await self.pool.close()

    async def execute(self, sql: str, parameters: list[Any]) -> list[dict[str, Any]]:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                await connection.execute("SET TRANSACTION READ ONLY")
                cursor = await connection.execute(sql, parameters)
                rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def health(self) -> dict[str, str]:
        rows = await self.execute(
            "SELECT current_user AS current_user, current_setting('transaction_read_only') AS transaction_read_only",
            [],
        )
        return {key: str(value) for key, value in rows[0].items()}
