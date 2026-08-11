from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class PredictionCreate(BaseModel):
    user_id: int = Field(..., examples=[1])
    model_id: int = Field(..., examples=[1])
    image_path: str = Field(
        default="uploads/demo.jpg",
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
    message: Optional[str] = None


class PredictionItem(BaseModel):
    id: int
    user_id: int
    model_id: int
    model_name: Optional[str] = None
    image_path: str
    status: str
    completed_at: Optional[datetime] = None
    created_at: datetime
    predictions: Optional[List[Any]] = None


class PredictionDetailResponse(BaseModel):
    id: int
    user_id: int
    model_id: int
    model_name: Optional[str] = None
    image_path: str
    status: str
    completed_at: Optional[datetime] = None
    created_at: datetime
    predictions: List[Any] = Field(default_factory=list)
    predictions_count: int = 0


class PredictionHistoryResponse(BaseModel):
    user_id: int
    predictions: List[PredictionItem]
