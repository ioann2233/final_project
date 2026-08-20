import re
import time
from pathlib import Path
from typing import List

IMAGE_PATH_PATTERN = re.compile(r"^[\w\-./\\]+$", re.UNICODE)


class ValidationError(ValueError):
    pass


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
    path = validate_image_path(image_path)
    base = Path(__file__).resolve().parent.parent
    full_path = base / path
    if not full_path.exists():
        raise ValidationError(f"файл не найден: {path}")

    import cv2

    frame = cv2.imread(str(full_path))
    if frame is None:
        raise ValidationError(f"не удалось прочитать изображение: {path}")

    from service.detection.detector import get_camera_detector

    detector = get_camera_detector(model_path, live_mode=False)
    detections = detector.detect_objects(frame)

    predictions: List[dict] = []
    for index, item in enumerate(detections, start=1):
        predictions.append(
            {
                "class": item["label"],
                "confidence": round(float(item["confidence"]), 3),
                "bbox": item["bbox"],
                "detection_id": index,
            }
        )

    if "access" in model_name.lower() or "контроль" in model_name.lower():
        time.sleep(0.5)

    return predictions
