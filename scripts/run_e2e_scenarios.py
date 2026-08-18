"""
Сквозные E2E-сценарии против запущенного Docker Compose.

Запуск:
  docker compose up --build -d --scale ml_worker=3
  docker compose exec api python seed.py
  python scripts/run_e2e_scenarios.py

Переменная окружения API_BASE_URL (по умолчанию http://localhost:8080).
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid

import requests

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8080").rstrip("/")
TIMEOUT = 30


class ScenarioRunner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.token: str | None = None
        self.user_id: int | None = None
        self.model_id: int | None = None
        self.task_id: int | None = None

    def ok(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"  [OK] {name}")
        else:
            self.failed += 1
            print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))

    def section(self, title: str) -> None:
        print(f"\n=== {title} ===")

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{API_BASE}{path}"
        headers = kwargs.pop("headers", {})
        if self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        return requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)

    def check_health(self) -> bool:
        self.section("Шаг 1. Проверка окружения")
        try:
            r = self.request("GET", "/health")
        except requests.RequestException as exc:
            print(f"  API недоступен: {exc}")
            print("  Запустите: docker compose up --build -d && docker compose exec api python seed.py")
            return False
        self.ok("Health check", r.status_code == 200 and r.json().get("status") == "healthy", r.text)
        return r.status_code == 200

    def test_users(self) -> None:
        self.section("Шаг 2. Пользователи")
        suffix = uuid.uuid4().hex[:8]
        username = f"e2e_user_{suffix}"
        password = "e2e_pass1234"

        r = self.request(
            "POST",
            "/api/users/signup",
            json={"username": username, "password": password, "initial_balance": 0},
        )
        self.ok("Создание пользователя", r.status_code == 201, r.text)
        if r.status_code == 201:
            data = r.json()
            self.token = data["access_token"]
            self.user_id = data["id"]

        r = self.request("POST", "/api/users/signin", json={"username": username, "password": password})
        self.ok("Авторизация", r.status_code == 200 and "access_token" in r.json(), r.text)
        if r.status_code == 200:
            self.token = r.json()["access_token"]

        r = self.request("POST", "/api/users/signin", json={"username": username, "password": password})
        self.ok("Повторная авторизация", r.status_code == 200, r.text)

        r = self.request("POST", "/api/users/signin", json={"username": username, "password": "wrong"})
        self.ok("Ошибка при неверном пароле", r.status_code == 401, r.text)

        r = self.request("GET", "/api/users/me")
        self.ok("/me с токеном", r.status_code == 200 and r.json()["username"] == username, r.text)

    def test_balance(self) -> None:
        self.section("Шаг 3. Баланс")
        assert self.user_id is not None

        r = self.request("GET", f"/api/balance/{self.user_id}")
        self.ok("Начальный баланс = 0", r.status_code == 200 and r.json()["balance"] == 0, r.text)

        r = self.request("POST", "/api/balance/top-up", json={"amount": 100.0})
        self.ok("Пополнение 100", r.status_code == 200 and r.json()["balance"] == 100.0, r.text)

        r = self.request("GET", f"/api/balance/{self.user_id}")
        self.ok("Баланс после пополнения", r.json()["balance"] == 100.0, r.text)

    def test_ml(self) -> None:
        self.section("Шаг 4. ML-запросы и списание")
        assert self.user_id is not None

        r = self.request("GET", "/api/models/")
        self.ok("Список моделей", r.status_code == 200 and len(r.json()) > 0, r.text)
        if r.status_code == 200 and r.json():
            self.model_id = r.json()[0]["id"]
            model_price = r.json()[0]["price"]
        else:
            return

        r = self.request(
            "POST",
            "/api/predictions/",
            json={"model_id": self.model_id, "image_path": "uploads/e2e_test.jpg"},
        )
        self.ok("Корректный ML-запрос", r.status_code == 201, r.text)
        if r.status_code == 201:
            accepted = r.json()["accepted"]
            self.task_id = accepted[0]["id"] if accepted else None
            self.ok("Баланс не списан до выполнения", r.json()["balance"] == 100.0, r.text)

        partial = self.request(
            "POST",
            "/api/predictions/",
            json={"model_id": self.model_id, "items": ["", "uploads/valid.jpg"]},
        )
        if partial.status_code == 201:
            data = partial.json()
            self.ok("Частично валидные данные", len(data["accepted"]) == 1 and len(data["rejected"]) == 1)
        else:
            self.ok("Частично валидные данные", False, partial.text)

        r = self.request(
            "POST",
            "/api/predictions/",
            json={"model_id": self.model_id, "items": ["", "null"]},
        )
        self.ok("Некорректные данные — 400", r.status_code == 400, r.text)

        if self.task_id:
            for _ in range(20):
                first = self.request("GET", f"/api/predictions/{self.task_id}").json()
                if first.get("status") in {"completed", "failed", "not enough balance"}:
                    break
                time.sleep(2)

            self.ok(
                "Предсказание выполнено worker'ом",
                first.get("status") == "completed",
                f"status={first.get('status')}",
            )
            self.ok("Списание после успеха", first.get("charged", 0) == model_price)

            bal = self.request("GET", f"/api/balance/{self.user_id}").json()["balance"]
            self.ok(
                "Баланс уменьшился",
                bal == 100.0 - model_price,
                f"balance={bal}",
            )

        self._test_insufficient_balance(model_price)

    def _test_insufficient_balance(self, model_price: float) -> None:
        """Отдельный пользователь с балансом ниже цены модели."""
        suffix = uuid.uuid4().hex[:8]
        username = f"e2e_poor_{suffix}"
        password = "e2e_pass1234"
        low_balance = max(model_price - 5.0, 0.0)

        r = self.request(
            "POST",
            "/api/users/signup",
            json={
                "username": username,
                "password": password,
                "initial_balance": low_balance,
            },
        )
        if r.status_code != 201:
            self.ok("Запрет при недостаточном балансе", False, r.text)
            return

        poor_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {poor_token}"}
        r = self.request(
            "POST",
            "/api/predictions/",
            headers=headers,
            json={"model_id": self.model_id, "image_path": "uploads/no_money.jpg"},
        )
        self.ok(
            "Запрет при недостаточном балансе",
            r.status_code == 400 and "Недостаточно средств" in r.text,
            f"status={r.status_code}, balance={low_balance}, price={model_price}",
        )

    def test_history(self) -> None:
        self.section("Шаг 5. История операций")
        assert self.user_id is not None

        r = self.request("GET", f"/api/balance/transactions/{self.user_id}")
        self.ok("История транзакций", r.status_code == 200 and len(r.json()["transactions"]) >= 1, r.text)
        types = {tx["type"] for tx in r.json()["transactions"]}
        self.ok("Есть top_up и purchase", "top_up" in types, str(types))

        r = self.request("GET", f"/api/predictions/history/{self.user_id}")
        self.ok("История ML-запросов", r.status_code == 200 and len(r.json()["predictions"]) >= 1, r.text)

    def run(self) -> int:
        print(f"E2E тестирование ML Service API: {API_BASE}")
        if not self.check_health():
            return 1
        self.test_users()
        self.test_balance()
        self.test_ml()
        self.test_history()
        print(f"\nИтого: {self.passed} OK, {self.failed} FAIL")
        return 0 if self.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(ScenarioRunner().run())
