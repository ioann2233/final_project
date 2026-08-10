from deps import flask_context
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.prediction import (
    PredictionCreate,
    PredictionHistoryResponse,
    PredictionItem,
    PredictionResponse,
)
from service.testing.ml_task import create_prediction_task, get_user_tasks
from service.testing.user import get_user_by_id

prediction_route = APIRouter()


def _to_prediction_item(task) -> PredictionItem:
    return PredictionItem(
        id=task.id,
        user_id=task.user_id,
        model_id=task.model_id,
        model_name=task.model.name if task.model else None,
        image_path=task.image_path,
        status=task.status,
        completed_at=task.completed_at,
        created_at=task.created_at,
    )


@prediction_route.post(
    "/",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Запрос на предсказание",
    description="Создание задачи ML-предсказания с оплатой модели",
)
async def create_prediction(
    data: PredictionCreate,
    _: None = Depends(flask_context),
) -> PredictionResponse:
    try:
        task = create_prediction_task(data.user_id, data.model_id, data.image_path)
        user = get_user_by_id(data.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return PredictionResponse(
        id=task.id,
        user_id=task.user_id,
        model_id=task.model_id,
        image_path=task.image_path,
        status=task.status,
        completed_at=task.completed_at,
        created_at=task.created_at,
        balance=user.get_balance() if user else 0.0,
    )


@prediction_route.get(
    "/history/{user_id}",
    response_model=PredictionHistoryResponse,
    summary="История запросов на предсказания",
)
async def prediction_history(
    user_id: int,
    _: None = Depends(flask_context),
) -> PredictionHistoryResponse:
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь id={user_id} не найден",
        )

    tasks = get_user_tasks(user_id)
    return PredictionHistoryResponse(
        user_id=user_id,
        predictions=[_to_prediction_item(task) for task in tasks],
    )
