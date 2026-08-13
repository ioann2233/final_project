from typing import Optional, Tuple

from auth.jwt_handler import TokenError, create_access_token, verify_access_token
from service.auth import authenticate_user
from service.testing.user import get_user_by_username
from ui.context import run_with_context

COOKIE_NAME = "access_token"


class AuthError(Exception):
    """Ошибка входа: нет пользователя или неверный пароль."""


def login_for_access_token(username: str, password: str) -> Tuple[str, object]:
    """Проверка пароля и выдача JWT — аналог /auth/token из lesson6."""
    user = run_with_context(authenticate_user, username, password)
    if user is None:
        raise AuthError("Неверный логин или пароль")
    token = create_access_token(user.username)
    return f"Bearer {token}", user


def authenticate(token: Optional[str]):
    """Проверка JWT из «cookie» (session_state). Как authenticate_cookie в lesson6."""
    if not token:
        return None
    try:
        raw = token.removeprefix("Bearer ")
        data = verify_access_token(raw)
        return run_with_context(get_user_by_username, data.get("user"))
    except TokenError:
        return None
