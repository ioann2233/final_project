import logging
from typing import Dict, List, Optional, Tuple

from extensions import db
from models.base import TaskStatus
from models.ml_task import MLTask
from models.transaction import Transaction
from service.rm import send_ml_task
from service.testing.ml_model import get_ml_model_by_id
from service.testing.user import get_user_by_id
from sqlalchemy.orm import joinedload
from worker.predictor import validate_input_items

logger = logging.getLogger(__name__)


def create_prediction_task(
    user_id: int,
    model_id: int,
    image_path: str = "pending",
    enqueue: bool = True,
    charge_now: bool = False,
) -> MLTask:
    user = get_user_by_id(user_id)
    model = get_ml_model_by_id(model_id)

    if not user:
        raise ValueError("Пользователь не найден")
    if not model or not model.is_active:
        raise ValueError("Модель не найдена или недоступна")
    if user.get_balance() <= 0:
        raise ValueError("Недостаточно средств на балансе")
    if user.get_balance() < model.price:
        raise ValueError(
            f"Недостаточно средств на балансе: нужно {model.price:.2f} ₽, "
            f"доступно {user.get_balance():.2f} ₽"
        )

    if charge_now:
        user.subtract_balance(model.price)

    task = MLTask(
        user_id=user.id,
        model_id=model.id,
        image_path=image_path,
        status=TaskStatus.CREATED.value,
    )
    db.session.add(task)
    db.session.flush()

    if charge_now:
        db.session.add(
            Transaction(
                user_id=user.id,
                amount=model.price,
                transaction_type="purchase",
                task_id=task.id,
            )
        )

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


def create_prediction_batch(
    user_id: int,
    model_id: int,
    items: List[str],
) -> Tuple[List[MLTask], List[dict], float]:
    accepted, rejected = validate_input_items(items)
    user = get_user_by_id(user_id)
    model = get_ml_model_by_id(model_id)

    if not user:
        raise ValueError("Пользователь не найден")
    if not model or not model.is_active:
        raise ValueError("Модель не найдена или недоступна")
    if user.get_balance() <= 0:
        raise ValueError("Недостаточно средств на балансе")

    if accepted:
        total = model.price * len(accepted)
        if user.get_balance() < total:
            raise ValueError(
                f"Недостаточно средств на балансе: нужно {total:.2f} ₽ "
                f"на {len(accepted)} корректных запрос(ов), "
                f"доступно {user.get_balance():.2f} ₽"
            )

    tasks: List[MLTask] = []
    for path in accepted:
        tasks.append(
            create_prediction_task(
                user_id=user_id,
                model_id=model_id,
                image_path=path,
                enqueue=True,
                charge_now=False,
            )
        )
    return tasks, rejected, user.get_balance()


def purchase_model(user_id: int, model_id: int) -> MLTask:
    return create_prediction_task(
        user_id, model_id, image_path="pending", enqueue=False, charge_now=True
    )


def get_task_by_id(task_id: int) -> Optional[MLTask]:
    return (
        db.session.query(MLTask)
        .options(
            joinedload(MLTask.model),
            joinedload(MLTask.result),
            joinedload(MLTask.transactions),
        )
        .filter_by(id=task_id)
        .first()
    )


def get_user_tasks(user_id: int) -> List[MLTask]:
    return (
        db.session.query(MLTask)
        .options(
            joinedload(MLTask.model),
            joinedload(MLTask.result),
            joinedload(MLTask.transactions),
        )
        .filter_by(user_id=user_id)
        .order_by(MLTask.created_at.desc(), MLTask.id.desc())
        .all()
    )


def charged_amount(task: MLTask) -> float:
    purchase = sum(
        float(tx.amount)
        for tx in (task.transactions or [])
        if tx.transaction_type == "purchase"
    )
    refund = sum(
        float(tx.amount)
        for tx in (task.transactions or [])
        if tx.transaction_type == "refund"
    )
    return max(purchase - refund, 0.0)


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
