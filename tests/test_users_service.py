"""The service must reach the database only through generated sqlc functions.

These tests use a fake asyncpg connection, so they need no running Postgres.
A fake record is a plain tuple in the field order of the generated row
dataclass, which is the column order the query selects.
"""

from dataclasses import fields
from datetime import datetime, timedelta
from pathlib import Path

import jwt

from lib.hash import hash_password, verify_password
from model.users import service as user_service
from model.users.dto import User
from model.users.service import UsersService
from sqlc.users import (
    GetUserByEmailRow,
    GetUserByPhoneNumberRow,
    GetUserByUsernameRow,
    GetUserRow,
    ListUsersRow,
)


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
        "created_at": None,
        "password_hash": None,
        "isdisabled": False,
        "deleted_at": None,
        "otp": None,
        "otp_expires_at": None,
    }
    values.update(overrides)
    return tuple(values[field.name] for field in fields(row_type))


def test_service_contains_no_sql():
    source = Path(user_service.__file__).read_text()
    for handwritten in ("select ", "SELECT ", "insert into", "INSERT INTO", "update ", "UPDATE ", "delete from"):
        assert handwritten not in source


async def test_create_goes_through_create_user():
    conn = FakeConnection({"CreateUser": (7,)})

    created = await UsersService(conn).create(
        User(id=7, username="ada", phone_number="100", email="ada@example.com", password="pw")
    )

    assert created == 7
    (kind, sql, args) = conn.calls_for("CreateUser")[0]
    assert kind == "fetchrow"
    assert "INSERT INTO users" in sql and "RETURNING id" in sql
    assert args[:4] == (7, "ada", "100", "ada@example.com")
    assert verify_password("pw", args[4])


async def test_list_all_goes_through_list_users():
    conn = FakeConnection({"ListUsers": [record(ListUsersRow)]})

    rows = await UsersService(conn).listAll()

    assert [row.id_ for row in rows] == [1]
    assert [call[0] for call in conn.calls] == ["fetch"]


async def test_fetch_goes_through_get_user():
    conn = FakeConnection({"GetUser": record(GetUserRow)})

    row = await UsersService(conn).fetch(1)

    assert row is not None and row.email == "ada@example.com"
    assert conn.calls_for("GetUser")[0][2] == (1,)


async def test_customer_password_login_returns_a_token():
    conn = FakeConnection(
        {"GetUserByUsername": record(GetUserByUsernameRow, password_hash=hash_password("pw"))}
    )

    token = await UsersService(conn).customerPasswordLogin("ada", "pw")

    assert token is not None
    payload = jwt.decode(token, "secret", algorithms=["HS256"])
    assert payload["user_id"] == 1 and payload["role"] == "customer"


async def test_customer_password_login_rejects_a_wrong_password():
    conn = FakeConnection(
        {"GetUserByUsername": record(GetUserByUsernameRow, password_hash=hash_password("pw"))}
    )

    assert await UsersService(conn).customerPasswordLogin("ada", "nope") is None


async def test_customer_password_login_rejects_a_user_without_a_hash():
    conn = FakeConnection({"GetUserByUsername": record(GetUserByUsernameRow)})

    assert await UsersService(conn).customerPasswordLogin("ada", "pw") is None


async def test_request_otp_by_email_updates_and_sends(monkeypatch):
    sent: list[tuple[str, int]] = []

    async def fake_send(email: str, otp: int):
        sent.append((email, otp))

    monkeypatch.setattr(user_service, "send_otp_email", fake_send)
    conn = FakeConnection({"GetUserByEmail": record(GetUserByEmailRow)})

    assert await UsersService(conn).requestOtp("ada@example.com", None) == 0

    (kind, _, args) = conn.calls_for("SetOtpByEmail")[0]
    assert kind == "execute"
    assert args[0].isdigit() and int(args[0]) < 1_000_000
    assert args[2] == "ada@example.com"
    assert sent == [("ada@example.com", int(args[0]))]


async def test_request_otp_by_phone_updates_and_sends(monkeypatch):
    sent: list[tuple[str, int]] = []

    async def fake_send(phone_number: str, otp: int):
        sent.append((phone_number, otp))

    monkeypatch.setattr(user_service, "send_otp_phone", fake_send)
    conn = FakeConnection({"GetUserByPhoneNumber": record(GetUserByPhoneNumberRow)})

    assert await UsersService(conn).requestOtp(None, "100") == 0

    (kind, _, args) = conn.calls_for("SetOtpByPhoneNumber")[0]
    assert kind == "execute"
    assert args[2] == "100"
    assert sent == [("100", int(args[0]))]


async def test_request_otp_with_both_identifiers_does_nothing():
    conn = FakeConnection()

    assert await UsersService(conn).requestOtp("ada@example.com", "100") is None
    assert conn.calls == []


async def test_request_otp_for_an_unknown_user_sends_nothing(monkeypatch):
    sent: list[tuple[str, int]] = []

    async def fake_send(email: str, otp: int):
        sent.append((email, otp))

    monkeypatch.setattr(user_service, "send_otp_email", fake_send)
    conn = FakeConnection()

    assert await UsersService(conn).requestOtp("nobody@example.com", None) is None
    assert sent == []
    assert conn.calls_for("SetOtpByEmail") == []


async def test_otplogin_rejects_an_expired_code():
    conn = FakeConnection(
        {
            "GetUserByPhoneNumber": record(
                GetUserByPhoneNumberRow,
                otp="4242",
                otp_expires_at=datetime.now() - timedelta(minutes=1),
            )
        }
    )

    assert await UsersService(conn).otplogin(None, "100") is None


async def test_otplogin_rejects_a_missing_expiry():
    conn = FakeConnection({"GetUserByPhoneNumber": record(GetUserByPhoneNumberRow, otp="4242")})

    assert await UsersService(conn).otplogin(None, "100") is None


async def test_otplogin_returns_token_and_user():
    conn = FakeConnection(
        {
            "GetUserByPhoneNumber": record(
                GetUserByPhoneNumberRow,
                otp="4242",
                otp_expires_at=datetime.now() + timedelta(minutes=5),
            )
        }
    )

    result = await UsersService(conn).otplogin(None, "100")

    assert result is not None
    assert result["user"].id_ == 1
    assert jwt.decode(result["token"], "secret", algorithms=["HS256"])["user_id"] == 1
