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

    # ── Asset storage ──
    # S3_BUCKET is the switch. Set, uploads go to the bucket and the database
    # stores `s3:<key>`; unset -- a fresh checkout, CI, a test run -- uploads
    # go to static/images/uploads/ and everything works without an AWS account.
    #
    # NO CREDENTIAL IS READ HERE. boto3 finds them by its own chain
    # (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, ~/.aws, an instance role),
    # which is why this file can be committed and .env cannot.
    S3_BUCKET = os.environ.get("S3_BUCKET", "")
    S3_REGION = os.environ.get("S3_REGION", "us-east-2")
    # For a local S3 stand-in (MinIO, LocalStack). Empty means real AWS.
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "")

    # Where a visitor's browser fetches an object from: a CloudFront domain,
    # or the bucket's own URL if it allows anonymous reads. Unset means the
    # bucket is private and every URL gets presigned -- correct, but unique
    # per request, so nothing downstream can cache it.
    S3_PUBLIC_BASE_URL = os.environ.get("S3_PUBLIC_BASE_URL", "").rstrip("/")
    S3_URL_EXPIRY_SECONDS = int(os.environ.get("S3_URL_EXPIRY_SECONDS", 3600))

    # Only meaningful on a bucket with ACLs enabled; new buckets have them
    # disabled and reject the header, so this is empty unless you know
    # otherwise. Prefer a bucket policy or CloudFront over per-object ACLs.
    S3_OBJECT_ACL = os.environ.get("S3_OBJECT_ACL", "")

    # A key's bytes never change -- a new upload gets a new key -- so the only
    # reason to revalidate is a deletion, and a deleted asset is a broken page
    # either way.
    S3_CACHE_CONTROL = os.environ.get(
        "S3_CACHE_CONTROL", "public, max-age=31536000, immutable"
    )

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

    # Pinned, not inherited. A developer with S3_BUCKET exported would
    # otherwise have the suite upload to a real bucket; the S3 path is covered
    # by tests that stub the client instead.
    S3_BUCKET = ""
    S3_PUBLIC_BASE_URL = ""


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
