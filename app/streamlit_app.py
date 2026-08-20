from typing import Optional

import streamlit as st

from auth.forms import LoginForm, RegisterForm
from ui import api_client as api
from ui.api_client import APIError

STATUS_LABELS = {
    "created": "Создана",
    "running": "Выполняется",
    "completed": "Готово",
    "failed": "Ошибка",
    "not enough balance": "Недостаточно средств",
}
TX_LABELS = {
    "top_up": "Пополнение",
    "purchase": "Списание за предикт",
    "spend": "Списание",
    "refund": "Возврат",
}


def init_session():
    st.session_state.setdefault("access_token", None)


def token() -> Optional[str]:
    return st.session_state.get("access_token")


def show_api_error(exc: APIError) -> None:
    st.error(str(exc))
    payload = exc.payload or {}
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict) and detail.get("rejected"):
        st.subheader("Отклонённые данные")
        st.dataframe(detail["rejected"], use_container_width=True, hide_index=True)


def current_user() -> Optional[dict]:
    access = token()
    if not access:
        return None
    try:
        return api.me(access)
    except APIError:
        st.session_state.access_token = None
        return None


def require_login() -> Optional[dict]:
    user = current_user()
    if not user:
        st.warning("Войдите, чтобы открыть личный кабинет.")
        return None
    return user


def page_home():
    st.title("ML Service — личный кабинет СКУД")
    st.markdown(
        """
Сервис детекции объектов для систем контроля доступа: загрузите кадры с камеры,
выберите модель и получите список найденных объектов (`person`, `own`/`stranger` и др.).

**Что умеет кабинет**
- регистрация и вход (JWT);
- **камера**: детекция людей и машин, зелёная рамка — «свой», красная — «чужой»;
- **свои люди и машины**: загрузка фото для распознавания;
- баланс в условных кредитах и пополнение без эквайринга;
- история загрузок, предсказаний и списаний.

Списание кредитов происходит **только после успешной** детекции (файл через воркер или снимок с камеры).
При нулевом или недостаточном балансе запрос отклоняется.
        """
    )
    user = current_user()
    if user:
        st.success(f"Вы вошли как **{user['username']}**. Баланс: {user['balance']:.2f} ₽")
    else:
        st.info("Авторизация не нужна для этой страницы. Чтобы работать с балансом и предиктами — войдите.")
        st.caption("Демо: `demo_user` / `demo1234` · админ: `demo_admin` / `admin1234`")

    st.subheader("Доступные модели")
    try:
        models = api.list_models()
    except APIError as exc:
        show_api_error(exc)
        return
    if not models:
        st.info("Модели не загружены. Выполните `docker compose exec api python seed.py`.")
        return
    st.dataframe(
        [
            {
                "ID": item["id"],
                "Название": item["name"],
                "Описание": item["description"],
                "Цена, ₽": item["price"],
            }
            for item in models
        ],
        use_container_width=True,
        hide_index=True,
    )


def page_login():
    st.title("Вход")
    with st.form("login_form"):
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти", type="primary")
    if not submitted:
        return
    form = LoginForm(username, password)
    if not form.is_valid():
        for error in form.errors:
            st.error(error)
        return
    try:
        data = api.signin(form.username, form.password)
    except APIError as exc:
        show_api_error(exc)
        return
    st.session_state.access_token = data["access_token"]
    st.success(f"Вход выполнен. Добро пожаловать, {data['username']}!")
    st.rerun()


def page_register():
    st.title("Регистрация")
    with st.form("register_form"):
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        initial_balance = st.number_input("Начальный баланс (₽)", min_value=0.0, value=0.0, step=1.0)
        submitted = st.form_submit_button("Создать аккаунт", type="primary")
    if not submitted:
        return
    form = RegisterForm(username, password, float(initial_balance))
    if not form.is_valid():
        for error in form.errors:
            st.error(error)
        return
    try:
        data = api.signup(form.username, form.password, form.initial_balance)
    except APIError as exc:
        show_api_error(exc)
        return
    st.session_state.access_token = data["access_token"]
    st.success(f"Аккаунт «{data['username']}» создан. Баланс: {data['balance']:.2f} ₽")
    st.rerun()


