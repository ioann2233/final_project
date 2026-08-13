import io
from typing import Optional

import pandas as pd
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
- баланс в условных кредитах и пополнение без эквайринга;
- ML-запрос через тот же REST API, что доступен снаружи;
- частичная валидация входа: ошибочные строки возвращаются, корректные идут в предикт;
- история загрузок, предсказаний и списаний.

Списание кредитов происходит **только после успешного** выполнения запроса воркером.
При нулевом или недостаточном балансе запрос не ставится в очередь.
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


def _parse_uploaded_table(uploaded) -> list[str]:
    name = uploaded.name.lower()
    raw = uploaded.getvalue()
    if name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(raw))
        for column in ("path", "image_path", "image", "file"):
            if column in df.columns:
                return [str(value) for value in df[column].tolist()]
        return [str(value) for value in df.iloc[:, 0].tolist()]
    text = raw.decode("utf-8", errors="replace")
    return [line.strip() for line in text.splitlines() if line.strip()]


def page_predict():
    user = require_login()
    if not user:
        return

    st.title("ML-запрос")
    st.caption(
        f"Баланс: **{user['balance']:.2f} ₽**. "
        "Списание только после успешного предикта. Некорректные строки вернутся в таблице ошибок."
    )
    if user["balance"] <= 0:
        st.error("Недостаточно средств на балансе. Пополните счёт в кабинете — запрос не будет выполнен.")

    try:
        models = api.list_models(token())
    except APIError as exc:
        show_api_error(exc)
        return
    if not models:
        st.info("Нет активных моделей.")
        return

    options = {f"{item['name']} — {item['price']:.2f} ₽": item for item in models}
    selected = st.selectbox("Модель", list(options.keys()))
    model = options[selected]

    st.markdown("Введите пути **по одному на строку** и/или загрузите файл (изображение, txt, csv).")
    text_items = st.text_area(
        "Входные данные",
        value="uploads/demo.jpg\nuploads/bad path!.jpg",
        height=120,
    )
    files = st.file_uploader(
        "Файлы",
        accept_multiple_files=True,
        type=["jpg", "jpeg", "png", "bmp", "webp", "txt", "csv"],
    )

    if not st.button("Отправить в ML-сервис", type="primary"):
        return

    items: list[str] = [line.strip() for line in text_items.splitlines() if line.strip()]
    access = token()
    for uploaded in files or []:
        name = uploaded.name.lower()
        try:
            if name.endswith((".txt", ".csv")):
                items.extend(_parse_uploaded_table(uploaded))
            else:
                saved = api.upload_file(access, uploaded.name, uploaded.getvalue())
                items.append(saved["path"])
                st.caption(f"Загружено: {saved['filename']} → `{saved['path']}`")
        except APIError as exc:
            show_api_error(exc)
            return

    if not items:
        st.error("Добавьте хотя бы одну строку или файл.")
        return

    try:
        result = api.create_predictions(access, model["id"], items)
    except APIError as exc:
        show_api_error(exc)
        return

    st.success(result.get("message", "Запрос принят"))
    st.info(f"Баланс после постановки в очередь (ещё без списания): {result['balance']:.2f} ₽")

    rejected = result.get("rejected") or []
    accepted = result.get("accepted") or []
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Обработаны (приняты)")
        if accepted:
            st.dataframe(
                [
                    {
                        "task_id": item["id"],
                        "данные": item["image_path"],
                        "статус": STATUS_LABELS.get(item["status"], item["status"]),
                    }
                    for item in accepted
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.write("Нет")
    with col_b:
        st.subheader("Отклонены валидацией")
        if rejected:
            st.dataframe(rejected, use_container_width=True, hide_index=True)
        else:
            st.write("Нет")


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

    st.subheader("ML-запросы")
    rows = pred.get("predictions") or []
    if rows:
        st.dataframe(
            [
                {
                    "Дата": item["created_at"],
                    "Данные": item["image_path"],
                    "Модель": item.get("model_name") or item["model_id"],
                    "Статус": STATUS_LABELS.get(item["status"], item["status"]),
                    "Списание, ₽": item.get("charged", 0),
                    "Детекций": len(item["predictions"] or []),
                }
                for item in rows
            ],
            use_container_width=True,
            hide_index=True,
        )
        ids = [item["id"] for item in rows]
        selected = st.selectbox("Результат задачи", ids)
        try:
            detail = api.get_prediction(access, int(selected))
        except APIError as exc:
            show_api_error(exc)
            return
        st.write(
            f"Статус: **{STATUS_LABELS.get(detail['status'], detail['status'])}** · "
            f"списано {detail.get('charged', 0):.2f} ₽"
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
    else:
        st.info("Запросов пока нет.")

    st.subheader("Движение кредитов")
    tx_rows = txs.get("transactions") or []
    if tx_rows:
        st.dataframe(
            [
                {
                    "Дата": item["created_at"],
                    "Тип": TX_LABELS.get(item["type"], item["type"]),
                    "Сумма, ₽": item["amount"],
                    "Задача": item.get("task_id") or "—",
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

    if user:
        pages = ["Главная", "Личный кабинет", "ML-запрос", "История"]
        if user["role"] == "admin":
            pages.append("Админ")
    else:
        pages = ["Главная", "Вход", "Регистрация"]

    with st.sidebar:
        st.header("Навигация")
        page = st.selectbox("Выбрать страницу", pages)
        if user:
            st.write(f"👤 {user['username']}")
            st.write(f"💰 {user['balance']:.2f} ₽")
            if st.button("Выйти", use_container_width=True):
                st.session_state.access_token = None
                st.rerun()
        st.caption("UI → REST API → очередь → воркер")

    if page == "Главная":
        page_home()
    elif page == "Вход":
        page_login()
    elif page == "Регистрация":
        page_register()
    elif page == "Личный кабинет":
        page_cabinet()
    elif page == "ML-запрос":
        page_predict()
    elif page == "История":
        page_history()
    elif page == "Админ":
        page_admin()


if __name__ == "__main__":
    main()
