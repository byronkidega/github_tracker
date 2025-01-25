from . import db
from sqlalchemy.sql import func
from cryptography.fernet import Fernet

class Repository(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)
    default_branch = db.Column(db.String(50), nullable=False)
    stars = db.Column(db.Integer, nullable=False, default=0)
    forks = db.Column(db.Integer, nullable=False, default=0)
    open_issues = db.Column(db.Integer, nullable=False, default=0)
    latest_commit_date = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Repository {self.name}>"
    

class Commit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hash = db.Column(db.String(40), unique=True, nullable=False)
    author = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    branch = db.Column(db.String(50), nullable=False)
    repository_id = db.Column(db.Integer, db.ForeignKey('repository.id'), nullable=False)
    repository = db.relationship("Repository", back_populates="commits")

Repository.commits = db.relationship("Commit", back_populates="repository", cascade="all, delete-orphan")



class UserToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    encrypted_token = db.Column(db.String(500), nullable=False)

    @staticmethod
    def encrypt_token(token, key):
        fernet = Fernet(key)
        return fernet.encrypt(token.encode()).decode()

    @staticmethod
    def decrypt_token(encrypted_token, key):
        fernet = Fernet(key)
        return fernet.decrypt(encrypted_token.encode()).decode()
