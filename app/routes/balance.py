from deps import flask_context
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.balance import BalanceResponse, TopUpRequest, TopUpResponse, TransactionInfo
from service.testing.user import get_user_by_id
from service.testing.wallet import get_balance, top_up_balance

balance_route = APIRouter()


@balance_route.get(
    "/{user_id}",
    response_model=BalanceResponse,
    summary="Баланс пользователя",
)
async def get_user_balance(
    user_id: int,
    _: None = Depends(flask_context),
) -> BalanceResponse:
    try:
        value = get_balance(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BalanceResponse(user_id=user_id, balance=value)


@balance_route.post(
    "/top-up",
    response_model=TopUpResponse,
    summary="Пополнение баланса",
)
async def top_up(
    data: TopUpRequest,
    _: None = Depends(flask_context),
) -> TopUpResponse:
    try:
        tx = top_up_balance(data.user_id, data.amount)
        user = get_user_by_id(data.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    tx_info = tx.get_info()
    return TopUpResponse(
        transaction=TransactionInfo(
            id=tx_info["id"],
            user_id=tx_info["user_id"],
            type=tx_info["type"],
            amount=tx_info["amount"],
            task_id=tx_info.get("task_id"),
            created_at=tx_info["created_at"],
        ),
        balance=user.get_balance() if user else 0.0,
    )
