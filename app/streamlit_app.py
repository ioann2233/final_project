import streamlit as st

from service.auth import authenticate_user
from service.testing.ml_model import get_active_models
from service.testing.ml_task import get_user_tasks_rows, purchase_model
from service.testing.transaction import get_user_transactions
from service.testing.user import create_user, get_all_users, get_user_by_id
from service.testing.wallet import top_up_balance
from ui.context import run_with_context

def init_session():
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "page" not in st.session_state:
        st.session_state.page = "Главная"


def get_current_user():
    user_id = st.session_state.get("user_id")
    if not user_id:
        return None
    return run_with_context(get_user_by_id, user_id)


def login(user_id: int):
    st.session_state.user_id = user_id


def logout():
    st.session_state.user_id = None
    st.session_state.page = "Главная"


def page_home():
    st.title("ML Service — СКУД")
    st.caption("Сервис детекции объектов с балансом и ML-моделями")
    st.info("REST API: http://localhost:8080/api/docs | UI через nginx: http://localhost/")

    try:
        users = run_with_context(get_all_users)
        models = run_with_context(get_active_models)
        st.success("База данных подключена")
    except Exception as exc:
        st.error(f"База данных недоступна: {exc}")
        st.info("Запустите: `docker compose up -d database` и `flask seed-db`")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Пользователей", len(users))
    with col2:
        st.metric("ML-моделей", len(models))

    st.subheader("Пользователи")
    if users:
        st.dataframe(
            [
                {
                    "ID": u.id,
                    "Логин": u.username,
                    "Роль": u.role,
                    "Баланс": f"{u.get_balance():.2f} ₽",
                }
                for u in users
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Нет пользователей. Выполните seed-db.")

    st.subheader("ML-модели")
    if models:
        st.dataframe(
            [
                {
                    "ID": m.id,
                    "Название": m.name,
                    "Описание": m.description,
                    "Цена": f"{m.price:.2f} ₽",
                }
                for m in models
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Нет моделей.")


def page_register():
    st.title("Регистрация")
    st.caption("Создайте аккаунт в ML Service")

    with st.form("register_form"):
        username = st.text_input("Логин", placeholder="ivan")
        password = st.text_input("Пароль", type="password", placeholder="минимум 4 символа")
        initial_balance = st.number_input("Начальный баланс (₽)", min_value=0.0, value=0.0, step=1.0)
        submitted = st.form_submit_button("Зарегистрироваться", type="primary")

    if submitted:
        if not username or not password:
            st.error("Логин и пароль обязательны")
            return
        try:
            user = run_with_context(
                create_user,
                username.strip(),
                password,
                "user",
                float(initial_balance),
            )
            login(user.id)
            st.success(f"Аккаунт «{user.username}» создан! Баланс: {user.get_balance():.2f} ₽")
            st.session_state.page = "Личный кабинет"
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def page_login():
    st.title("Вход")
    st.caption("Войдите в личный кабинет")

    with st.form("login_form"):
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти", type="primary")

    if submitted:
        user = run_with_context(authenticate_user, username.strip(), password)
        if not user:
            st.error("Неверный логин или пароль")
            return
        login(user.id)
        st.success(f"Добро пожаловать, {user.username}!")
        st.session_state.page = "Личный кабинет"
        st.rerun()

    st.info("Демо: demo_user / demo1234")


def page_cabinet():
    user = get_current_user()
    if not user:
        st.warning("Войдите в систему, чтобы открыть личный кабинет.")
        if st.button("Перейти ко входу"):
            st.session_state.page = "Вход"
            st.rerun()
        return

    user = run_with_context(get_user_by_id, user.id)

    st.title("Личный кабинет")
    st.caption(f"Добро пожаловать, **{user.username}**!")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ID", user.id)
    c2.metric("Роль", user.role)
    c3.metric("Баланс", f"{user.get_balance():.2f} ₽")
    c4.metric("Логин", user.username)

    st.divider()

    st.subheader("Пополнить баланс")
    with st.form("top_up_form"):
        amount = st.number_input("Сумма (₽)", min_value=1.0, value=100.0, step=10.0)
        if st.form_submit_button("Пополнить", type="primary"):
            try:
                run_with_context(top_up_balance, user.id, float(amount))
                st.success(f"Баланс пополнен на {amount:.2f} ₽")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.divider()

    st.subheader("Купить ML-модель")
    models = run_with_context(get_active_models)
    if not models:
        st.info("Модели не найдены.")
    else:
        for model in models:
            with st.container(border=True):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"**{model.name}**")
                    st.write(model.description)
                    st.write(f"Цена: **{model.price:.2f} ₽**")
                with col_b:
                    can_buy = user.get_balance() >= model.price
                    if st.button(
                        "Купить",
                        key=f"buy_{model.id}",
                        disabled=not can_buy,
                        type="primary",
                        use_container_width=True,
                    ):
                        try:
                            run_with_context(purchase_model, user.id, model.id)
                            st.success(f"Модель «{model.name}» куплена!")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                    if not can_buy:
                        st.caption("Недостаточно средств")

    st.divider()

    st.subheader("Мои покупки")
    tasks = run_with_context(get_user_tasks_rows, user.id)
    if tasks:
        st.dataframe(tasks, use_container_width=True, hide_index=True)
    else:
        st.info("Покупок пока нет.")

    st.divider()

    st.subheader("История операций")
    transactions = run_with_context(get_user_transactions, user.id)
    if transactions:
        type_labels = {
            "top_up": "Пополнение",
            "purchase": "Покупка модели",
            "spend": "Списание",
            "refund": "Возврат",
        }
        st.dataframe(
            [
                {
                    "Дата": tx.created_at.strftime("%d.%m.%Y %H:%M"),
                    "Тип": type_labels.get(tx.transaction_type, tx.transaction_type),
                    "Сумма": f"{tx.amount:.2f} ₽",
                }
                for tx in transactions
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Операций пока нет.")


PAGES = {
    "Главная": page_home,
    "Вход": page_login,
    "Регистрация": page_register,
    "Личный кабинет": page_cabinet,
}


def main():
    st.set_page_config(
        page_title="ML Service — СКУД",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session()

    with st.sidebar:
        st.header("Навигация")
        user = get_current_user()
        if user:
            st.write(f"👤 {user.username}")
            st.write(f"💰 {user.get_balance():.2f} ₽")
            if st.button("Выйти", use_container_width=True):
                logout()
                st.rerun()
            st.divider()

        pages = list(PAGES.keys())
        if user and st.session_state.page not in pages:
            st.session_state.page = "Личный кабинет"

        selected = st.radio(
            "Раздел",
            pages,
            index=pages.index(st.session_state.page) if st.session_state.page in pages else 0,
            label_visibility="collapsed",
        )
        st.session_state.page = selected

    PAGES[st.session_state.page]()


if __name__ == "__main__":
    main()
