from . import db

class Repository(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    default_branch = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)

class Commit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    repository_id = db.Column(db.Integer, db.ForeignKey('repository.id'))
