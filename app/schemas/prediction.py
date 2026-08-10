from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PredictionCreate(BaseModel):
    user_id: int = Field(..., examples=[1])
    model_id: int = Field(..., examples=[1])
    image_path: str = Field(
        default="pending",
        min_length=1,
        max_length=500,
        examples=["uploads/photo.jpg"],
        description="Путь к изображению или идентификатор входных данных",
    )


class PredictionResponse(BaseModel):
    id: int
    user_id: int
    model_id: int
    image_path: str
    status: str
    completed_at: Optional[datetime] = None
    created_at: datetime
    balance: float


class PredictionItem(BaseModel):
    id: int
    user_id: int
    model_id: int
    model_name: Optional[str] = None
    image_path: str
    status: str
    completed_at: Optional[datetime] = None
    created_at: datetime


class PredictionHistoryResponse(BaseModel):
    user_id: int
    predictions: List[PredictionItem]
