from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from service.detection.draw_utils import draw_text
from service.detection.face_engine import FaceEngine, get_face_engine
from service.detection.yolo_engine import detect_with_yolo

OWN_COLOR = (0, 220, 0)
STRANGER_COLOR = (0, 0, 255)
VEHICLE_MATCH_THRESHOLD = 0.45

_detectors: Dict[str, "YoloCameraDetector"] = {}


class DescriptorExtractor:

    def __init__(self) -> None:
        self._face_engine: Optional[FaceEngine] = None

    @property
    def face_engine(self) -> FaceEngine:
        if self._face_engine is None:
            self._face_engine = get_face_engine()
        return self._face_engine

    @staticmethod
    def compute_vehicle_descriptor(image: np.ndarray) -> List[float]:
        if image is None or image.size == 0:
            raise ValueError("Пустое изображение")
        resized = cv2.resize(image, (64, 64))
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten().astype(float).tolist()

    def extract_person_descriptor(self, image: np.ndarray) -> List[float]:
        embedding = self.face_engine.extract_face_embedding(image)
        if embedding is None:
            raise ValueError(
                "Лицо не найдено на фото. Загрузите снимок с чётко видимым лицом анфас."
            )
        return embedding

    def extract_vehicle_descriptor(self, image: np.ndarray) -> List[float]:
        return self.compute_vehicle_descriptor(image)

    @staticmethod
    def vehicle_similarity(first: List[float], second: List[float]) -> float:
        a = np.array(first, dtype=np.float32).reshape(16, 16)
        b = np.array(second, dtype=np.float32).reshape(16, 16)
        return float(cv2.compareHist(a, b, cv2.HISTCMP_CORREL))

    def match_vehicle(
        self,
        descriptor: List[float],
        known_entities: List[dict],
    ) -> Tuple[bool, Optional[str], float]:
        best_name: Optional[str] = None
        best_score = -1.0
        for entity in known_entities:
            if entity.get("entity_type") != "vehicle":
                continue
            score = self.vehicle_similarity(descriptor, entity["descriptor"])
            if score > best_score:
                best_score = score
                best_name = entity.get("name")
        if best_score >= VEHICLE_MATCH_THRESHOLD and best_name:
            return True, best_name, best_score
        return False, None, best_score

    def classify_detection(
        self,
        frame: np.ndarray,
        item: dict,
        known_entities: List[dict],
    ) -> dict:
        x1, y1, x2, y2 = item["bbox"]
        crop = frame[y1:y2, x1:x2]
        is_own = False
        name: Optional[str] = None
        score = -1.0

        if crop.size == 0:
            status = "stranger"
            title = item["label"]
        elif item["entity_type"] == "person":
            embedding = self.face_engine.extract_face_embedding(crop)
            if embedding is not None:
                is_own, name, score = self.face_engine.match_person(
                    embedding,
                    known_entities,
                )
            status = "own" if is_own else "stranger"
            title = name if is_own and name else item["label"]
        else:
            descriptor = self.extract_vehicle_descriptor(crop)
            is_own, name, score = self.match_vehicle(descriptor, known_entities)
            status = "own" if is_own else "stranger"
            title = name if is_own and name else item["label"]

        return {
            "class": title,
            "entity_type": item["entity_type"],
            "label": item["label"],
            "status": status,
            "name": name,
            "confidence": round(float(item["confidence"]), 3),
            "match_score": round(float(score), 3) if is_own else None,
            "bbox": item["bbox"],
        }


class YoloCameraDetector(DescriptorExtractor):

    def __init__(self, model_path: str = "yolov8n.pt", live_mode: bool = False) -> None:
        super().__init__()
        self.model_path = model_path
        self.live_mode = live_mode

    def detect_objects(self, frame: np.ndarray) -> List[dict]:
        imgsz = 416 if self.live_mode else 640
        conf = 0.3 if self.live_mode else 0.35
        return detect_with_yolo(frame, self.model_path, conf=conf, imgsz=imgsz)

    def classify_detections(
        self,
        frame: np.ndarray,
        known_entities: List[dict],
    ) -> List[dict]:
        return [
            self.classify_detection(frame, item, known_entities)
            for item in self.detect_objects(frame)
        ]

    def annotate_frame(self, frame: np.ndarray, known_entities: List[dict]) -> np.ndarray:
        output = frame.copy()
        classified = self.classify_detections(frame, known_entities)

        for index, item in enumerate(classified, start=1):
            x1, y1, x2, y2 = item["bbox"]
            is_own = item["status"] == "own"
            color = OWN_COLOR if is_own else STRANGER_COLOR
            status_label = "свой" if is_own else "чужой"
            title = item["class"]

            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            caption = f"{title} | {status_label} | {item['confidence']:.0%}"
            if item.get("match_score") is not None:
                caption += f" | {item['match_score']:.0%}"
            text_y = max(y1 - 24, 4)
            output = draw_text(output, caption, (x1, text_y), color)

        output = draw_text(
            output,
            f"YOLO: {self.model_path} | зелёный=свой | красный=чужой",
            (10, 8),
            (255, 255, 255),
            font_size=16,
        )
        return output


def get_camera_detector(
    model_path: str = "yolov8n.pt",
    live_mode: bool = False,
) -> YoloCameraDetector:
    key = f"{model_path}:{'live' if live_mode else 'full'}"
    if key not in _detectors:
        _detectors[key] = YoloCameraDetector(model_path, live_mode=live_mode)
    return _detectors[key]


CameraDetector = YoloCameraDetector
