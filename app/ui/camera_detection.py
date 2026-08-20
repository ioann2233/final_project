from typing import List

import cv2
import numpy as np
import streamlit as st

from service.detection.detector import get_camera_detector
from ui import api_client as api
from ui.api_client import APIError, log_camera_detection


def _load_known_entities(access_token: str) -> List[dict]:
    try:
        entities = api.list_known_entities_for_detection(access_token)
    except APIError as exc:
        st.error(str(exc))
        return []
    return [
        {
            "id": item["id"],
            "entity_type": item["entity_type"],
            "name": item["name"],
            "descriptor": item.get("descriptor") or [],
        }
        for item in entities
    ]


def _select_model(access_token: str) -> dict | None:
    try:
        models = api.list_models(access_token)
    except APIError as exc:
        st.error(str(exc))
        return None
    if not models:
        st.warning("Модели не найдены. Выполните `docker compose exec api python seed.py`.")
        return None

    model_ids = [item["id"] for item in models]
    if st.session_state.get("camera_model_select") not in model_ids:
        st.session_state.camera_model_select = model_ids[0]

    options = {
        item["id"]: f"{item['name']} — {item['model_path']} ({item['price']:.0f} ₽)"
        for item in models
    }
    selected_id = st.selectbox(
        "Модель YOLO",
        options=model_ids,
        format_func=lambda model_id: options[model_id],
        key="camera_model_select",
    )
    return next(item for item in models if item["id"] == selected_id)


def _show_bgr(image, caption: str) -> None:
    st.image(
        cv2.cvtColor(image, cv2.COLOR_BGR2RGB),
        channels="RGB",
        use_container_width=True,
        caption=caption,
    )