def page_cabinet():
    user = require_login()
    if not user:
        return

    st.title("Личный кабинет")
    c1, c2, c3 = st.columns(3)
    c1.metric("Логин", user["username"])
    c2.metric("Роль", user["role"])
    c3.metric("Баланс, ₽", f"{user['balance']:.2f}")
    st.caption("Баланс хранится на backend. Интерфейс только запрашивает и инициирует операции.")

    st.subheader("Пополнить баланс")
    cols = st.columns(4)
    for amount, col in zip((50, 100, 250, 500), cols):
        if col.button(f"+ {amount} ₽", use_container_width=True):
            try:
                result = api.top_up(token(), float(amount))
                st.success(f"Пополнено на {amount} ₽. Новый баланс: {result['balance']:.2f} ₽")
                st.rerun()
            except APIError as exc:
                show_api_error(exc)

    with st.form("top_up_manual"):
        amount = st.number_input("Сумма вручную (₽)", min_value=1.0, value=100.0, step=10.0)
        if st.form_submit_button("Пополнить", type="primary"):
            try:
                result = api.top_up(token(), float(amount))
                st.success(f"Пополнено на {amount:.2f} ₽. Новый баланс: {result['balance']:.2f} ₽")
                st.rerun()
            except APIError as exc:
                show_api_error(exc)


def _format_dt(value) -> str:
    if not value:
        return "—"
    text = str(value)
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except ValueError:
        return text[:19].replace("T", " ")


def _source_label(path: str) -> str:
    normalized = (path or "").replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    if "uploads/camera/" in normalized or normalized.startswith("camera/"):
        if "live" in name or "/live" in normalized:
            return "Камера (live)"
        return "Камера"
    return "Файл"


