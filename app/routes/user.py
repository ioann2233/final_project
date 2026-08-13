import logging
from typing import List

from auth.jwt_handler import create_access_token
from deps import get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.user import SignInResponse, UserCreate, UserLogin, UserResponse
from service.auth import authenticate_user
from service.testing.user import create_user, get_all_users, get_user_by_id
from ui.context import run_with_context

logger = logging.getLogger(__name__)

user_route = APIRouter()


def _to_user_response(user) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        balance=user.get_balance(),
        created_at=user.created_at,
    )


def _to_signin(user) -> SignInResponse:
    token = create_access_token(user.username)
    base = _to_user_response(user)
    return SignInResponse(**base.model_dump(), access_token=token, token_type="bearer")


@user_route.post(
    "/signup",
    response_model=SignInResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация",
)
def signup(data: UserCreate) -> SignInResponse:
    def _handler():
        user = create_user(
            username=data.username.strip(),
            password=data.password,
            role="user" if data.role == "admin" else data.role,
            initial_balance=data.initial_balance,
        )
        logger.info("New user registered: %s", user.username)
        return _to_signin(user)

    try:
        return run_with_context(_handler)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@user_route.post(
    "/signin",
    response_model=SignInResponse,
    summary="Авторизация (JWT)",
)
def signin(data: UserLogin) -> SignInResponse:
    def _handler():
        user = authenticate_user(data.username, data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный логин или пароль",
            )
        return _to_signin(user)

    return run_with_context(_handler)


@user_route.get("/me", response_model=UserResponse, summary="Текущий пользователь")
def me(user=Depends(get_current_user)) -> UserResponse:
    fresh = run_with_context(get_user_by_id, user.id)
    return _to_user_response(fresh)


@user_route.get(
    "/",
    response_model=List[UserResponse],
    summary="Список пользователей (админ)",
)
def list_users(_admin=Depends(require_admin)) -> List[UserResponse]:
    def _handler():
        return [_to_user_response(item) for item in get_all_users()]

    return run_with_context(_handler)


@user_route.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Пользователь по ID",
)
def get_user(user_id: int, current=Depends(get_current_user)) -> UserResponse:
    if current.role != "admin" and current.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")

    def _handler():
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь id={user_id} не найден",
            )
        return _to_user_response(user)

    return run_with_context(_handler)
