from dataclasses import fields

from fastapi import FastAPI

import db
import handlers


class FakeConnection:
    """Records every call and answers with the row registered under the query name."""

    def __init__(self, rows: dict[str, object] | None = None):
        self.rows = rows or {}
        self.calls: list[tuple[str, str, tuple]] = []

    def _match(self, sql: str):
        for name, row in self.rows.items():
            if f"-- name: {name} :" in sql:
                return row
        return None

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self._match(sql)

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return self._match(sql) or []

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        return "UPDATE 1"

    def calls_for(self, query_name: str):
        return [call for call in self.calls if f"-- name: {query_name} :" in call[1]]


def record(row_type, **overrides) -> tuple:
    """A fake Record whose values follow the generated dataclass field order."""
    values = {
        "id_": 1,
        "username": "ada",
        "phone_number": "100",
        "email": "ada@example.com",
        "password_hash": None,
        "role": "user",
        "isdisabled": False,
        "deleted_at": None,
        "otp": None,
        "otp_expires_at": None,
        "created_at": None,
        "updated_at": None,
    }
    values.update(overrides)
    return tuple(values[field.name] for field in fields(row_type))


def make_app(conn: FakeConnection) -> FastAPI:
    """A plain app with the real routers/middleware and a fake DB dependency."""
    app = FastAPI()
    handlers.attach(app)

    async def override():
        yield conn

    app.dependency_overrides[db.get_db] = override
    return app
