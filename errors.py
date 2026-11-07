from lib.http_errors import HttpError


class ErrorCodes:
    """Every error the API can return.

    ``label`` is what clients receive as ``errcode``, ``msg`` is the human
    readable ``detail`` and ``code`` is the HTTP status.
    """

    # Generic.
    BadRequest = HttpError("BadRequest", "bad request", 400)
    UnAuthorized = HttpError("UnAuthorized", "failed to log in", 401)
    Forbidden = HttpError("Forbidden", "Access is forbidden. contact administrator", 403)
    NotFound = HttpError("NotFound", "404 not found", 404)
    Conflict = HttpError("Conflict", "already exists", 409)
    UserLoggedOut = HttpError("UserLoggedOut", "you have to login first", 403)
    TechnicalIssue = HttpError("TechnicalIssue", "we will be back soon", 501)

    # Signup and login.
    InvalidCredentials = HttpError("InvalidCredentials", "invalid username or password", 401)
    InvalidOtp = HttpError("InvalidOtp", "invalid or expired code", 401)
    AuthMethodDisabled = HttpError("AuthMethodDisabled", "auth method is disabled", 404)
    UserAlreadyExists = HttpError(
        "UserAlreadyExists", "username, email or phone number already in use", 409
    )

    # Sessions and authorization.
    InvalidToken = HttpError("InvalidToken", "invalid or expired session", 401)
    AdminRequired = HttpError("AdminRequired", "admin role required", 403)
    UserNotFound = HttpError("UserNotFound", "user not found", 404)

    # Server.
    ServerMisconfigured = HttpError("ServerMisconfigured", "server is misconfigured", 500)
