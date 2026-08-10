from typing import Dict

from fastapi import APIRouter

home_route = APIRouter()


@home_route.get(
    "/",
    response_model=Dict[str, str],
    summary="Root endpoint",
    description="Информация о сервисе",
)
async def index() -> Dict[str, str]:
    return {
        "message": "ML Service API",
        "docs": "/api/docs",
        "ui": "Streamlit на порту 8501",
    }


@home_route.get(
    "/health",
    response_model=Dict[str, str],
    summary="Health check",
    description="Проверка доступности сервиса",
)
async def health_check() -> Dict[str, str]:
    return {"status": "healthy"}
