import time
from pathlib import Path
from typing import List, Optional

from extensions import db
from models.known_entity import KnownEntity
from service.detection.detector import DescriptorExtractor

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads" / "known"
_extractor: DescriptorExtractor | None = None


def get_extractor() -> DescriptorExtractor:
    global _extractor
    if _extractor is None:
        _extractor = DescriptorExtractor()
    return _extractor


def _resolve_image(image_path: str) -> Path:
    base = Path(__file__).resolve().parent.parent
    return base / image_path


def _entity_payload(entity: KnownEntity) -> dict:
    return {
        "id": entity.id,
        "user_id": entity.user_id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "image_path": entity.image_path,
        "descriptor": entity.get_descriptor(),
        "created_at": entity.created_at,
    }


def list_known_entities(user_id: int, entity_type: Optional[str] = None) -> List[KnownEntity]:
    query = db.session.query(KnownEntity).filter_by(user_id=user_id)
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    return query.order_by(KnownEntity.id.desc()).all()


def list_known_entities_payload(user_id: int) -> List[dict]:
    return [_entity_payload(entity) for entity in list_known_entities(user_id)]


def create_known_entity(
    user_id: int,
    entity_type: str,
    name: str,
    image_bytes: bytes,
    filename: str,
) -> KnownEntity:
    if entity_type not in {"person", "vehicle"}:
        raise ValueError("entity_type должен быть person или vehicle")
    if not name.strip():
        raise ValueError("Укажите имя")
    if not image_bytes:
        raise ValueError("Файл пустой")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        raise ValueError("Допустимы изображения jpg, png, bmp, webp")

    dest_name = f"{user_id}_{entity_type}_{int(time.time())}_{name.strip()[:40]}{suffix}"
    dest_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in dest_name)
    dest_path = UPLOAD_DIR / dest_name
    dest_path.write_bytes(image_bytes)

    import cv2
    import numpy as np

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Не удалось прочитать изображение")

    if entity_type == "person":
        descriptor = get_extractor().extract_person_descriptor(image)
    else:
        descriptor = get_extractor().extract_vehicle_descriptor(image)

    entity = KnownEntity(
        user_id=user_id,
        entity_type=entity_type,
        name=name.strip(),
        image_path=f"uploads/known/{dest_name}",
        descriptor=KnownEntity.serialize_descriptor(descriptor),
    )
    db.session.add(entity)
    db.session.commit()
    db.session.refresh(entity)
    return entity


def delete_known_entity(user_id: int, entity_id: int) -> bool:
    entity = db.session.get(KnownEntity, entity_id)
    if not entity or entity.user_id != user_id:
        return False

    image_file = _resolve_image(entity.image_path)
    db.session.delete(entity)
    db.session.commit()
    if image_file.exists():
        image_file.unlink(missing_ok=True)
    return True
