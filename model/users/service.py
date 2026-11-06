"""User queries, all resolved through the sqlc-generated functions.

Every statement lives in ``queries/users.sql``. Nothing in this module builds
SQL strings: edit the .sql file and re-run ``sqlc generate``.
"""

from datetime import datetime, timedelta

import asyncpg
import jwt
import secrets

from sqlc import users as queries
from lib.hash import hash_password, verify_password
from lib.otp.email import send_otp_email
from lib.otp.phone import send_otp_phone
from model.users import dto





dummy_hash = hash_password("277e559b25561148f616550ee0aa34020c0397ea8db30e2000a8583a17742c21")





class UsersService:
    conn: asyncpg.Connection

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn


    async def create(self, user: dto.User) -> int | None:
        return await queries.create_user(
            self.conn,
            id_=user.id,
            username=user.username,
            phone_number=user.phone_number,
            email=user.email,
            password_hash=hash_password(user.password),
            role = "user"
        )


    async def listAll(self) -> list[queries.ListUsersRow]:
        return list(await queries.list_users(self.conn))


    async def fetch(self, user_id: int) -> queries.GetUserRow | None:
        return await queries.get_user(self.conn, user_id=user_id)


    async def customerPasswordLogin(self, username: str, password: str) -> str | None:
        try:
            user = await queries.get_user_by_username(self.conn, username=username)
        except:
            # prevent timing attacks
            verify_password(password, dummy_hash)
            return None

        if user is None:
            verify_password(password, dummy_hash)
            return None

        if user.password_hash is None:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return self._token(user.id_)


    async def requestOtp(self, email: str | None, phone_number: str | None) -> int | None:
        otpcode = secrets.randbelow(1_000_000)
        otp_expiry = datetime.now() + timedelta(minutes=5)

        if email is None:
            try:
                user = await queries.get_user_by_phone_number(
                    self.conn, phone_number=phone_number
                )
            except:
                return None
        elif phone_number is None:
            try:
                user = await queries.get_user_by_email(self.conn, email=email)
            except:
                return None
        else:
            return None

        if user is None:
            return None

        if email is None:
            await queries.set_otp_by_phone_number(
                self.conn,
                otp_code=str(otpcode),
                otp_expires_at=otp_expiry,
                phone_number=phone_number,
            )
            await send_otp_phone(phone_number, otpcode)
        else:
            await queries.set_otp_by_email(
                self.conn,
                otp_code=str(otpcode),
                otp_expires_at=otp_expiry,
                email=email,
            )
            await send_otp_email(email, otpcode)

        return 0


    async def otplogin(
        self, email: str | None, phone_number: str | None
    ) -> dict | None:
        if email is None:
            try:
                user = await queries.get_user_by_phone_number(
                    self.conn, phone_number=phone_number
                )
            except:
                return None
        elif phone_number is None:
            try:
                user = await queries.get_user_by_email(self.conn, email=email)
            except:
                return None
        else:
            return None

        if user is None:
            return None

        if user.otp_expires_at is None or user.otp_expires_at <= datetime.now():
            return None

        return {
            "token": self._token(user.id_),
            "user": user,
        }


    def _token(self, user_id: int) -> str:
        return jwt.encode(
            {
                "user_id": int(user_id),
                "exp": datetime.now() + timedelta(hours=24),
                "role": "customer",
            },
            "secret",
            algorithm="HS256",
        )

