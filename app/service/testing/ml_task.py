import logging
from typing import Dict, List, Optional

from extensions import db
from models.base import TaskStatus
from models.ml_task import MLTask
from models.transaction import Transaction
from service.rm import send_ml_task
from service.testing.ml_model import get_ml_model_by_id
from service.testing.user import get_user_by_id
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


def create_prediction_task(
    user_id: int,
    model_id: int,
    image_path: str = "pending",
    enqueue: bool = True,
) -> MLTask:
    user = get_user_by_id(user_id)
    model = get_ml_model_by_id(model_id)

    if not user:
        raise ValueError("Пользователь не найден")
    if not model or not model.is_active:
        raise ValueError("Модель не найдена или недоступна")
    if user.get_balance() < model.price:
        raise ValueError("Недостаточно средств на балансе")

    user.subtract_balance(model.price)

    task = MLTask(
        user_id=user.id,
        model_id=model.id,
        image_path=image_path,
        status=TaskStatus.CREATED.value,
    )
    db.session.add(task)
    db.session.flush()

    transaction = Transaction(
        user_id=user.id,
        amount=model.price,
        transaction_type="purchase",
        task_id=task.id,
    )
    db.session.add(transaction)
    db.session.commit()
    db.session.refresh(task)

    if enqueue:
        try:
            send_ml_task({"task_id": task.id})
        except Exception as exc:
            logger.error("Не удалось отправить task_id=%s в RabbitMQ: %s", task.id, exc)
            task.status = TaskStatus.FAILED.value
            db.session.commit()
            raise ValueError(
                f"Задача создана (id={task.id}), но очередь недоступна: {exc}"
            ) from exc

    return task


def purchase_model(user_id: int, model_id: int) -> MLTask:
    # UI-покупка без инференса: в очередь не ставим
    return create_prediction_task(
        user_id, model_id, image_path="pending", enqueue=False
    )


def get_task_by_id(task_id: int) -> Optional[MLTask]:
    return (
        db.session.query(MLTask)
        .options(joinedload(MLTask.model), joinedload(MLTask.result))
        .filter_by(id=task_id)
        .first()
    )


def get_user_tasks(user_id: int) -> List[MLTask]:
    return (
        db.session.query(MLTask)
        .options(joinedload(MLTask.model), joinedload(MLTask.result))
        .filter_by(user_id=user_id)
        .order_by(MLTask.created_at.desc(), MLTask.id.desc())
        .all()
    )


def get_user_tasks_rows(user_id: int) -> List[Dict[str, str]]:
    tasks = get_user_tasks(user_id)
    return [
        {
            "Дата": task.created_at.strftime("%d.%m.%Y %H:%M"),
            "Модель": task.model.name if task.model else "—",
            "Статус": task.status,
        }
        for task in tasks
    ]
