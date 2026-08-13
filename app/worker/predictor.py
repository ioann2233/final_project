import hashlib
import random
import re
import time
from typing import List

IMAGE_PATH_PATTERN = re.compile(r"^[\w\-./\\]+$", re.UNICODE)


class ValidationError(ValueError):
    """Некорректные входные данные ML-задачи."""


def validate_image_path(image_path: str) -> str:
    if not image_path or not isinstance(image_path, str):
        raise ValidationError("путь обязателен")

    path = image_path.strip()
    if not path:
        raise ValidationError("пустая строка")
    if len(path) > 500:
        raise ValidationError("путь слишком длинный (макс. 500 символов)")
    if path in {"pending", "none", "null"}:
        raise ValidationError("путь не задан: укажите файл или uploads/photo.jpg")
    if not IMAGE_PATH_PATTERN.match(path):
        raise ValidationError("недопустимые символы в пути")
    return path


def validate_input_items(items: List[str]) -> tuple[List[str], List[dict]]:
    """Разделяет вход на принятые и отклонённые записи (частичная валидация)."""
    accepted: List[str] = []
    rejected: List[dict] = []
    for index, raw in enumerate(items):
        value = raw if isinstance(raw, str) else str(raw)
        try:
            accepted.append(validate_image_path(value))
        except ValidationError as exc:
            rejected.append({"index": index, "value": value, "error": str(exc)})
    return accepted, rejected


def run_prediction(model_name: str, model_path: str, image_path: str) -> List[dict]:
    """
    Эмуляция инференса YOLO-подобной модели.
    Детерминированный результат по model_path + image_path (удобно для ручных тестов).
    """
    path = validate_image_path(image_path)
    time.sleep(1.5)

    seed = int(
        hashlib.md5(f"{model_path}:{path}".encode("utf-8")).hexdigest()[:8],
        16,
    )
    rng = random.Random(seed)

    if "access" in model_name.lower() or "контроль" in model_name.lower():
        classes = ["own", "stranger"]
    else:
        classes = ["person", "car", "dog", "cat", "bicycle"]

    count = rng.randint(1, 4)
    predictions: List[dict] = []
    for i in range(count):
        cls = classes[rng.randint(0, len(classes) - 1)]
        x1, y1 = rng.randint(0, 400), rng.randint(0, 400)
        w, h = rng.randint(40, 200), rng.randint(40, 200)
        predictions.append(
            {
                "class": cls,
                "confidence": round(rng.uniform(0.55, 0.99), 3),
                "bbox": [x1, y1, x1 + w, y1 + h],
                "detection_id": i + 1,
            }
        )
    return predictions