def page_camera(require_login, show_api_error, token) -> None:
    user = require_login()
    if not user:
        return

    st.title("Камера — детекция людей и машин")
    st.markdown(
        """
Детекция через **YOLO** (люди, машины, автобусы и др.) + сравнение со списком «своих» по лицу (SFace).
- **Зелёная рамка** — свой
- **Красная рамка** — чужой

Каждый запуск детекции списывает стоимость выбранной модели и пишет результат в историю.
        """
    )

    access = token()
    selected_model = _select_model(access)
    if not selected_model:
        return

    model_path = selected_model["model_path"]
    model_id = selected_model["id"]
    price = float(selected_model["price"])
    last = st.session_state.get("camera_last_result") or {}
    shown_balance = float(last["balance"]) if last.get("balance") is not None else float(user["balance"])
    st.caption(
        f"Активная модель: **{selected_model['name']}** (`{model_path}`). "
        f"Стоимость запуска: **{price:.2f} ₽**. Баланс: **{shown_balance:.2f} ₽**."
    )

    known = _load_known_entities(access)
    people_count = sum(1 for item in known if item["entity_type"] == "person")
    vehicle_count = sum(1 for item in known if item["entity_type"] == "vehicle")
    c1, c2 = st.columns(2)
    c1.metric("Своих людей", people_count)
    c2.metric("Своих машин", vehicle_count)
    st.caption(
        "Список «своих» пуст — все объекты будут чужими (красные рамки). "
        "Добавьте людей на вкладке «Свои люди и машины»."
        if not known
        else "Зелёная рамка = свой, красная = чужой."
    )

    st.subheader("Снимок")
    snapshot = st.camera_input("Сделайте снимок для анализа", key="camera_snapshot")
    can_run = snapshot is not None and shown_balance >= price
    run = st.button(
        f"Детектировать и списать {price:.2f} ₽",
        type="primary",
        key="camera_run_detection",
        disabled=not can_run,
    )

    status_text = "Сделайте снимок, затем нажмите кнопку детекции."
    annotated = None

    annotated_bytes = st.session_state.get("camera_last_annotated")
    if annotated_bytes:
        annotated = cv2.imdecode(np.frombuffer(annotated_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)

    if snapshot is None:
        status_text = "Сделайте снимок, затем нажмите кнопку детекции."
    elif shown_balance < price:
        status_text = (
            f"Недостаточно средств: нужно {price:.2f} ₽, доступно {shown_balance:.2f} ₽. "
            "Пополните баланс в личном кабинете."
        )
    else:
        file_bytes = snapshot.getvalue()
        frame = cv2.imdecode(np.frombuffer(file_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            status_text = "Не удалось прочитать кадр."
        elif run:
            detector = get_camera_detector(model_path, live_mode=False)
            annotated = detector.annotate_frame(frame, known)
            try:
                result = log_camera_detection(
                    access,
                    model_id,
                    "snapshot",
                    snapshot.name or "snapshot.jpg",
                    file_bytes,
                )
            except APIError as exc:
                status_text = str(exc)
            else:
                encoded_ok, encoded = cv2.imencode(".jpg", annotated)
                st.session_state.camera_last_result = result
                st.session_state.camera_last_annotated = encoded.tobytes() if encoded_ok else None
                last = result
                charged = float(result.get("charged") or 0)
                balance = result.get("balance")
                status_text = result.get("message") or (
                    f"Сохранено в историю: задача #{result['id']}, "
                    f"детекций: {result.get('detections_count', 0)}"
                )
                if balance is not None:
                    status_text += (
                        f" Списано {charged:.2f} ₽. Новый баланс: {float(balance):.2f} ₽. "
                        "Чтобы прогнать снимок через другую модель — выберите её и нажмите кнопку снова."
                    )
        elif last:
            charged = float(last.get("charged") or 0)
            balance = last.get("balance")
            status_text = last.get("message") or (
                f"Сохранено в историю: задача #{last['id']}, "
                f"детекций: {last.get('detections_count', 0)}"
            )
            if balance is not None:
                status_text += f" Списано {charged:.2f} ₽. Новый баланс: {float(balance):.2f} ₽."
        else:
            status_text = "Снимок готов. Нажмите кнопку, чтобы запустить детекцию и списать кредиты."

    if annotated is None:
        annotated = np.full((80, 480, 3), 36, dtype=np.uint8)
        caption = "Результат детекции появится здесь"
    else:
        caption = "Зелёный = свой, красный = чужой"
    _show_bgr(annotated, caption)
    st.info(status_text)


def page_known_entities(require_login, show_api_error, token) -> None:
    user = require_login()
    if not user:
        return

    st.title("Свои люди и машины")
    st.markdown(
        "Для **людей** — фото с чётко видимым лицом (используется SFace). "
        "Для **машин** — фото автомобиля целиком."
    )

    access = token()
    try:
        entities = api.list_known_entities(access)
    except APIError as exc:
        show_api_error(exc)
        return

    tab_add, tab_list = st.tabs(["Добавить", "Мой список"])

    with tab_add:
        entity_type = st.selectbox(
            "Тип",
            options=["person", "vehicle"],
            format_func=lambda value: "Человек" if value == "person" else "Машина",
        )
        name = st.text_input("Имя или номер", placeholder="Иван / А123BC777")
        photo = st.file_uploader(
            "Фото",
            type=["jpg", "jpeg", "png", "bmp", "webp"],
            key="known_entity_photo",
        )
        if entity_type == "person":
            st.caption("Лицо должно быть хорошо видно, без сильных теней и поворота.")
        if st.button("Добавить в «свои»", type="primary"):
            if not name.strip():
                st.error("Укажите имя.")
            elif not photo:
                st.error("Загрузите фото.")
            else:
                try:
                    result = api.add_known_entity(
                        access,
                        name.strip(),
                        entity_type,
                        photo.name,
                        photo.getvalue(),
                    )
                    st.success(result.get("message", "Добавлено"))
                    st.rerun()
                except APIError as exc:
                    show_api_error(exc)

    with tab_list:
        if not entities:
            st.info("Пока никого не добавлено.")
            return

        for item in entities:
            cols = st.columns([1, 3, 1])
            type_label = "Человек" if item["entity_type"] == "person" else "Машина"
            cols[0].write(f"**{type_label}**")
            cols[1].write(f"**{item['name']}** · `{item['image_path']}`")
            if cols[2].button("Удалить", key=f"del_{item['id']}"):
                try:
                    api.delete_known_entity(access, item["id"])
                    st.rerun()
                except APIError as exc:
                    show_api_error(exc)
