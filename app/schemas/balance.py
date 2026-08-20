from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BalanceResponse(BaseModel):
    user_id: int
    balance: float


class TopUpRequest(BaseModel):
    amount: float = Field(..., gt=0, examples=[100.0])
    user_id: Optional[int] = Field(default=None, examples=[1])


class TransactionInfo(BaseModel):
    id: int
    user_id: int
    type: str
    amount: float
    task_id: Optional[int] = None
    created_at: datetime


class TopUpResponse(BaseModel):
    transaction: TransactionInfo
    balance: float


class TransactionHistoryResponse(BaseModel):
    user_id: Optional[int] = None
    transactions: list[TransactionInfo]
