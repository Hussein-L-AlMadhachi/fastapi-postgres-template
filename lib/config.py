"""Runtime configuration, read once from the environment.

A local ``.env`` file at the project root is loaded on import, so running the
backend on your machine needs no exports. Real environment variables always win
over the file, which keeps production and CI untouched.
"""

import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "5432"
DEFAULT_USER = "postgres"
DEFAULT_DATABASE = "app"


def database_url(override: str | None = None) -> str:
    """Resolve the Postgres DSN.

    Order: an explicit ``override``, then ``DATABASE_URL``, then a URL built
    from the libpq variables (``PGHOST``, ``PGPORT``, ``PGUSER``,
    ``PGPASSWORD``, ``PGDATABASE``) with local defaults. Using the ``PG*``
    names means ``psql`` picks up the same settings without extra flags.
    """
    if override:
        return _normalize(override)

    url = os.getenv("DATABASE_URL")
    if url:
        return _normalize(url)

    user = quote(os.getenv("PGUSER", DEFAULT_USER), safe="")
    password = os.getenv("PGPASSWORD")
    credentials = f"{user}:{quote(password, safe='')}" if password else user
    host = os.getenv("PGHOST", DEFAULT_HOST)
    port = os.getenv("PGPORT", DEFAULT_PORT)
    name = quote(os.getenv("PGDATABASE", DEFAULT_DATABASE), safe="")
    return f"postgresql://{credentials}@{host}:{port}/{name}"


def _normalize(url: str) -> str:
    """asyncpg rejects the short ``postgres://`` scheme some hosts hand out."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url
