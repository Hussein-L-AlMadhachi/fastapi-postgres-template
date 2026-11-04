"""Async Postgres access: one shared connection pool plus a small query wrapper.

A single connection is borrowed per request. Query parameters use native
Postgres placeholders (``$1``, ``$2``, ...), so write SQL the way psql expects
it. Credentials come from ``lib/config.py``, which reads the environment and a
local ``.env``. Schema changes are not automated: run the SQL in ``migrations/``
yourself.
"""

import asyncio
import json
import re
from collections.abc import AsyncGenerator, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any, TypeAlias

import asyncpg

from lib import config

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

Row: TypeAlias = dict[str, Any]

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


def _adapt(value: Any) -> Any:
    """Postgres takes JSON as text; every other type maps over natively."""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, default=str)
    return value


def _quote_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"invalid sql identifier: {name!r}")
    return f'"{name}"'


def _build_insert(table: str, columns: Sequence[str], returning: bool) -> str:
    quoted = ", ".join(_quote_identifier(column) for column in columns)
    placeholders = ", ".join(f"${index}" for index in range(1, len(columns) + 1))
    statement = f"INSERT INTO {_quote_identifier(table)} ({quoted}) VALUES ({placeholders})"
    return f"{statement} RETURNING *" if returning else statement


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


@asynccontextmanager
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


class DB:
    """Async wrapper around one asyncpg connection.

    Statements commit on their own unless they run inside ``DB.transaction()``.
    Query helpers return plain dicts.
    """

    connection: asyncpg.Connection

    def __init__(self, connection: asyncpg.Connection):
        self.connection = connection

    # -- raw statements ----------------------------------------------------

    async def execute(self, sql: str, *parameters: Any) -> str:
        """Run one statement and return the Postgres status tag (``INSERT 0 1``)."""
        return await self.connection.execute(sql, *self._params(parameters))

    async def executemany(
        self, sql: str, parameters: Iterable[Sequence[Any]]
    ) -> int:
        rows = [self._params(row) for row in parameters]
        if not rows:
            return 0
        await self.connection.executemany(sql, rows)
        return len(rows)

    async def executescript(self, sql: str) -> None:
        """Run several semicolon-separated statements. No parameters allowed."""
        await self.connection.execute(sql)

    # -- reads -------------------------------------------------------------

    async def fetchOne(self, sql: str, *parameters: Any) -> Row | None:
        row = await self.connection.fetchrow(sql, *self._params(parameters))
        return None if row is None else dict(row)

    async def fetchAll(self, sql: str, *parameters: Any) -> list[Row]:
        rows = await self.connection.fetch(sql, *self._params(parameters))
        return [dict(row) for row in rows]

    async def fetchMany(self, sql: str, size: int, *parameters: Any) -> list[Row]:
        """First ``size`` rows, read through a server-side cursor."""
        if size <= 0:
            raise ValueError("size must be a positive integer")

        async with self.connection.transaction():
            async with self.connection.cursor(
                sql, *self._params(parameters)
            ) as cursor:
                rows = await cursor.fetch(size)
        return [dict(row) for row in rows]

    async def iterate(
        self, sql: str, *parameters: Any, size: int = 256
    ) -> AsyncGenerator[Row]:
        """Stream rows in chunks instead of materialising the whole result."""
        if size <= 0:
            raise ValueError("size must be a positive integer")

        async with self.connection.transaction():
            async with self.connection.cursor(
                sql, *self._params(parameters)
            ) as cursor:
                while True:
                    rows = await cursor.fetch(size)
                    if not rows:
                        break
                    for row in rows:
                        yield dict(row)

    async def scalar(self, sql: str, *parameters: Any) -> Any:
        """First column of the first row, or None when nothing matches."""
        return await self.connection.fetchval(sql, *self._params(parameters))

    async def pluck(self, sql: str, *parameters: Any) -> list[Any]:
        """First column of every row."""
        rows = await self.connection.fetch(sql, *self._params(parameters))
        return [row[0] for row in rows]

    async def exists(self, sql: str, *parameters: Any) -> bool:
        return await self.scalar(sql, *parameters) is not None

    # -- writes ------------------------------------------------------------

    async def insert(self, table: str, values: Mapping[str, Any]) -> Row:
        """Insert one row and return it (``INSERT ... RETURNING *``)."""
        if not values:
            raise ValueError("nothing to insert")

        sql = _build_insert(table, list(values), returning=True)
        row = await self.connection.fetchrow(sql, *self._params(values.values()))
        if row is None:
            raise RuntimeError(f"insert into {table!r} returned no row")
        return dict(row)

    async def insertMany(self, table: str, rows: Sequence[Mapping[str, Any]]) -> int:
        """Insert several rows with the same columns, return the number of rows."""
        if not rows:
            return 0

        columns = list(rows[0])
        try:
            parameters = [tuple(row[column] for column in columns) for row in rows]
        except KeyError as missing:
            raise ValueError(f"row is missing column {missing.args[0]!r}") from None

        return await self.executemany(
            _build_insert(table, columns, returning=False), parameters
        )

    # -- schema introspection ----------------------------------------------

    async def tables(self) -> list[str]:
        return await self.pluck(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )

    async def columns(self, table: str) -> list[Row]:
        _quote_identifier(table)  # same friendly error as the write helpers
        rows = await self.connection.fetch(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = $1 "
            "ORDER BY ordinal_position",
            table,
        )
        return [dict(row) for row in rows]

    # -- transactions ------------------------------------------------------

    @property
    def in_transaction(self) -> bool:
        return self.connection.is_in_transaction()

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator["DB"]:
        """Group writes into one transaction: commit on success, rollback on error."""
        async with self.connection.transaction():
            yield self

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _params(parameters: Iterable[Any]) -> tuple[Any, ...]:
        return tuple(_adapt(value) for value in parameters)
