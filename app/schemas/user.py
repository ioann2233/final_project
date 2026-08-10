from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=80, examples=["ivan"])
    password: str = Field(..., min_length=4, examples=["secret123"])
    role: str = Field(default="user", examples=["user"])
    initial_balance: float = Field(default=0.0, ge=0, examples=[100.0])


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, examples=["ivan"])
    password: str = Field(..., examples=["secret123"])


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    balance: float
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
