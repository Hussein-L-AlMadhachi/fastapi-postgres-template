from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, Request
import asyncpg

from db import get_db
from errors import ErrorCodes
from lib.response import StandardResponse
from model.users.service import UsersService

router = APIRouter(prefix="/api/users", tags=["users"])


def _serialize_row(row) -> dict:
    data = asdict(row)
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


@router.get("/me")
async def me(request: Request, conn: asyncpg.Connection = Depends(get_db)):
    user = await UsersService(conn).fetch(request.state.user["user_id"])
    if user is None:
        return StandardResponse(ErrorCodes.UserNotFound).nolog_error()
    return StandardResponse("ok", _serialize_row(user)).success()


@router.get("")
async def list_users(request: Request, conn: asyncpg.Connection = Depends(get_db)):
    if request.state.user.get("role") != "admin":
        return StandardResponse(ErrorCodes.AdminRequired).nolog_error()
    rows = await UsersService(conn).list_all()
    return StandardResponse("ok", [_serialize_row(row) for row in rows]).success()
