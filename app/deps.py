from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt_handler import TokenError, verify_access_token
from service.testing.user import get_user_by_username
from ui.context import get_flask_app, run_with_context

bearer_scheme = HTTPBearer(auto_error=False)


def flask_context():
    with get_flask_app().app_context():
        yield


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    try:
        payload = verify_access_token(creds.credentials)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    username = payload.get("user")
    user = run_with_context(get_user_by_username, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )
    return user


def require_admin(user=Depends(get_current_user)):
    if getattr(user, "role", None) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для администратора",
        )
    return user
