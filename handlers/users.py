from fastapi import APIRouter, Depends, Request
import asyncpg

from db import get_db
from errors import ErrorCodes
from lib.response import StandardResponse
from model.users.dto import UserListItemOut, UserOut
from model.users.service import UsersService

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me")
async def me(request: Request, conn: asyncpg.Connection = Depends(get_db)):
    user = await UsersService(conn).fetch(request.state.user["user_id"])
    if user is None:
        return StandardResponse(ErrorCodes.UserNotFound).nolog_error()
    return StandardResponse("ok", UserOut.model_validate(user)).success()


@router.get("")
async def list_users(request: Request, conn: asyncpg.Connection = Depends(get_db)):
    if request.state.user.get("role") != "admin":
        return StandardResponse(ErrorCodes.AdminRequired).nolog_error()

    rows = await UsersService(conn).list_all()
    users = [UserListItemOut.model_validate(row) for row in rows]
    return StandardResponse("ok", users).success()
