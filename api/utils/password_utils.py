from passlib.context import CryptContext

_password_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _password_ctx.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _password_ctx.verify(plain_password, hashed_password)
    except Exception:
        return False 