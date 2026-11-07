import argon2

ph = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=1024 * 30,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=argon2.Type.ID
)

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except (argon2.exceptions.VerificationError, argon2.exceptions.InvalidHashError):
        return False
