from flask import render_template, request
from . import db
from flask import Blueprint


routes = Blueprint('routes', __name__)

@routes.route("/")
def home():
    return render_template("base.html")
