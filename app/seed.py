from database.database import init_db
from main import create_app
from service.testing.ml_model import create_ml_model, get_all_models
from service.testing.user import create_user, get_user_by_username

DEMO_USERS = [
    {
        "username": "demo_user",
        "password": "demo1234",
        "role": "user",
        "initial_balance": 100.0,
    },
    {
        "username": "demo_admin",
        "password": "admin1234",
        "role": "admin",
        "initial_balance": 1000.0,
    },
]

DEMO_MODELS = [
    {
        "name": "YOLOv8n Detection",
        "description": "Лёгкая модель",
        "price": 10.0,
        "model_path": "yolov8n.pt",
    },
    {
        "name": "YOLOv8s Detection",
        "description": "Средняя модель",
        "price": 25.0,
        "model_path": "yolov8s.pt",
    },
    {
        "name": "Access Control Detector",
        "description": "Детекция 'своих' и 'чужих'",
        "price": 40.0,
        "model_path": "yolov8n.pt",
    },
]


def seed_database(drop_all: bool = True) -> None:
    app = create_app()
    init_db(app, drop_all=drop_all)

    with app.app_context():
        print("=== Seed: создание демо-пользователей ===")
        for user_data in DEMO_USERS:
            existing = get_user_by_username(user_data["username"])
            if existing:
                print(f"  уже существует: {existing}")
                continue

            user = create_user(
                username=user_data["username"],
                password=user_data["password"],
                role=user_data["role"],
                initial_balance=user_data["initial_balance"],
            )
            print(f"  создан: {user} | баланс={user.get_balance()}")

        print("\n=== Seed: создание базовых ML-моделей ===")
        existing_names = {m.name for m in get_all_models()}
        for model_data in DEMO_MODELS:
            if model_data["name"] in existing_names:
                print(f"  уже существует: {model_data['name']}")
                continue

            model = create_ml_model(**model_data)
            print(f"  создана: {model}")

        print("\nSeed завершён успешно.")


if __name__ == "__main__":
    seed_database(drop_all=True)
