from . import db
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
