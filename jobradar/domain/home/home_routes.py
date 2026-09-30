from flask import Blueprint, render_template

from ...web.request_scope import container

home_bp = Blueprint("home", __name__)


@home_bp.get("/")
def index():
    return render_template("pages/home.html", page=container().home.page())
