from typing import List

from deps import flask_context
from fastapi import APIRouter, Depends
from schemas.model import MLModelResponse
from service.testing.ml_model import get_active_models

models_route = APIRouter()


@models_route.get(
    "/",
    response_model=List[MLModelResponse],
    summary="Список ML-моделей",
)
async def list_models(_: None = Depends(flask_context)) -> List[MLModelResponse]:
    models = get_active_models()
    return [
        MLModelResponse(
            id=model.id,
            name=model.name,
            description=model.description,
            price=model.price,
            model_path=model.model_path,
            is_active=model.is_active,
            created_at=model.created_at,
        )
        for model in models
    ]
