from flask import Blueprint, jsonify, request

from service.auth import authenticate_user
from service.testing.ml_model import get_active_models
from service.testing.ml_task import purchase_model
from service.testing.transaction import get_user_transactions
from service.testing.user import create_user, get_user_by_id
from service.testing.wallet import get_balance, spend_credits, top_up_balance

bp = Blueprint("api", __name__)


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = data.get("role", "user")

    try:
        initial_balance = float(data.get("initial_balance", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "initial_balance должен быть числом"}), 400

    if not username or not password:
        return jsonify({"error": "username и password обязательны"}), 400

    try:
        user = create_user(
            username=username,
            password=password,
            role=role,
            initial_balance=initial_balance,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(user.get_info()), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = authenticate_user(username, password)
    if not user:
        return jsonify({"error": "Неверный логин или пароль"}), 401

    return jsonify(user.get_info())


@bp.get("/balance/<int:user_id>")
def balance(user_id):
    try:
        value = get_balance(user_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"user_id": user_id, "balance": value})


@bp.post("/balance/top-up")
def top_up():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    amount = data.get("amount")

    if user_id is None or amount is None:
        return jsonify({"error": "user_id и amount обязательны"}), 400

    try:
        tx = top_up_balance(int(user_id), float(amount))
        user = get_user_by_id(int(user_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "transaction": tx.get_info(),
        "balance": user.get_balance() if user else None,
    })


@bp.post("/balance/spend")
def spend():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    amount = data.get("amount")

    if user_id is None or amount is None:
        return jsonify({"error": "user_id и amount обязательны"}), 400

    try:
        tx = spend_credits(int(user_id), float(amount), data.get("task_id"))
        user = get_user_by_id(int(user_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "transaction": tx.get_info(),
        "balance": user.get_balance() if user else None,
    })


@bp.get("/history/<int:user_id>")
def history(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": f"Пользователь id={user_id} не найден"}), 404

    transactions = get_user_transactions(user_id)
    return jsonify({
        "user_id": user_id,
        "transactions": [tx.get_info() for tx in transactions],
    })


@bp.get("/models")
def models():
    items = get_active_models()
    return jsonify({"models": [m.get_info() for m in items]})


@bp.post("/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    model_id = data.get("model_id")

    if user_id is None or model_id is None:
        return jsonify({"error": "user_id и model_id обязательны"}), 400

    try:
        task = purchase_model(int(user_id), int(model_id))
        user = get_user_by_id(int(user_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "task": task.get_info(),
        "balance": user.get_balance() if user else None,
    }), 201


@bp.get("/")
def index():
    return jsonify({"message": "ML Service API. UI: Streamlit на порту 8501"})
