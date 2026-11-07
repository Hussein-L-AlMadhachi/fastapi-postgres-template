import jwt
from starlette.datastructures import Headers

from errors import ErrorCodes
from lib import config
from lib.auth import parse_bearer_token
from lib.response import StandardResponse


PUBLIC_PATHS = {"/", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}
PUBLIC_API_PREFIX = "/api/auth/"


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_API_PREFIX)


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope["path"]
        if not (path == "/api" or path.startswith("/api/")):
            return await self.app(scope, receive, send)

        if scope["method"] == "OPTIONS" or is_public_path(path):
            return await self.app(scope, receive, send)

        headers = Headers(scope=scope)
        token = parse_bearer_token(headers.get("Authorization"))
        if not token:
            response = StandardResponse(ErrorCodes.InvalidToken).nolog_error()
            return await response(scope, receive, send)

        try:
            secret = config.app_secret()
        except RuntimeError as exc:
            response = StandardResponse(ErrorCodes.ServerMisconfigured).error(
                "AuthMiddleware", exc
            )
            return await response(scope, receive, send)

        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            response = StandardResponse(ErrorCodes.InvalidToken).nolog_error()
            return await response(scope, receive, send)

        if not isinstance(payload, dict) or "user_id" not in payload:
            response = StandardResponse(ErrorCodes.InvalidToken).nolog_error()
            return await response(scope, receive, send)

        scope.setdefault("state", {})["user"] = payload

        return await self.app(scope, receive, send)
