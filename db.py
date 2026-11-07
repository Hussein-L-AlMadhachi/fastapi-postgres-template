
import asyncio
from collections.abc import AsyncGenerator

import asyncpg

from lib import config

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


async def _ensure_pool(
    dsn: str | None = None, *, min_size: int = 1, max_size: int = 10
) -> bool:
    """Create the shared pool when it is missing. True means this call created it."""
    global _pool
    async with _pool_lock:
        if _pool is not None:
            return False
        _pool = await asyncpg.create_pool(
            config.database_url(dsn), min_size=min_size, max_size=max_size
        )
        return True


async def connect(
    dsn: str | None = None, *, min_size: int = 1, max_size: int = 10
) -> asyncpg.Pool:
    """Open the shared pool. Calling it twice reuses the open pool."""
    await _ensure_pool(dsn, min_size=min_size, max_size=max_size)
    return pool()


async def disconnect() -> None:
    """Close the shared pool and drop every idle connection."""
    global _pool
    async with _pool_lock:
        if _pool is not None:
            await _pool.close()
            _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("connection pool is not open, await db.connect() first")
    return _pool


async def db_context(dsn: str | None = None) -> AsyncGenerator[asyncpg.Connection]:
    """Borrow a pooled connection for the duration of the block.

    Used outside the app, it opens a throwaway pool and closes it on exit.
    Inside the app the pool comes from ``connect()`` and stays open.
    """
    owns_pool = await _ensure_pool(dsn)
    try:
        async with pool().acquire() as connection:
            yield connection
    finally:
        if owns_pool:
            await disconnect()


async def get_db() -> AsyncGenerator[asyncpg.Connection]:
    """FastAPI dependency that borrows a connection for a single request."""
    async with db_context() as connection:
        yield connection
