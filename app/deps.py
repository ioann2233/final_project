from ui.context import get_flask_app


def flask_context():
    """FastAPI dependency: Flask app context для SQLAlchemy-сессии."""
    with get_flask_app().app_context():
        yield
