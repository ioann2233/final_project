from typing import Any, List

from fastapi import APIRouter, HTTPException, status
from schemas.prediction import (
    PredictionCreate,
    PredictionDetailResponse,
    PredictionHistoryResponse,
    PredictionItem,
    PredictionResponse,
)
from service.testing.ml_task import (
    create_prediction_task,
    get_task_by_id,
    get_user_tasks,
)
from service.testing.user import get_user_by_id
from ui.context import run_with_context

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
        predictions=(task.result.show() if task.result else None),
    )


@prediction_route.post(
    "/",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Запрос на предсказание",
    description=(
        "Создаёт ML-задачу, списывает оплату и публикует сообщение в RabbitMQ. "
        "Воркеры асинхронно выполняют предикт и сохраняют результат."
    ),
)
def create_prediction(data: PredictionCreate) -> PredictionResponse:
    def _handler():
        task = create_prediction_task(data.user_id, data.model_id, data.image_path)
        user = get_user_by_id(data.user_id)
        return PredictionResponse(
            id=task.id,
            user_id=task.user_id,
            model_id=task.model_id,
            image_path=task.image_path,
            status=task.status,
            completed_at=task.completed_at,
            created_at=task.created_at,
            balance=user.get_balance() if user else 0.0,
            message="Задача отправлена в очередь ML-воркеров",
        )

    try:
        return run_with_context(_handler)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@prediction_route.get(
    "/history/{user_id}",
    response_model=PredictionHistoryResponse,
    summary="История запросов на предсказания",
)
def prediction_history(user_id: int) -> PredictionHistoryResponse:
    def _handler():
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

    return run_with_context(_handler)


@prediction_route.get(
    "/{task_id}",
    response_model=PredictionDetailResponse,
    summary="Результат предсказания по task_id",
)
def get_prediction(task_id: int) -> PredictionDetailResponse:
    def _handler():
        task = get_task_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Задача id={task_id} не найдена",
            )
        predictions: List[Any] = task.result.show() if task.result else []
        return PredictionDetailResponse(
            id=task.id,
            user_id=task.user_id,
            model_id=task.model_id,
            model_name=task.model.name if task.model else None,
            image_path=task.image_path,
            status=task.status,
            completed_at=task.completed_at,
            created_at=task.created_at,
            predictions=predictions,
            predictions_count=len(predictions),
        )

    return run_with_context(_handler)
