# fastapi-postgres-template

FastAPI + asyncpg + Postgres, with sqlc-generated typed queries and a
configurable auth layer that supports password login, email OTP login and phone
OTP login.

## Setup

```bash
cp .env.example .env
# set APP_SECRET in .env, for example:
openssl rand -hex 32

python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

psql "$DATABASE_URL" -f db/migrations/0001_init_db.up.sql
python main.py
```

Or run everything with containers:

```bash
./run.sh        # podman compose up --build --force-recreate
```

## Layout

| Path              | What it is                                              |
| ----------------- | ------------------------------------------------------- |
| `handlers/`       | HTTP routers (`auth`, `users`)                          |
| `middleware/`     | Bearer token middleware                                 |
| `model/users/`    | DTOs and `UsersService`                                 |
| `lib/`            | config, hashing, OTP senders, response helpers          |
| `db/migrations/`  | SQL schema, applied by hand and parsed by sqlc          |
| `db/queries/`     | sqlc query definitions                                  |
| `sqlc/`           | Generated query functions and row dataclasses           |
| `tests/`          | Service tests and API tests with a fake asyncpg connection |

## Docs

- [Database and sqlc](docs/db.md)
- [Auth flows and configuration](docs/auth.md)

Run the tests with `pytest` (they use a fake connection, so no Postgres is
needed).
