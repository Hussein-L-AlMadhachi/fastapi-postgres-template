from lib.http_errors import HttpError

class ErrorCodes:
    NotFound = HttpError("404 not found", 404)
    Forbidden = HttpError("Access is forbidden. contact administrator", 403)
    BadRequest = HttpError("bad request", 400)
    UserLoggedOut = HttpError("you have to login first", 403)
    UnAuthorized = HttpError("failed to log in", 403)
    TechnicalIssue = HttpError("we will be back soon", 501)
