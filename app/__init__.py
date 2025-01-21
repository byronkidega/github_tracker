from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail

db = SQLAlchemy()
mail = Mail()

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('../instance/config.py')
    db.init_app(app)
    mail.init_app(app)

    # Import and register blueprints here
    from .routes import routes
    app.register_blueprint(routes, url_prefix='/auth')

    with app.app_context():
        from . import routes
        db.create_all()

    return app
