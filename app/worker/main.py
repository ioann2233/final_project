"""ML worker: получает задачи из RabbitMQ, валидирует, предиктит, пишет результат."""

from __future__ import annotations

import json
import logging
import os
import socket
import time
from datetime import datetime
from typing import Any, Dict, Optional

import pika
from sqlalchemy.orm import joinedload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ml_worker")

QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "ml_task_queue")
WORKER_ID = os.getenv("HOSTNAME") or socket.gethostname()


def _rabbit_params() -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST", "localhost"),
        port=int(os.getenv("RABBITMQ_PORT", "5672")),
        virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
        credentials=pika.PlainCredentials(
            username=os.getenv("RABBITMQ_USER", "rmuser"),
            password=os.getenv("RABBITMQ_PASS", "rmpassword"),
        ),
        heartbeat=30,
        blocked_connection_timeout=2,
    )


def _get_flask_app():
    from main import create_app

    return create_app()


def _parse_message(body: bytes) -> Dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Невалидный JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Сообщение должно быть JSON-объектом")

    task_id = payload.get("task_id")
    if task_id is None:
        raise ValueError("В сообщении нет task_id")
    try:
        task_id = int(task_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("task_id должен быть целым числом") from exc
    if task_id <= 0:
        raise ValueError("task_id должен быть положительным")

    return {"task_id": task_id}


def _refund_task_payment(task) -> float:
    """Возвращает списанные за задачу средства. Работа не выполнена."""
    from models.transaction import Transaction

    if not task.user or not task.user.wallet:
        return 0.0

    already_refunded = any(
        tx.transaction_type == "refund" for tx in task.transactions
    )
    if already_refunded:
        return 0.0

    purchase = next(
        (tx for tx in task.transactions if tx.transaction_type == "purchase"),
        None,
    )
    if purchase and purchase.amount > 0:
        amount = float(purchase.amount)
    elif task.model and task.model.price > 0:
        amount = float(task.model.price)
    else:
        return 0.0

    from extensions import db

    task.user.add_balance(amount)
    db.session.add(
        Transaction(
            user_id=task.user_id,
            amount=amount,
            transaction_type="refund",
            task_id=task.id,
        )
    )
    return amount


def process_task(task_id: int) -> None:
    from extensions import db
    from models.base import TaskStatus
    from models.ml_task import MLTask
    from models.prediction import PredictionResult
    from worker.predictor import ValidationError, run_prediction

    task: Optional[MLTask] = (
        db.session.query(MLTask)
        .options(joinedload(MLTask.model), joinedload(MLTask.result))
        .filter_by(id=task_id)
        .first()
    )
    if not task:
        raise ValueError(f"Задача id={task_id} не найдена в БД")

    if task.status == TaskStatus.COMPLETED.value and task.result is not None:
        logger.info("[%s] task_id=%s уже completed — пропуск", WORKER_ID, task_id)
        return

    if not task.model or not task.model.is_active:
        raise ValidationError("Модель недоступна или неактивна")

    task.status = TaskStatus.RUNNING.value
    db.session.commit()
    logger.info(
        "[%s] task_id=%s RUNNING model=%s image=%s",
        WORKER_ID,
        task_id,
        task.model.name,
        task.image_path,
    )

    try:
        predictions = run_prediction(
            model_name=task.model.name,
            model_path=task.model.model_path,
            image_path=task.image_path,
        )

        if task.result is None:
            result = PredictionResult(task_id=task.id, predictions=predictions)
            db.session.add(result)
        else:
            task.result.predictions = predictions

        task.status = TaskStatus.COMPLETED.value
        task.completed_at = datetime.utcnow()
        db.session.commit()
        logger.info(
            "[%s] task_id=%s COMPLETED detections=%s",
            WORKER_ID,
            task_id,
            len(predictions),
        )
    except Exception:
        db.session.rollback()
        task = (
            db.session.query(MLTask)
            .options(
                joinedload(MLTask.model),
                joinedload(MLTask.user),
                joinedload(MLTask.transactions),
            )
            .filter_by(id=task_id)
            .first()
        )
        if task:
            task.status = TaskStatus.FAILED.value
            task.completed_at = datetime.utcnow()
            refunded = _refund_task_payment(task)
            db.session.commit()
            logger.warning(
                "[%s] task_id=%s FAILED, refunded=%.2f",
                WORKER_ID,
                task_id,
                refunded,
            )
        raise


def on_message(ch, method, _properties, body: bytes) -> None:
    app = _get_flask_app()
    try:
        payload = _parse_message(body)
        task_id = payload["task_id"]
        logger.info("[%s] Received task_id=%s", WORKER_ID, task_id)
        with app.app_context():
            process_task(task_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        logger.exception("[%s] Ошибка обработки: %s", WORKER_ID, exc)
        # ack после записи FAILED / невалидного сообщения — без бесконечного retry
        ch.basic_ack(delivery_tag=method.delivery_tag)


def connect_with_retry(max_attempts: int = 60, delay_sec: float = 2.0):
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            connection = pika.BlockingConnection(_rabbit_params())
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_qos(prefetch_count=1)
            logger.info(
                "[%s] Connected to RabbitMQ, queue=%s (attempt %s)",
                WORKER_ID,
                QUEUE_NAME,
                attempt,
            )
            return connection, channel
        except Exception as exc:
            last_error = exc
            logger.warning(
                "[%s] RabbitMQ недоступен (attempt %s/%s): %s",
                WORKER_ID,
                attempt,
                max_attempts,
                exc,
            )
            time.sleep(delay_sec)
    raise RuntimeError(f"Не удалось подключиться к RabbitMQ: {last_error}")


def main() -> None:
    logger.info("[%s] ML worker starting...", WORKER_ID)
    connection, channel = connect_with_retry()
    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=on_message,
        auto_ack=False,
    )
    logger.info("[%s] Waiting for ML tasks. Ctrl+C to exit", WORKER_ID)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("[%s] Stopping...", WORKER_ID)
        channel.stop_consuming()
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
