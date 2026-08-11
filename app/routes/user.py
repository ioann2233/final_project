import logging
from typing import List

from fastapi import APIRouter, HTTPException, status
from schemas.user import UserCreate, UserLogin, UserResponse
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


@user_route.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация",
    description="Создание нового пользователя",
)
def signup(data: UserCreate) -> UserResponse:
    def _handler():
        user = create_user(
            username=data.username.strip(),
            password=data.password,
            role=data.role,
            initial_balance=data.initial_balance,
        )
        logger.info("New user registered: %s", user.username)
        return _to_user_response(user)

    try:
        return run_with_context(_handler)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@user_route.post(
    "/signin",
    response_model=UserResponse,
    summary="Авторизация",
    description="Вход по логину и паролю",
)
def signin(data: UserLogin) -> UserResponse:
    def _handler():
        user = authenticate_user(data.username, data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный логин или пароль",
            )
        return _to_user_response(user)

    return run_with_context(_handler)


@user_route.get(
    "/",
    response_model=List[UserResponse],
    summary="Список пользователей",
)
def list_users() -> List[UserResponse]:
    def _handler():
        return [_to_user_response(user) for user in get_all_users()]

    return run_with_context(_handler)


@user_route.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Пользователь по ID",
)
def get_user(user_id: int) -> UserResponse:
    def _handler():
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь id={user_id} не найден",
            )
        return _to_user_response(user)

    return run_with_context(_handler)
