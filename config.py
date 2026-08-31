import os
from datetime import timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    LOG_DIR = BASE_DIR / "logs"
    PORT = int(os.environ.get("PORT", 5002))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:mysecretpassword@localhost:5432/postgres",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Session cookie ──
    # SameSite=Lax is what actually stops a cross-site POST from riding the
    # admin's session; the CSRF token is the second lock, not the first.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Off by default: local dev is plain http, where a Secure cookie is one the
    # browser silently drops. Set SESSION_COOKIE_SECURE=1 wherever TLS is on.
    SESSION_COOKIE_SECURE = os.environ.get(
        "SESSION_COOKIE_SECURE", ""
    ).lower() in ("1", "true", "yes")

    # An admin session ends when the browser does, unless the box is ticked.
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # Inside static/images, not beside it: the templates render
    # `static/images/<image_path>`, so anywhere else needs its own URL rule.
    UPLOAD_SUBDIR = "uploads"
    UPLOAD_DIR = BASE_DIR / "app" / "static" / "images" / UPLOAD_SUBDIR
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}

    # Set by docker-compose locally. Governs everything that trades a production
    # optimisation for seeing an edit immediately: Jinja's template cache and the
    # static-asset max-age.
    DEV_RELOAD = os.environ.get("DEV_RELOAD", "").lower() in ("1", "true", "yes")

    # Big serif page headings ("Projects", "Blog"). Off pulls the tabs up under
    # the nav and gives the list the whole viewport.
    SHOW_PAGE_TITLE = os.environ.get(
        "SHOW_PAGE_TITLE", "1"
    ).lower() not in ("0", "false", "off", "no")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    # Tests post forms without a browser to fetch a token first. The protection
    # is still exercised: one test turns it back on and asserts the rejection.
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