def page_history():
    user = require_login()
    if not user:
        return

    st.title("История операций и предсказаний")
    if st.button("Обновить"):
        st.rerun()

    access = token()
    try:
        pred = api.prediction_history(access, user["id"])
        txs = api.transactions(access, user["id"])
    except APIError as exc:
        show_api_error(exc)
        return

    st.subheader("Детекции")
    rows = pred.get("predictions") or []
    if rows:
        st.dataframe(
            [
                {
                    "ID": item["id"],
                    "Дата": _format_dt(item.get("created_at")),
                    "Источник": _source_label(item.get("image_path") or ""),
                    "Данные": item["image_path"],
                    "Модель": item.get("model_name") or item["model_id"],
                    "Статус": STATUS_LABELS.get(item["status"], item["status"]),
                    "Списание, ₽": round(float(item.get("charged") or 0), 2),
                    "Детекций": len(item["predictions"] or []),
                }
                for item in rows
            ],
            use_container_width=True,
            hide_index=True,
        )
        labels = {
            item["id"]: (
                f"#{item['id']} · {item.get('model_name') or item['model_id']} · "
                f"{STATUS_LABELS.get(item['status'], item['status'])} · "
                f"{float(item.get('charged') or 0):.2f} ₽"
            )
            for item in rows
        }
        selected = st.selectbox(
            "Результат задачи",
            options=list(labels.keys()),
            format_func=lambda task_id: labels[task_id],
        )
        try:
            detail = api.get_prediction(access, int(selected))
        except APIError as exc:
            show_api_error(exc)
            return
        st.write(
            f"Статус: **{STATUS_LABELS.get(detail['status'], detail['status'])}** · "
            f"списано **{float(detail.get('charged') or 0):.2f} ₽**"
        )
        if detail["status"] in {"created", "running"}:
            st.info("Воркер ещё считает. Нажмите «Обновить».")
        detections = detail.get("predictions") or []
        if detections:
            st.dataframe(detections, use_container_width=True, hide_index=True)
        elif detail["status"] == "completed":
            st.info("Детекций нет.")
        elif detail["status"] == "failed":
            st.error("Предикт не удался, списания нет (или выполнен возврат).")
        elif detail["status"] == "not enough balance":
            st.error("Недостаточно средств — списания нет.")
    else:
        st.info("Запросов пока нет.")

    st.subheader("Движение кредитов")
    tx_rows = txs.get("transactions") or []
    if tx_rows:
        st.dataframe(
            [
                {
                    "Дата": _format_dt(item.get("created_at")),
                    "Тип": TX_LABELS.get(item.get("type"), item.get("type")),
                    "Сумма, ₽": round(float(item.get("amount") or 0), 2),
                    "Задача": item.get("task_id") if item.get("task_id") else "—",
                }
                for item in tx_rows
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Транзакций пока нет.")


def page_admin():
    user = require_login()
    if not user:
        return
    if user["role"] != "admin":
        st.error("Доступ только для администратора.")
        return

    st.title("Админ-панель")
    access = token()
    try:
        users = api.list_users(access)
        txs = api.all_transactions(access)
    except APIError as exc:
        show_api_error(exc)
        return

    st.subheader("Пользователи")
    st.dataframe(
        [
            {
                "ID": item["id"],
                "Логин": item["username"],
                "Роль": item["role"],
                "Баланс": item["balance"],
            }
            for item in users
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Пополнить баланс пользователя")
    with st.form("admin_top_up"):
        user_id = st.number_input("ID пользователя", min_value=1, step=1)
        amount = st.number_input("Сумма (₽)", min_value=1.0, value=100.0, step=10.0)
        if st.form_submit_button("Пополнить", type="primary"):
            try:
                result = api.top_up(access, float(amount), user_id=int(user_id))
                st.success(f"Баланс пользователя {user_id}: {result['balance']:.2f} ₽")
                st.rerun()
            except APIError as exc:
                show_api_error(exc)

    st.subheader("Все транзакции")
    tx_rows = txs.get("transactions") or []
    if tx_rows:
        st.dataframe(
            [
                {
                    "Дата": item["created_at"],
                    "User ID": item["user_id"],
                    "Тип": TX_LABELS.get(item["type"], item["type"]),
                    "Сумма": item["amount"],
                    "Задача": item.get("task_id") or "—",
                }
                for item in tx_rows
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Транзакций нет.")


def main():
    st.set_page_config(
        page_title="ML Service — кабинет",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session()
    user = current_user()

    PAGE_LABELS = {
        "home": "Главная",
        "login": "Вход",
        "register": "Регистрация",
        "cabinet": "Личный кабинет",
        "camera": "Камера",
        "known": "Свои люди и машины",
        "history": "История",
        "admin": "Админ",
    }

    if user:
        page_keys = ["home", "cabinet", "camera", "known", "history"]
        if user["role"] == "admin":
            page_keys.append("admin")
    else:
        page_keys = ["home", "login", "register"]

    if st.session_state.get("main_navigation") not in page_keys:
        st.session_state.main_navigation = page_keys[0]

    with st.sidebar:
        st.header("Навигация")
        page_key = st.radio(
            "Страница",
            options=page_keys,
            format_func=lambda key: PAGE_LABELS[key],
            key="main_navigation",
            label_visibility="collapsed",
        )
        if user:
            st.write(f"👤 {user['username']}")
            st.write(f"💰 {user['balance']:.2f} ₽")
            if st.button("Выйти", use_container_width=True):
                st.session_state.access_token = None
                st.rerun()
        st.caption("UI → REST API → очередь → воркер")

    if page_key == "home":
        page_home()
    elif page_key == "login":
        page_login()
    elif page_key == "register":
        page_register()
    elif page_key == "cabinet":
        page_cabinet()
    elif page_key == "camera":
        from ui.camera_detection import page_camera

        page_camera(require_login, show_api_error, token)
    elif page_key == "known":
        from ui.camera_detection import page_known_entities

        page_known_entities(require_login, show_api_error, token)
    elif page_key == "history":
        page_history()
    elif page_key == "admin":
        page_admin()


if __name__ == "__main__":
    main()
