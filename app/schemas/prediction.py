from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class PredictionCreate(BaseModel):
    model_id: int = Field(..., examples=[1])
    image_path: Optional[str] = Field(
        default=None,
        max_length=500,
        examples=["uploads/photo.jpg"],
    )
    items: Optional[List[str]] = Field(
        default=None,
        examples=[["uploads/a.jpg", "uploads/b.jpg"]],
    )


class RejectedItem(BaseModel):
    index: int
    value: str
    error: str


class PredictionResponse(BaseModel):
    id: int
    user_id: int
    model_id: int
    image_path: str
    status: str
    completed_at: Optional[datetime] = None
    created_at: datetime
    balance: Optional[float] = None
    message: Optional[str] = None


class PredictionBatchResponse(BaseModel):
    accepted: List[PredictionResponse]
    rejected: List[RejectedItem]
    balance: float
    price_per_item: float
    message: str


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
    charged: float = 0.0


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
    charged: float = 0.0


class PredictionHistoryResponse(BaseModel):
    user_id: int
    predictions: List[PredictionItem]


class UploadResponse(BaseModel):
    path: str
    filename: str


class CameraDetectionResponse(BaseModel):
    id: int
    model_id: int
    model_name: Optional[str] = None
    image_path: str
    mode: str
    detections_count: int
    predictions: List[Any]
    charged: float = 0.0
    balance: Optional[float] = None
    price: float = 0.0
    message: str = "Детекция сохранена в историю, кредиты списаны"
