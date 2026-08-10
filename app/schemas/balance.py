from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BalanceResponse(BaseModel):
    user_id: int
    balance: float


class TopUpRequest(BaseModel):
    user_id: int = Field(..., examples=[1])
    amount: float = Field(..., gt=0, examples=[100.0])


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
