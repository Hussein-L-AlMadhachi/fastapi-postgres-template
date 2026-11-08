# Database

Postgres, `asyncpg`, and **sqlc** for queries. No service builds a SQL string:
SQL lives in `db/queries/*.sql`, and `sqlc generate` turns it into typed Python
in `sqlc/`.

## Layout

| Path | What it is |
| --- | --- |
| `db/migrations/` | Plain SQL DDL, applied by hand. Also sqlc's schema source. |
| `db/queries/*.sql` | Named queries with sqlc annotations (`:one`, `:many`, `:exec`). |
| `sqlc/` | Output of `sqlc generate`. Committed. Never edit by hand. |
| `db.py` | Pool lifecycle: `connect`, `disconnect`, `pool`, `db_context`, `get_db`. |

`schema: "db/migrations"` means every `.sql` file in that directory is parsed
as schema, including down migrations. Keep new tables in an up migration there
so sqlc can see them.

## The workflow

1. Write the table change in a migration file, for example
   `db/migrations/0002_add_sessions.up.sql`, plus a matching down file.
2. Write the query in `db/queries/<domain>.sql`:

   ```sql
   -- name: CreateSession :one
   INSERT INTO sessions (user_id, token_hash, expires_at)
   VALUES (@user_id, @token_hash, @expires_at)
   RETURNING id;
   ```

3. Run it:

   ```bash
   sqlc generate
   ```

4. The plugin drops a module per query file into `sqlc/`, plus `sqlc/models.py`
   with a dataclass per table.

`sqlc vet` runs the same parse pass and catches bad SQL without writing files.
`sqlc compile` checks the configuration and queries without generating output.

## Calling generated code

Functions take the connection as the first argument and keyword-only params:

```python
import asyncpg

from sqlc.users import get_user

user = await get_user(conn, user_id=user_id)   # GetUserRow | None
```

Inside a request, the connection comes from `get_db`. Service functions take
that connection as their first argument and call the generated functions:

```python
from db import get_db
from fastapi import APIRouter, Depends
from features.users.service import fetch

router = APIRouter()


@router.get("/users/{user_id}")
async def read_user(user_id: int, conn: asyncpg.Connection = Depends(get_db)):
    user = await fetch(conn, user_id)
    ...
```

## Connection pool

`db.py` owns the pool. `connect()` creates it once, `disconnect()` closes it,
and repeated `connect()` calls reuse the open pool. `server.py` opens the pool
in the FastAPI lifespan and closes it on shutdown.

`get_db` is the request dependency. It borrows one connection from the pool and
returns it when the request ends. The pool defaults to `min_size=1` and
`max_size=10`; `connect` and `db_context` accept overrides for scripts and
tests. `db_context` opens a throwaway pool when none exists and closes only the
pool it created.

## Schema

`users` is the only table.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `bigint identity` | primary key, inserts do not supply it |
| `username` | `varchar(127)` | nullable, unique |
| `phone_number` | `varchar(31)` | nullable, unique |
| `email` | `varchar(511)` | nullable, unique |
| `role` | `varchar(31)` | not null, defaults to `user` |
| `password_hash` | `char(100)` | nullable, argon2id is about 98 characters |
| `otp` | `varchar(12)` | nullable, plain text six digit code |
| `otp_expires_at` | `timestamp` | nullable |
| `isdisabled` | `boolean` | not null, defaults to `false` |
| `created_at` | `timestamp` | defaults to `now()` |
| `updated_at` | `timestamp` | defaults to `now()`, touched by OTP updates |
| `deleted_at` | `timestamp` | nullable, soft delete marker |

`users_identity_check` requires at least one of `username`, `email` or
`phone_number`, which is what lets the same table serve password, email OTP and
phone OTP accounts. All three identity columns are nullable and unique, so an
empty value must be stored as `NULL`, not `''`.

Every read query filters `isdisabled = false AND deleted_at IS NULL`. Disabling
or soft deleting a user therefore hides it from login, `/api/users` and
`/api/users/me`.

## Generated names

- `id` becomes `id_` on the generated dataclass, because `id` is a builtin.
- Query rows are suffixed with the query name: `GetUserRow`, `ListUsersRow`,
  `GetUserByEmailRow`.
- Columns keep their SQL types: `decimal` becomes `decimal.Decimal`, `timestamp`
  becomes `datetime.datetime`. Pydantic models are not generated; convert in the
  handler or service when the response shape differs from the row.
- A `:one` query that matches nothing returns `None`, not an exception. Check
  it. A failed statement (bad SQL, dropped connection, constraint violation)
  raises.

The committed `sqlc/models.py` also contains an `Item` dataclass left over from
the removed `items` table. It is unused. Run `sqlc generate` to refresh the
output after a schema change and the stale model disappears.

## Configuration

`lib/config.py` resolves the DSN: an explicit override, then `DATABASE_URL`,
then a URL built from `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`.
A `.env` file at the project root is loaded on import; real environment
variables win over it.

The same module exposes the auth knobs: `app_secret()`, `auth_methods()`,
`otp_ttl_minutes()`, `access_token_ttl_hours()`, `otp_auto_signup()`,
`app_env()` and `is_dev()`. The full table is in the [README](../README.md).

`sqlc.yaml` pins the Python plugin by URL and sha256, so the first
`sqlc generate` on a new machine downloads the wasm and later runs are offline.

## Migrations

There is no migration tool. Apply them yourself:

```bash
psql "$DATABASE_URL" -f db/migrations/0001_init_db.up.sql
psql "$DATABASE_URL" -f db/migrations/0001_init_db.down.sql
```

With compose, the same files are mounted at `/migrations`:

```bash
podman compose exec db psql -U postgres -d app -f /migrations/0001_init_db.up.sql
```

The down file is for manual resets only; it drops `users`.
