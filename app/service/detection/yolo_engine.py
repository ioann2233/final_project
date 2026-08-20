from __future__ import annotations

from typing import Dict, List

import numpy as np

PERSON_CLASS_ID = 0
VEHICLE_CLASS_IDS = {
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

_models: Dict[str, object] = {}


def get_yolo_model(model_path: str):
    if model_path not in _models:
        from ultralytics import YOLO

        _models[model_path] = YOLO(model_path)
    return _models[model_path]


def detect_with_yolo(
    frame: np.ndarray,
    model_path: str,
    conf: float = 0.35,
    imgsz: int = 640,
) -> List[dict]:
    model = get_yolo_model(model_path)
    results = model.predict(frame, imgsz=imgsz, conf=conf, verbose=False)
    if not results:
        return []

    height, width = frame.shape[:2]
    detections: List[dict] = []
    for box in results[0].boxes:
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width - 1, x2), min(height - 1, y2)
        if x2 <= x1 or y2 <= y1:
            continue

        if class_id == PERSON_CLASS_ID:
            entity_type = "person"
            label = "person"
        elif class_id in VEHICLE_CLASS_IDS:
            entity_type = "vehicle"
            label = VEHICLE_CLASS_IDS[class_id]
        else:
            continue

        detections.append(
            {
                "entity_type": entity_type,
                "label": label,
                "confidence": confidence,
                "bbox": [x1, y1, x2, y2],
            }
        )
    return detections
