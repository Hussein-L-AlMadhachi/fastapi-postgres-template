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

ALLOWED_AUTH_METHODS = frozenset({"password", "email_otp", "phone_otp"})
DEFAULT_AUTH_METHODS = ("password", "email_otp", "phone_otp")


def database_url(override: str | None = None) -> str:
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
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def app_secret() -> str:
    secret = os.getenv("APP_SECRET")
    if not secret:
        raise RuntimeError("APP_SECRET is not set")
    return secret


def auth_methods() -> set[str]:
    raw = os.getenv("AUTH_METHODS")
    if raw is None:
        return set(DEFAULT_AUTH_METHODS)
    return {name.strip() for name in raw.split(",") if name.strip() in ALLOWED_AUTH_METHODS}


def otp_ttl_minutes() -> int:
    return _int_env("OTP_TTL_MINUTES", 5)


def access_token_ttl_hours() -> int:
    return _int_env("ACCESS_TOKEN_TTL_HOURS", 24)


def otp_auto_signup() -> bool:
    return _bool_env("AUTH_OTP_AUTO_SIGNUP", True)


def app_env() -> str:
    return os.getenv("APP_ENV", "dev")


def is_dev() -> bool:
    return app_env().lower() in {"dev", "development", "local"}


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
