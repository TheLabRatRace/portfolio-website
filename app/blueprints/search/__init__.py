from flask import Blueprint

search_bp = Blueprint("search", __name__, template_folder="../../templates/search")

from app.blueprints.search import routes  # noqa: E402, F401
