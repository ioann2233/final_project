import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.balance import balance_route
from routes.home import home_route
from routes.models import models_route
from routes.prediction import prediction_route
from routes.user import user_route
from ui.context import get_flask_app

logger = logging.getLogger(__name__)

APP_NAME = "ML Service API"
APP_DESCRIPTION = "REST API для ML-сервиса: регистрация, авторизация, баланс, предсказания"
API_VERSION = "1.0.0"


def create_application() -> FastAPI:
    application = FastAPI(
        title=APP_NAME,
        description=APP_DESCRIPTION,
        version=API_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(home_route, tags=["Home"])
    application.include_router(user_route, prefix="/api/users", tags=["Users"])
    application.include_router(balance_route, prefix="/api/balance", tags=["Balance"])
    application.include_router(prediction_route, prefix="/api/predictions", tags=["Predictions"])
    application.include_router(models_route, prefix="/api/models", tags=["Models"])

    return application


app = create_application()


@app.on_event("startup")
def on_startup() -> None:
    try:
        logger.info("Initializing database...")
        flask_app = get_flask_app()
        with flask_app.app_context():
            import models  # noqa: F401

            from extensions import db

            db.create_all()
        logger.info("Application startup completed successfully")
    except Exception as exc:
        logger.error("Startup failed: %s", exc)
        raise


@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("Application shutting down...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info",
    )
