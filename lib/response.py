from logs import logger

from lib.http_errors import HttpError
from starlette.responses import JSONResponse


class StandardResponse:
    """Builds the JSON envelope every endpoint returns.

    Pass a plain string for a successful response and an ``ErrorCodes`` member
    for an error response. The error path rejects strings on purpose: an unknown
    label used to fall through to a generic 500, which hid real bugs.
    """

    def __init__(self, msg: str | HttpError, data: dict | list | None = None):
        self.msg = msg
        self.data = data

    def success(self, status_code: int = 200) -> JSONResponse:
        return JSONResponse(
            content={
                "detail": self.msg,
                "data": self.data,
            },
            status_code=status_code,
        )

    def log_info(self, action_name: str, msg: str, info=None) -> "StandardResponse":
        logger.info(action_name, msg=msg, info=info)
        return self

    def error(self, action_name: str, err) -> JSONResponse:
        logger.error(action_name, error=str(err), info=self.data)
        return self._error_response()

    def critical(self, action_name: str, err) -> JSONResponse:
        logger.critical(action_name, error=str(err), info=self.data)
        return self._error_response()

    def nolog_error(self) -> JSONResponse:
        return self._error_response()

    def _error_response(self) -> JSONResponse:
        if not isinstance(self.msg, HttpError):
            raise TypeError(
                f"error responses need an ErrorCodes member, got {self.msg!r}. "
                "Use .success() for successful responses."
            )

        return JSONResponse(
            status_code=self.msg.code,
            content={
                "errcode": self.msg.label,
                "detail": self.msg.msg,
            },
        )
