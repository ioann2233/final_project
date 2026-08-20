import re
import time
from pathlib import Path
from typing import Any, List, Optional

from deps import get_current_user
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from schemas.prediction import (
    CameraDetectionResponse,
    PredictionBatchResponse,
    PredictionCreate,
    PredictionDetailResponse,
    PredictionHistoryResponse,
    PredictionItem,
    PredictionResponse,
    RejectedItem,
    UploadResponse,
)
from service.testing.camera_log import create_camera_detection_log
from service.testing.ml_model import get_ml_model_by_id
from service.testing.ml_task import (
    charged_amount,
    create_prediction_batch,
    get_task_by_id,
    get_user_tasks,
)
from service.testing.user import get_user_by_id
from ui.context import run_with_context

prediction_route = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
ALLOWED_SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".txt", ".csv"}


def _to_prediction_item(task) -> PredictionItem:
    return PredictionItem(
        id=task.id,
        user_id=task.user_id,
        model_id=task.model_id,
        model_name=task.model.name if task.model else None,
        image_path=task.image_path,
        status=task.status,
        completed_at=task.completed_at,
        created_at=task.created_at,
        predictions=(task.result.show() if task.result else None),
        charged=charged_amount(task),
    )


def _to_prediction_response(task, balance: Optional[float] = None) -> PredictionResponse:
    return PredictionResponse(
        id=task.id,
        user_id=task.user_id,
        model_id=task.model_id,
        image_path=task.image_path,
        status=task.status,
        completed_at=task.completed_at,
        created_at=task.created_at,
        balance=balance,
        message="Задача в очереди. Списание кредитов — после успешного предикта.",
    )


def _collect_items(data: PredictionCreate) -> List[str]:
    items: List[str] = []
    if data.items:
        items.extend(data.items)
    if data.image_path:
        items.append(data.image_path)
    return items


@prediction_route.post(
    "/upload",
    response_model=UploadResponse,
    summary="Загрузка входного файла",
)
def upload_input(
    file: UploadFile = File(...),
    current=Depends(get_current_user),
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIX:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый тип файла: {suffix or 'без расширения'}",
        )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stem = SAFE_NAME.sub("_", Path(file.filename).stem) or "input"
    filename = f"{current.id}_{int(time.time())}_{stem}{suffix}"
    dest = UPLOAD_DIR / filename
    dest.write_bytes(file.file.read())
    return UploadResponse(path=f"uploads/{filename}", filename=file.filename)


CAMERA_DIR = UPLOAD_DIR / "camera"
CAMERA_MODES = {"snapshot", "live"}


@prediction_route.post(
    "/camera",
    response_model=CameraDetectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Детекция с камеры и запись в историю",
)
def camera_detection(
    model_id: int = Form(...),
    mode: str = Form(...),
    file: UploadFile = File(...),
    current=Depends(get_current_user),
) -> CameraDetectionResponse:
    if mode not in CAMERA_MODES:
        raise HTTPException(status_code=400, detail="mode: snapshot или live")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")

    suffix = Path(file.filename).suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        raise HTTPException(status_code=400, detail="Нужно изображение jpg/png/webp")

    content = file.file.read()

    def _handler():
        import cv2
        import numpy as np

        from service.detection.detector import get_camera_detector
        from service.known_entity import list_known_entities_payload

        model = get_ml_model_by_id(model_id)
        if not model or not model.is_active:
            raise ValueError("Модель не найдена или недоступна")

        user = get_user_by_id(current.id)
        price = float(model.price)
        if user and user.get_balance() < price:
            raise ValueError(
                f"Недостаточно средств на балансе: нужно {price:.2f} ₽, "
                f"доступно {user.get_balance():.2f} ₽"
            )

        image_array = np.frombuffer(content, dtype=np.uint8)
        frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Не удалось прочитать изображение")

        known = list_known_entities_payload(current.id)
        detector = get_camera_detector(model.model_path, live_mode=(mode == "live"))
        detections = detector.classify_detections(frame, known)

        CAMERA_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{current.id}_{mode}_{time.time_ns()}{suffix}"
        dest = CAMERA_DIR / filename
        dest.write_bytes(content)
        image_path = f"uploads/camera/{filename}"

        task, charged, balance = create_camera_detection_log(
            current.id,
            model_id,
            mode,
            detections,
            image_path,
        )
        return CameraDetectionResponse(
            id=task.id,
            model_id=model.id,
            model_name=model.name,
            image_path=image_path,
            mode=mode,
            detections_count=len(detections),
            predictions=detections,
            charged=charged,
            balance=balance,
            price=price,
            message=(
                f"Детекция сохранена в историю. Списано {charged:.2f} ₽, "
                f"баланс {balance:.2f} ₽"
            ),
        )

    try:
        return run_with_context(_handler)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@prediction_route.post(
    "/",
    response_model=PredictionBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="ML-запрос (валидация + очередь)",
)
def create_prediction(
    data: PredictionCreate,
    current=Depends(get_current_user),
) -> PredictionBatchResponse:
    items = _collect_items(data)
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Передайте items или image_path",
        )

    def _handler():
        model = get_ml_model_by_id(data.model_id)
        if not model or not model.is_active:
            raise ValueError("Модель не найдена или недоступна")
        tasks, rejected, balance = create_prediction_batch(
            current.id, data.model_id, items
        )
        user = get_user_by_id(current.id)
        return PredictionBatchResponse(
            accepted=[_to_prediction_response(task, balance) for task in tasks],
            rejected=[RejectedItem(**item) for item in rejected],
            balance=user.get_balance() if user else balance,
            price_per_item=model.price,
            message=(
                f"Принято {len(tasks)}, отклонено {len(rejected)}. "
                "Кредиты спишутся после успешного выполнения."
            ),
        )

    try:
        result = run_with_context(_handler)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not result.accepted and result.rejected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Все входные данные отклонены валидацией",
                "rejected": [item.model_dump() for item in result.rejected],
            },
        )
    return result


@prediction_route.get(
    "/history/{user_id}",
    response_model=PredictionHistoryResponse,
    summary="История запросов на предсказания",
)
def prediction_history(
    user_id: int,
    current=Depends(get_current_user),
) -> PredictionHistoryResponse:
    if current.role != "admin" and current.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")

    def _handler():
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь id={user_id} не найден",
            )
        tasks = get_user_tasks(user_id)
        return PredictionHistoryResponse(
            user_id=user_id,
            predictions=[_to_prediction_item(task) for task in tasks],
        )

    return run_with_context(_handler)


@prediction_route.get(
    "/{task_id}",
    response_model=PredictionDetailResponse,
    summary="Результат предсказания по task_id",
)
def get_prediction(
    task_id: int,
    current=Depends(get_current_user),
) -> PredictionDetailResponse:
    def _handler():
        task = get_task_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Задача id={task_id} не найдена",
            )
        if current.role != "admin" and task.user_id != current.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
        predictions: List[Any] = task.result.show() if task.result else []
        return PredictionDetailResponse(
            id=task.id,
            user_id=task.user_id,
            model_id=task.model_id,
            model_name=task.model.name if task.model else None,
            image_path=task.image_path,
            status=task.status,
            completed_at=task.completed_at,
            created_at=task.created_at,
            predictions=predictions,
            predictions_count=len(predictions),
            charged=charged_amount(task),
        )

    return run_with_context(_handler)
