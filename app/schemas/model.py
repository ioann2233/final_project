from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MLModelResponse(BaseModel):
    id: int
    name: str
    description: str
    price: float
    model_path: str
    is_active: bool
    created_at: Optional[datetime] = None
