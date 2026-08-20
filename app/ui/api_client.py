import os
from typing import Any, Optional

import requests

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8080").rstrip("/")


class APIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _detail_text(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        if "message" in detail:
            return str(detail["message"])
        return str(detail)
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                parts.append(item.get("msg") or str(item))
            else:
                parts.append(str(item))
        return "; ".join(parts)
    return str(detail)


def _raise_for_status(response: requests.Response) -> None:
    if response.status_code < 400:
        return
    payload = None
    try:
        payload = response.json()
        message = _detail_text(payload.get("detail", payload))
    except Exception:
        message = response.text or f"HTTP {response.status_code}"
    raise APIError(message, response.status_code, payload)


def _headers(token: Optional[str] = None, json_body: bool = True) -> dict:
    headers = {}
    if json_body:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def api_request(
    method: str,
    path: str,
    token: Optional[str] = None,
    json: Any = None,
    files: Any = None,
    data: Any = None,
    timeout: int = 30,
) -> Any:
    url = f"{API_BASE}{path}"
    try:
        if files is not None or data is not None:
            response = requests.request(
                method,
                url,
                headers=_headers(token, json_body=False),
                files=files,
                data=data,
                timeout=timeout,
            )
        else:
            response = requests.request(
                method,
                url,
                headers=_headers(token, json_body=True),
                json=json,
                timeout=timeout,
            )
    except requests.RequestException as exc:
        raise APIError(f"Backend недоступен: {exc}") from exc
    _raise_for_status(response)
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def signup(username: str, password: str, initial_balance: float = 0.0) -> dict:
    return api_request(
        "POST",
        "/api/users/signup",
        json={
            "username": username,
            "password": password,
            "initial_balance": initial_balance,
            "role": "user",
        },
    )


def signin(username: str, password: str) -> dict:
    return api_request(
        "POST",
        "/api/users/signin",
        json={"username": username, "password": password},
    )


def me(token: str) -> dict:
    return api_request("GET", "/api/users/me", token=token)


def list_models(token: Optional[str] = None) -> list:
    return api_request("GET", "/api/models/", token=token) or []


def get_balance(token: str, user_id: int) -> dict:
    return api_request("GET", f"/api/balance/{user_id}", token=token)


def top_up(token: str, amount: float, user_id: Optional[int] = None) -> dict:
    payload: dict[str, Any] = {"amount": amount}
    if user_id is not None:
        payload["user_id"] = user_id
    return api_request("POST", "/api/balance/top-up", token=token, json=payload)


def transactions(token: str, user_id: int) -> dict:
    return api_request("GET", f"/api/balance/transactions/{user_id}", token=token)


def all_transactions(token: str) -> dict:
    return api_request("GET", "/api/balance/transactions", token=token)


def list_users(token: str) -> list:
    return api_request("GET", "/api/users/", token=token) or []


def upload_file(token: str, filename: str, content: bytes) -> dict:
    return api_request(
        "POST",
        "/api/predictions/upload",
        token=token,
        files={"file": (filename, content)},
    )


def create_predictions(token: str, model_id: int, items: list[str]) -> dict:
    return api_request(
        "POST",
        "/api/predictions/",
        token=token,
        json={"model_id": model_id, "items": items},
    )


def prediction_history(token: str, user_id: int) -> dict:
    return api_request("GET", f"/api/predictions/history/{user_id}", token=token)


def get_prediction(token: str, task_id: int) -> dict:
    return api_request("GET", f"/api/predictions/{task_id}", token=token)


def list_known_entities(token: str) -> list:
    data = api_request("GET", "/api/known-entities/", token=token) or {}
    return data.get("entities") or []


def list_known_entities_for_detection(token: str) -> list:
    data = api_request("GET", "/api/known-entities/detection-data", token=token) or {}
    return data.get("entities") or []


def add_known_entity(
    token: str,
    name: str,
    entity_type: str,
    filename: str,
    content: bytes,
) -> dict:
    return api_request(
        "POST",
        "/api/known-entities/",
        token=token,
        files={"file": (filename, content)},
        data={"name": name, "entity_type": entity_type},
    )


def delete_known_entity(token: str, entity_id: int) -> None:
    api_request("DELETE", f"/api/known-entities/{entity_id}", token=token)


def log_camera_detection(
    token: str,
    model_id: int,
    mode: str,
    filename: str,
    content: bytes,
    timeout: int = 120,
) -> dict:
    return api_request(
        "POST",
        "/api/predictions/camera",
        token=token,
        files={"file": (filename, content)},
        data={"model_id": str(model_id), "mode": mode},
        timeout=timeout,
    )
