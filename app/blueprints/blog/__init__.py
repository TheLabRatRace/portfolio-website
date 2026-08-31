from flask import Blueprint

blog_bp = Blueprint("blog", __name__)

from app.blueprints.blog import routes  # noqa: E402, F401
