import time
from datetime import datetime

from jose import JWTError, jwt

from config import Config

SECRET_KEY = Config.SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRE_SECONDS = 8 * 3600


class TokenError(Exception):
    """Ошибка JWT: нет токена, истёк или подпись неверна."""


def create_access_token(user: str) -> str:
    payload = {
        "user": user,
        "expires": time.time() + TOKEN_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> dict:
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        expire = data.get("expires")
        if expire is None:
            raise TokenError("No access token supplied")
        if datetime.utcnow() > datetime.utcfromtimestamp(expire):
            raise TokenError("Token expired!")
        return data
    except JWTError as exc:
        raise TokenError("Invalid token") from exc
