# Lamma Marketplace BE

FastAPI + asyncpg + Postgres, with sqlc-generated typed queries and a
configurable auth layer that supports password login, email OTP login and phone
OTP login.

## Requirements

- Python 3.12 or newer (the container image uses 3.14)
- Postgres
- `sqlc` only when you change migrations or queries

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Create `.env` in the project root with at least a signing secret:

```bash
printf 'APP_SECRET=%s\n' "$(openssl rand -hex 32)" > .env
```

Apply the schema, then start the server:

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app
psql "$DATABASE_URL" -f db/migrations/0001_init_db.up.sql
python main.py
```

`main.py` starts uvicorn with reload on `127.0.0.1:8000`. Without reload:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

When `DATABASE_URL` is not set, the DSN is built from `PGHOST`, `PGPORT`,
`PGUSER`, `PGPASSWORD` and `PGDATABASE`. A `.env` file at the project root is
loaded on import, and real environment variables win over it.

## Containers

```bash
./run.sh
```

`run.sh` refuses to start when `APP_SECRET` is missing from `.env`, then runs
`podman compose up --build --force-recreate`. The same compose file works with
`docker compose`.

Migrations are mounted into the database container at `/migrations` but are not
applied automatically:

```bash
podman compose exec db psql -U postgres -d app -f /migrations/0001_init_db.up.sql
```

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_SECRET` | none, required | HS256 key for access tokens. When missing, protected requests answer `500 ServerMisconfigured` and password or OTP login fails. Generate with `openssl rand -hex 32`. |
| `APP_ENV` | `dev` | `dev`, `development` and `local` count as development, where OTP senders log the code. Compose sets it to `prod`. |
| `DATABASE_URL` | built from `PG*` | Full DSN. A `postgres://` prefix is rewritten to `postgresql://`. |
| `PGHOST` | `localhost` | Used when `DATABASE_URL` is unset. |
| `PGPORT` | `5432` | Used when `DATABASE_URL` is unset. |
| `PGUSER` | `postgres` | Used when `DATABASE_URL` is unset. |
| `PGPASSWORD` | empty | Used when `DATABASE_URL` is unset. |
| `PGDATABASE` | `app` | Used when `DATABASE_URL` is unset. |
| `AUTH_METHODS` | `password,email_otp,phone_otp` | Comma separated. Unknown names are dropped. A disabled flow answers `404 AuthMethodDisabled`. |
| `AUTH_OTP_AUTO_SIGNUP` | `true` | Create a bare user when an unknown email or phone requests a code. |
| `OTP_TTL_MINUTES` | `5` | Values of zero or less fall back to the default. |
| `ACCESS_TOKEN_TTL_HOURS` | `24` | Values of zero or less fall back to the default. |

Settings live in `lib/config.py` and are read from the environment on each
call.

## API

Every response uses one envelope:

- success: `{"detail": "ok", "data": ...}`
- handled error: `{"errcode": "<label>", "detail": "<message>"}`

Pydantic validation failures keep the FastAPI default shape,
`422 {"detail": [...]}`.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/` | public | service version |
| `POST` | `/api/auth/signup` | public | password signup |
| `POST` | `/api/auth/login` | public | password login |
| `POST` | `/api/auth/otp/request` | public | send a login code |
| `POST` | `/api/auth/otp/login` | public | log in with a code |
| `GET` | `/api/users/me` | bearer token | current user |
| `GET` | `/api/users` | bearer token, `admin` role | active users |

Interactive docs are served at `/docs`, with `/openapi.json` and `/redoc`
alongside. Those paths and `/api/auth/*` bypass the bearer middleware.

Auth flows, validation rules and the error table: [docs/auth.md](docs/auth.md).

## Services

Services are module-level functions under `features/`, not classes. Each one
takes an `asyncpg` connection first, then request models or plain values, and
returns plain values or sqlc row dataclasses:

```python
from features.users.service import fetch

user = await fetch(conn, request.state.user["user_id"])
```

Handlers get the connection from the `get_db` dependency and pass it down.
Services never build SQL strings; every statement comes from `sqlc/`. The user
service lives in `features/users/service.py`, and its request and response
models live in `features/users/model.py`.

## Layout

| Path | What it is |
| --- | --- |
| `features/users/` | request and response models, service functions |
| `handlers/` | HTTP routers (`auth`, `users`, `index`) |
| `middleware/` | bearer token middleware |
| `lib/` | config, hashing, OTP senders, response helpers |
| `db/migrations/` | SQL schema, applied by hand and parsed by sqlc |
| `db/queries/` | sqlc query definitions |
| `sqlc/` | generated query functions and row dataclasses |
| `jobs/` | placeholder for background jobs |
| `docs/` | database and auth notes |

After changing a migration or a query, run `sqlc generate` and commit the
updated `sqlc/` output.

## Docs

- [Database and sqlc](docs/db.md)
- [Auth flows and configuration](docs/auth.md)
