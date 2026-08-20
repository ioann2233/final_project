from datetime import datetime
from typing import List, Tuple

from extensions import db
from models.base import TaskStatus
from models.ml_task import MLTask
from models.prediction import PredictionResult
from models.transaction import Transaction
from service.testing.ml_model import get_ml_model_by_id
from service.testing.user import get_user_by_id


def create_camera_detection_log(
    user_id: int,
    model_id: int,
    mode: str,
    detections: List[dict],
    image_path: str,
) -> Tuple[MLTask, float, float]:
    user = get_user_by_id(user_id)
    model = get_ml_model_by_id(model_id)
    if not user:
        raise ValueError("Пользователь не найден")
    if not model or not model.is_active:
        raise ValueError("Модель не найдена или недоступна")

    price = float(model.price)
    if user.get_balance() < price:
        raise ValueError(
            f"Недостаточно средств на балансе: нужно {price:.2f} ₽, "
            f"доступно {user.get_balance():.2f} ₽"
        )

    now = datetime.utcnow()
    source_label = "camera/live" if mode == "live" else "camera/snapshot"
    task = MLTask(
        user_id=user.id,
        model_id=model.id,
        image_path=image_path or f"{source_label}/{now.isoformat()}",
        status=TaskStatus.COMPLETED.value,
        completed_at=now,
    )
    db.session.add(task)
    db.session.flush()
    db.session.add(
        PredictionResult(
            task_id=task.id,
            predictions=detections,
        )
    )

    charged = 0.0
    if price > 0:
        if not user.subtract_balance(price):
            db.session.rollback()
            raise ValueError(
                f"Недостаточно средств на балансе: нужно {price:.2f} ₽, "
                f"доступно {user.get_balance():.2f} ₽"
            )
        db.session.add(
            Transaction(
                user_id=user.id,
                amount=price,
                transaction_type="purchase",
                task_id=task.id,
            )
        )
        charged = price

    db.session.commit()
    db.session.refresh(task)
    return task, charged, user.get_balance()
