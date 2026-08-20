from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field


EntityType = Literal["person", "vehicle"]


class KnownEntityResponse(BaseModel):
    id: int
    user_id: int
    entity_type: EntityType
    name: str
    image_path: str
    created_at: datetime


class KnownEntityListResponse(BaseModel):
    entities: List[KnownEntityResponse]


class KnownEntityDetectionItem(BaseModel):
    id: int
    entity_type: EntityType
    name: str
    descriptor: List[float]


class KnownEntityDetectionResponse(BaseModel):
    entities: List[KnownEntityDetectionItem]


class KnownEntityCreateResponse(BaseModel):
    entity: KnownEntityResponse
    message: str = Field(default="Сущность добавлена в список «своих»")
