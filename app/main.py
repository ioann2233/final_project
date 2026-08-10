from flask import Flask

from config import Config
from extensions import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    import models  # noqa: F401

    from flask_routes import bp
    app.register_blueprint(bp)

    @app.cli.command("init-db")
    def init_db_command():
        from database.database import init_db
        init_db(app, drop_all=False)
        print("Таблицы созданы.")

    @app.cli.command("seed-db")
    def seed_db_command():
        from seed import seed_database
        seed_database(drop_all=True)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
