import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bootstrap import Bootstrap
from pathlib import Path
from os import path



db = SQLAlchemy()
DB_NAME = "github_tracker.db"
migrate = Migrate()
bootstrap = Bootstrap()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'It,slm@143'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize the extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    bootstrap.init_app(app)

    # Register blueprints
    from . import routes
    app.register_blueprint(routes.bp)

    return app

def create_database(app):
    db_path = os.path.join('app/', DB_NAME)
    if not path.exists(db_path):
        with app.app_context():
            db.create_all()