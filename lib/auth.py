
def parse_bearer_token(auth: str | None) -> str | None:
    if not auth:
        return None

    scheme, _, token = auth.partition(" ")

    if scheme.lower() != "bearer":
        return None

    token = token.strip()
    return token or None
