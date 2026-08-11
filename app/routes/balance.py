from fastapi import APIRouter, HTTPException, status
from schemas.balance import (
    BalanceResponse,
    TopUpRequest,
    TopUpResponse,
    TransactionHistoryResponse,
    TransactionInfo,
)
from service.testing.transaction import get_user_transactions
from service.testing.user import get_user_by_id
from service.testing.wallet import get_balance, top_up_balance
from ui.context import run_with_context

balance_route = APIRouter()


def _to_transaction_info(tx) -> TransactionInfo:
    tx_info = tx.get_info()
    return TransactionInfo(
        id=tx_info["id"],
        user_id=tx_info["user_id"],
        type=tx_info["type"],
        amount=tx_info["amount"],
        task_id=tx_info.get("task_id"),
        created_at=tx_info["created_at"],
    )


@balance_route.get(
    "/transactions/{user_id}",
    response_model=TransactionHistoryResponse,
    summary="История транзакций пользователя",
)
def get_transaction_history(user_id: int) -> TransactionHistoryResponse:
    def _handler():
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь id={user_id} не найден",
            )
        transactions = get_user_transactions(user_id)
        return TransactionHistoryResponse(
            user_id=user_id,
            transactions=[_to_transaction_info(tx) for tx in transactions],
        )

    return run_with_context(_handler)


@balance_route.get(
    "/{user_id}",
    response_model=BalanceResponse,
    summary="Баланс пользователя",
)
def get_user_balance(user_id: int) -> BalanceResponse:
    def _handler():
        try:
            value = get_balance(user_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        return BalanceResponse(user_id=user_id, balance=value)

    return run_with_context(_handler)


@balance_route.post(
    "/top-up",
    response_model=TopUpResponse,
    summary="Пополнение баланса",
)
def top_up(data: TopUpRequest) -> TopUpResponse:
    def _handler():
        tx = top_up_balance(data.user_id, data.amount)
        user = get_user_by_id(data.user_id)
        return TopUpResponse(
            transaction=_to_transaction_info(tx),
            balance=user.get_balance() if user else 0.0,
        )

    try:
        return run_with_context(_handler)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
