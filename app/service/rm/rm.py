import json
import logging
import os
from typing import Any, Dict

import pika

logger = logging.getLogger(__name__)

QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "ml_task_queue")


def _connection_params() -> pika.ConnectionParameters:
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


def send_ml_task(payload: Dict[str, Any]) -> None:
    """Публикация ML-задачи в очередь (один издатель → несколько слушателей)."""
    body = json.dumps(payload, ensure_ascii=False)
    connection = pika.BlockingConnection(_connection_params())
    try:
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=body.encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
        logger.info("ML task published to %s: %s", QUEUE_NAME, payload)
    finally:
        connection.close()
