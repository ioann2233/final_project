from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

MODEL_DIR = Path(__file__).resolve().parent / "models_data"
YUNET_MODEL = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_MODEL = MODEL_DIR / "face_recognition_sface_2021dec.onnx"

YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
SFACE_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_recognition_sface/face_recognition_sface_2021dec.onnx"
)

FACE_MATCH_THRESHOLD = 0.45
_engine: Optional["FaceEngine"] = None


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return
    urllib.request.urlretrieve(url, destination)


class FaceEngine:

    def __init__(self) -> None:
        _download(YUNET_URL, YUNET_MODEL)
        _download(SFACE_URL, SFACE_MODEL)
        self._detector = cv2.FaceDetectorYN.create(
            str(YUNET_MODEL),
            "",
            (320, 320),
            score_threshold=0.6,
            nms_threshold=0.3,
            top_k=5000,
        )
        self._recognizer = cv2.FaceRecognizerSF.create(str(SFACE_MODEL), "")

    def _detect_faces(self, image: np.ndarray):
        height, width = image.shape[:2]
        self._detector.setInputSize((width, height))
        _, faces = self._detector.detect(image)
        if faces is None:
            return []
        return list(faces)

    def extract_face_embedding(self, image: np.ndarray) -> Optional[List[float]]:
        faces = self._detect_faces(image)
        if not faces:
            return None
        face = max(faces, key=lambda item: float(item[2]) * float(item[3]))
        aligned = self._recognizer.alignCrop(image, face)
        feature = self._recognizer.feature(aligned)
        return feature.flatten().astype(float).tolist()

    @staticmethod
    def embedding_similarity(first: List[float], second: List[float]) -> float:
        a = np.array(first, dtype=np.float32)
        b = np.array(second, dtype=np.float32)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom <= 1e-8:
            return -1.0
        return float(np.dot(a, b) / denom)

    def match_person(
        self,
        embedding: List[float],
        known_entities: List[dict],
    ) -> tuple[bool, Optional[str], float]:
        best_name: Optional[str] = None
        best_score = -1.0
        for entity in known_entities:
            if entity.get("entity_type") != "person":
                continue
            descriptor = entity.get("descriptor") or []
            if len(descriptor) != len(embedding):
                continue
            score = self.embedding_similarity(embedding, descriptor)
            if score > best_score:
                best_score = score
                best_name = entity.get("name")
        if best_score >= FACE_MATCH_THRESHOLD and best_name:
            return True, best_name, best_score
        return False, None, best_score


def get_face_engine() -> FaceEngine:
    global _engine
    if _engine is None:
        _engine = FaceEngine()
    return _engine
