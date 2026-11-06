import os

import jwt
from starlette.datastructures import Headers

from lib.auth import parse_bearer_token
from lib.response import StandardResponse
from errors import ErrorCodes



class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope["path"]
        if not (path == "/api" or path.startswith("/api/")):
            return await self.app(scope, receive, send)

        headers = Headers(scope=scope)
        token = headers.get("Authorization")
        token = parse_bearer_token(token)
        if not token:
            response = StandardResponse(ErrorCodes.UnAuthorized, {"reason":"bad token"}).nolog_error("AuthMiddleware")
            return await response(scope, receive, send)            

        secret = os.environ.get("APP_SECRET")
        if not secret:
            response = StandardResponse(ErrorCodes.TechnicalIssue, {"reason":"no secret configured"}).error("AuthMiddleware")
            return await response(scope, receive, send)            

        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except Exception:
            response = StandardResponse(ErrorCodes.UnAuthorized, {"reason":"bad token"}).nolog_error("AuthMiddleware")
            return await response(scope, receive, send)

        scope.setdefault("state", {})["user"] = payload

        return await self.app(scope, receive, send)

