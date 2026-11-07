class HttpError:
    """A client-facing error: a stable label, a human message and a status.

    Instances live as attributes on ``ErrorCodes`` and are passed around
    directly, so a typo is an ``AttributeError`` at import time instead of a
    silent fallback to an internal error at request time.
    """

    label: str
    msg: str
    code: int

    def __init__(self, label: str, msg: str, code: int):
        self.label = label
        self.msg = msg
        self.code = code

    def __repr__(self) -> str:
        return f"HttpError({self.label!r}, {self.code})"
