from typing import List

from fastapi import APIRouter
from schemas.model import MLModelResponse
from service.testing.ml_model import get_active_models
from ui.context import run_with_context

models_route = APIRouter()


@models_route.get(
    "/",
    response_model=List[MLModelResponse],
    summary="Список ML-моделей",
)
def list_models() -> List[MLModelResponse]:
    def _handler():
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

    return run_with_context(_handler)
