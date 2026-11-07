from datetime import datetime, timedelta

import jwt
import pytest
from conftest import FakeConnection, make_app, record
from fastapi.testclient import TestClient

from lib.hash import hash_password
from sqlc.users import GetUserByEmailRow, GetUserByUsernameRow, GetUserRow


def _token(secret: str = "test-secret", user_id: int = 1, role: str = "user") -> str:
    return jwt.encode({"user_id": user_id, "role": role}, secret, algorithm="HS256")


def _client(conn: FakeConnection) -> TestClient:
    return TestClient(make_app(conn))


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("APP_SECRET", "test-secret")
    monkeypatch.setenv("AUTH_METHODS", "password,email_otp,phone_otp")
    monkeypatch.setenv("APP_ENV", "dev")


def test_signup_returns_created_id():
    conn = FakeConnection({"CreateUser": (7,)})

    response = _client(conn).post(
        "/api/auth/signup",
        json={"username": "ada", "email": "ada@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    assert response.json()["data"] == {"id": 7}


def test_password_login_returns_a_token():
    conn = FakeConnection(
        {"GetUserByUsername": record(GetUserByUsernameRow, password_hash=hash_password("pw"))}
    )

    response = _client(conn).post(
        "/api/auth/login", json={"username": "ada", "password": "pw"}
    )

    assert response.status_code == 200
    token = response.json()["data"]["token"]
    assert jwt.decode(token, "test-secret", algorithms=["HS256"])["user_id"] == 1


def test_disabled_auth_method_returns_404(monkeypatch):
    monkeypatch.setenv("AUTH_METHODS", "phone_otp")
    conn = FakeConnection()

    response = _client(conn).post(
        "/api/auth/login", json={"username": "ada", "password": "pw"}
    )

    assert response.status_code == 404
    assert response.json()["errcode"] == "AuthMethodDisabled"


def test_wrong_password_returns_invalid_credentials():
    conn = FakeConnection(
        {
            "GetUserByUsername": record(
                GetUserByUsernameRow, password_hash=hash_password("right")
            )
        }
    )

    response = _client(conn).post(
        "/api/auth/login", json={"username": "ada", "password": "wrong"}
    )

    assert response.status_code == 401
    assert response.json()["errcode"] == "InvalidCredentials"


def test_wrong_otp_returns_invalid_otp():
    conn = FakeConnection(
        {
            "GetUserByEmail": record(
                GetUserByEmailRow,
                otp="424242",
                otp_expires_at=datetime.now() + timedelta(minutes=5),
            )
        }
    )

    response = _client(conn).post(
        "/api/auth/otp/login", json={"email": "ada@example.com", "code": "000000"}
    )

    assert response.status_code == 401
    assert response.json()["errcode"] == "InvalidOtp"


def test_a_malformed_token_returns_invalid_token():
    response = _client(FakeConnection()).get(
        "/api/users/me", headers={"Authorization": "Bearer not-a-jwt"}
    )

    assert response.status_code == 401
    assert response.json()["errcode"] == "InvalidToken"


def test_list_users_requires_the_admin_role():
    response = _client(FakeConnection()).get(
        "/api/users", headers={"Authorization": f"Bearer {_token(role='user')}"}
    )

    assert response.status_code == 403
    assert response.json()["errcode"] == "AdminRequired"


def test_me_returns_user_not_found_for_a_missing_user():
    response = _client(FakeConnection()).get(
        "/api/users/me", headers={"Authorization": f"Bearer {_token()}"}
    )

    assert response.status_code == 404
    assert response.json()["errcode"] == "UserNotFound"


def test_me_requires_a_token():
    response = _client(FakeConnection()).get("/api/users/me")

    assert response.status_code == 401


def test_me_returns_the_current_user():
    conn = FakeConnection({"GetUser": record(GetUserRow)})
    client = _client(conn)

    response = client.get(
        "/api/users/me", headers={"Authorization": f"Bearer {_token()}"}
    )

    assert response.status_code == 200
    assert response.json()["data"]["id_"] == 1


def test_me_serializes_datetimes_and_never_exposes_credentials():
    conn = FakeConnection(
        {"GetUser": record(GetUserRow, created_at=datetime(2024, 1, 2, 3, 4, 5))}
    )

    response = _client(conn).get(
        "/api/users/me", headers={"Authorization": f"Bearer {_token()}"}
    )

    data = response.json()["data"]
    assert data["created_at"] == "2024-01-02T03:04:05"
    assert "password_hash" not in data
    assert "otp" not in data


def test_otp_request_returns_sent_true():
    conn = FakeConnection({"GetUserByEmail": record(GetUserByEmailRow)})

    response = _client(conn).post(
        "/api/auth/otp/request", json={"email": "ada@example.com"}
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"sent": True}


def test_otp_login_returns_a_token():
    conn = FakeConnection(
        {
            "GetUserByEmail": record(
                GetUserByEmailRow,
                otp="424242",
                otp_expires_at=datetime.now() + timedelta(minutes=5),
            )
        }
    )

    response = _client(conn).post(
        "/api/auth/otp/login", json={"email": "ada@example.com", "code": "424242"}
    )

    assert response.status_code == 200
    assert "token" in response.json()["data"]
