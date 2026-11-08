from fastapi import APIRouter, Depends, Request
import asyncpg

from db import get_db
from errors import ErrorCodes
from lib.response import StandardResponse
from features.users.model import UserListItemOut, UserOut
import features.users.service as users_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me")
async def me(request: Request, conn: asyncpg.Connection = Depends(get_db)):
    user = await users_service.fetch(conn, request.state.user["user_id"])
    if user is None:
        return StandardResponse(ErrorCodes.UserNotFound).nolog_error()
    return StandardResponse("ok", UserOut.model_validate(user)).success()


@router.get("")
async def list_users(request: Request, conn: asyncpg.Connection = Depends(get_db)):
    if request.state.user.get("role") != "admin":
        return StandardResponse(ErrorCodes.AdminRequired).nolog_error()

    rows = await users_service.list_all()
    users = [UserListItemOut.model_validate(row) for row in rows]
    return StandardResponse("ok", users).success()
