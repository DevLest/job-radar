from flask import Blueprint, render_template

from ...web.request_scope import container

usage_bp = Blueprint("usage", __name__, url_prefix="/usage")


@usage_bp.get("")
def page():
    return render_template("pages/usage.html", page=container().usage_service.page())
