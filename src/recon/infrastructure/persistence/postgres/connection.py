from __future__ import annotations

from contextlib import asynccontextmanager 
from typing import AsyncIterator

import asyncpg 

from recon.infrastructure.persistence.postgres.config import DatabaseConfig


class PostgresConnection:
    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config 
        self._pool: asyncpg.Pool | None = None 

    async def connect(self) -> None:
        if self._pool is not None:
            return 

        self._pool = await asyncpg.create_pool(
            dsn=self._config.dsn,
            min_size=1,
            max_size=10,
        )
    
    async def close(self) -> None:
        if self._pool is None:
            return 

        await self._pool.close()
        self._pool = None 

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Postgres connection pool is not initialized.")

        return self._pool

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        async with self.pool.acquire() as connection:
            yield connection 
