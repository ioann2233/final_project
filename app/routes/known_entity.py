import re
import time
from pathlib import Path

from deps import get_current_user
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from schemas.known_entity import (
    KnownEntityCreateResponse,
    KnownEntityDetectionItem,
    KnownEntityDetectionResponse,
    KnownEntityListResponse,
    KnownEntityResponse,
)
from service.known_entity import (
    create_known_entity,
    delete_known_entity,
    list_known_entities,
)
from ui.context import run_with_context

known_entity_route = APIRouter()

ALLOWED_TYPES = {"person", "vehicle"}
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _to_response(entity) -> KnownEntityResponse:
    return KnownEntityResponse(**entity.get_info())


@known_entity_route.get(
    "/",
    response_model=KnownEntityListResponse,
    summary="Список «своих» людей и машин",
)
def get_known_entities(current=Depends(get_current_user)) -> KnownEntityListResponse:
    def _handler():
        entities = list_known_entities(current.id)
        return KnownEntityListResponse(entities=[_to_response(item) for item in entities])

    return run_with_context(_handler)


@known_entity_route.get(
    "/detection-data",
    response_model=KnownEntityDetectionResponse,
    summary="Данные для детекции на камере (с дескрипторами)",
)
def get_detection_data(current=Depends(get_current_user)) -> KnownEntityDetectionResponse:
    def _handler():
        from service.known_entity import list_known_entities_payload

        payload = list_known_entities_payload(current.id)
        entities = [
            KnownEntityDetectionItem(
                id=item["id"],
                entity_type=item["entity_type"],
                name=item["name"],
                descriptor=item["descriptor"],
            )
            for item in payload
        ]
        return KnownEntityDetectionResponse(entities=entities)

    return run_with_context(_handler)


@known_entity_route.post(
    "/",
    response_model=KnownEntityCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить «своего» человека или машину",
)
def add_known_entity(
    name: str = Form(..., description="Имя или номер"),
    entity_type: str = Form(..., description="person или vehicle"),
    file: UploadFile = File(...),
    current=Depends(get_current_user),
) -> KnownEntityCreateResponse:
    if entity_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entity_type: person или vehicle",
        )
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")

    content = file.file.read()
    filename = SAFE_NAME.sub("_", Path(file.filename).name) or f"photo_{int(time.time())}.jpg"

    def _handler():
        try:
            entity = create_known_entity(
                current.id,
                entity_type,
                name,
                content,
                filename,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return KnownEntityCreateResponse(entity=_to_response(entity))

    return run_with_context(_handler)


@known_entity_route.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить из списка «своих»",
)
def remove_known_entity(entity_id: int, current=Depends(get_current_user)) -> None:
    def _handler():
        deleted = delete_known_entity(current.id, entity_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Запись не найдена")

    run_with_context(_handler)
