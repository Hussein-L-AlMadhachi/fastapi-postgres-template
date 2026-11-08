"""User queries, all resolved through the sqlc-generated functions.

Every statement lives in ``db/queries/users.sql``. Nothing in this module builds
SQL strings: edit the .sql file and re-run ``sqlc generate``.
"""

from datetime import datetime, timedelta, timezone

import asyncpg
import jwt
import secrets

from lib import config
from lib.hash import hash_password, verify_password
from lib.otp.email import send_otp_email
from lib.otp.phone import send_otp_phone
from features.users import model
from sqlc import users as queries


dummy_hash = hash_password("277e559b25561148f616550ee0aa34020c0397ea8db30e2000a8583a17742c21")


class UserAlreadyExists(Exception):
    """Raised when a unique identity column is taken."""


async def _find_for_otp(
    conn: asyncpg.Connection, identifier_type: model.OtpIdentifierType, value: str
) -> queries.GetUserByEmailRow | queries.GetUserByPhoneNumberRow | None:
    if identifier_type == "email":
        return await queries.get_user_by_email(conn, email=value)
    return await queries.get_user_by_phone_number(conn, phone_number=value)


def _generate_token(user_id: int, role: str) -> str:
    return jwt.encode(
        {
            "user_id": int(user_id),
            "role": role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=config.access_token_ttl_hours()),
        },
        config.app_secret(),
        algorithm="HS256",
    )


async def _find_for_password(
    conn: asyncpg.Connection, login: model.PasswordLogin
) -> queries.GetUserByUsernameRow | queries.GetUserByEmailRow | queries.GetUserByPhoneNumberRow | None:
    
    identifier_type, value = login.identifier()
    if identifier_type == "username":
        return await queries.get_user_by_username(conn, username=value)
    if identifier_type == "email":
        return await queries.get_user_by_email(conn, email=value)
    return await queries.get_user_by_phone_number(conn, phone_number=value)







async def list_all(conn: asyncpg.Connection) -> list[queries.ListUsersRow]:
    return await queries.list_users(conn)


async def fetch(conn: asyncpg.Connection, user_id: int) -> queries.GetUserRow | None:
    return await queries.get_user(conn, user_id=user_id)


async def password_login(conn: asyncpg.Connection, login: model.PasswordLogin) -> str | None:
    user = await _find_for_password(conn, login)
    if user is None or user.password_hash is None:
        # Run a real verification so a missing account costs the same time.
        verify_password(login.password, dummy_hash)
        return None

    if not verify_password(login.password, user.password_hash):
        return None

    return _generate_token(user.id_, user.role)


# user requests the OTP first then verifies it with otp_login()
async def request_otp(conn: asyncpg.Connection, request: model.OtpRequest) -> bool:
    identifier_type, value = request.identifier()
    otp_code = f"{secrets.randbelow(1_000_000):06d}"
    otp_expires_at = datetime.now() + timedelta(minutes=config.otp_ttl_minutes())

    user = await _find_for_otp(conn, identifier_type, value)
    if user is None:
        if not config.otp_auto_signup():
            return False
        try:
            await queries.create_user(
                conn,
                username=None,
                phone_number=value if identifier_type == "phone_number" else None,
                email=value if identifier_type == "email" else None,
                password_hash=None,
                role="user",
            )
        except asyncpg.UniqueViolationError:
            return False

    if identifier_type == "email":
        await queries.set_otp_by_email(
            conn,
            otp_code=otp_code,
            otp_expires_at=otp_expires_at,
            email=value,
        )
        await send_otp_email(value, otp_code)
    else:
        await queries.set_otp_by_phone_number(
            conn,
            otp_code=otp_code,
            otp_expires_at=otp_expires_at,
            phone_number=value,
        )
        await send_otp_phone(value, otp_code)

    return True


async def otp_login(conn: asyncpg.Connection, login: model.OtpLogin) -> str | None:
    identifier_type, value = login.identifier()
    user = await _find_for_otp(conn, identifier_type, value)

    if user is None or user.otp is None or user.otp_expires_at is None:
        return None
    if user.otp_expires_at <= datetime.now():
        return None
    if not secrets.compare_digest(user.otp, login.code):
        return None

    if identifier_type == "email":
        await queries.clear_otp_by_email(conn, email=value)
    else:
        await queries.clear_otp_by_phone_number(conn, phone_number=value)

    return _generate_token(user.id_, user.role)


async def create(conn: asyncpg.Connection, user: model.UserSignup) -> int:
    try:
        user_id = await queries.create_user(
            conn,
            username=user.username,
            phone_number=user.phone_number,
            email=user.email,
            password_hash=hash_password(user.password),
            role="user",
        )
    except asyncpg.UniqueViolationError as exc:
        raise UserAlreadyExists("username, email or phone number already in use") from exc

    if user_id is None:
        raise RuntimeError("create_user returned no id")
    return user_id


