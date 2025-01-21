import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = "It,slm@143"
SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'github_tracker.db')}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'your_email@gmail.com'
MAIL_PASSWORD = 'your_password'
