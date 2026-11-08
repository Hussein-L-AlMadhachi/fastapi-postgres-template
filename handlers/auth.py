from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse
import asyncpg

from db import get_db
from errors import ErrorCodes
from lib import config
from lib.response import StandardResponse
from features.users import model
from features.users.service import UserAlreadyExists, UsersService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _disabled_method_response(method: str) -> JSONResponse | None:
    if method in config.auth_methods():
        return None
    return StandardResponse(ErrorCodes.AuthMethodDisabled).nolog_error()


@router.post("/signup")
async def signup(body: model.UserSignup, conn: asyncpg.Connection = Depends(get_db)):
    disabled = _disabled_method_response("password")
    if disabled is not None:
        return disabled

    try:
        user_id = await UsersService(conn).create(body)
    except UserAlreadyExists as exc:
        return StandardResponse(ErrorCodes.UserAlreadyExists).error("signup", exc)
    return StandardResponse("ok", {"id": user_id}).success(201)


@router.post("/login")
async def password_login(body: model.PasswordLogin, conn: asyncpg.Connection = Depends(get_db)):
    disabled = _disabled_method_response("password")
    if disabled is not None:
        return disabled

    token = await UsersService(conn).password_login(body)
    if token is None:
        return StandardResponse(ErrorCodes.InvalidCredentials).nolog_error()
    return StandardResponse("ok", {"token": token}).success()


@router.post("/otp/request")
async def request_otp(body: model.OtpRequest, conn: asyncpg.Connection = Depends(get_db)):
    identifier_type, _ = body.identifier()
    disabled = _disabled_method_response(
        "email_otp" if identifier_type == "email" else "phone_otp"
    )
    if disabled is not None:
        return disabled
 
    await UsersService(conn).request_otp(body)
    # Always answer the same way so the endpoint cannot be used to enumerate accounts.
    return StandardResponse("ok", {"sent": True}).success()


@router.post("/otp/login")
async def otp_login(body: model.OtpLogin, conn: asyncpg.Connection = Depends(get_db)):
    identifier_type, _ = body.identifier()
    disabled = _disabled_method_response(
        "email_otp" if identifier_type == "email" else "phone_otp"
    )
    if disabled is not None:
        return disabled

    token = await UsersService(conn).otp_login(body)
    if token is None:
        return StandardResponse(ErrorCodes.InvalidOtp).nolog_error()
    return StandardResponse("ok", {"token": token}).success()
