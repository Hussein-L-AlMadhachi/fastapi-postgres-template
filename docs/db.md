# Database

Postgres, `asyncpg`, and **sqlc** for queries. There is no hand-written query
string anywhere in the app code: SQL lives in `queries/*.sql`, and
`sqlc generate` turns it into typed Python in `generated/`.

## Layout

| Path             | What it is                                                    |
| ---------------- | ------------------------------------------------------------- |
| `migrations/`    | Plain SQL DDL, applied by hand. Also sqlc's schema source.      |
| `queries/*.sql`  | Named queries with sqlc annotations (`:one`, `:many`, `:exec`). |
| `generated/`     | Output of `sqlc generate`. Committed. Never edit by hand.       |
| `db.py`          | Pool lifecycle only: `connect`, `disconnect`, `pool`, `get_db`. |

`schema: "migrations"` means every `.sql` file in that directory is parsed as
schema. Keep new tables there so sqlc can see them.

## The workflow

1. Write the table in a migration file, e.g. `migrations/0002_add_sessions.up.sql`.
2. Write the query in `queries/<domain>.sql`:

   ```sql
   -- name: CreateSession :one
   INSERT INTO sessions (user_id, token_hash, expires_at)
   VALUES (sqlc.arg(user_id), sqlc.arg(token_hash), sqlc.arg(expires_at))
   RETURNING id, user_id, expires_at;
   ```

3. Run it:

   ```bash
   sqlc generate        # add -f sqlc.yaml if you keep the config elsewhere
   ```

4. The plugin drops a module per query file into `generated/`, plus
   `generated/models.py` with a dataclass per table.

`sqlc vet` runs the same parse pass and catches bad SQL without writing files.

## Calling generated code

Functions take the connection as the first argument and keyword-only params:

```python
import asyncpg
from fastapi import APIRouter, Depends

from db import get_db
from generated.users import get_user

router = APIRouter()


@router.get("/users/{user_id}")
async def read_user(user_id: int, conn: asyncpg.Connection = Depends(get_db)):
    user = await get_user(conn, user_id=user_id)   # GetUserRow | None
    ...
```

The pool itself is opened once by the lifespan in `server.py`; `get_db` borrows
one connection per request and returns it when the request ends. Nothing in the
app closes the pool per request.

## Things sqlc does to names

- `id` becomes `id_` on the generated dataclass (`id_ : int`), because `id` is a
  builtin. Query rows are also suffixed with the query name: `GetUserRow`.
- Columns keep their SQL types: `decimal` becomes `decimal.Decimal`, `TIMESTAMP`
  becomes `datetime.datetime`. Pydantic models are not generated; convert in the
  handler if the response shape differs from the row.
- A `:one` query that matches nothing returns `None`, not an exception. Check it.
  A failed statement (bad SQL, dropped connection, constraint violation) raises.

## Configuration

`lib/config.py` resolves the DSN: an explicit `dsn` argument, then
`DATABASE_URL`, then a URL built from `PGHOST`, `PGPORT`, `PGUSER`,
`PGPASSWORD`, `PGDATABASE`. A `.env` file at the project root is loaded on
import; real environment variables always win over it.

`sqlc.yaml` pins the plugin by URL and sha256, so the first `sqlc generate` on a
new machine downloads the wasm and every later run is offline.

## Migrations

There is no migration tool. Apply them yourself:

```bash
psql "$DATABASE_URL" -f migrations/0001_init_db.up.sql
psql "$DATABASE_URL" -f migrations/0001_init_db.down.sql
```

`users.id` is a plain `bigint primary key` with no identity/default, so inserts
into `users` must supply `id` explicitly until that changes.
