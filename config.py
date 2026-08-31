import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).parent


# Keys that are published, guessable, or simply absent. Flask signs the
# session cookie with SECRET_KEY, so anyone holding it can mint a cookie that
# says "logged in as user 1, is_admin" -- the admin login is then decorative.
# This repository is public, which is what turns a committed default from a
# bad habit into a working bypass.
INSECURE_SECRET_KEYS = frozenset({
    "",
    "dev-secret-change-in-production",
    "dev-only-never-in-production",
    "change-me-to-a-long-random-string",
    "change-me",
    "secret",
})


def assert_secret_key_is_safe(config_name, secret_key):
    """Refuse to start a production app on a key an attacker already knows.

    Loud at boot rather than quiet forever: a weak key breaks nothing visible,
    so nothing ever surfaces it. The one moment it can be caught is here.
    """
    if config_name != "production":
        return
    if (secret_key or "").strip() in INSECURE_SECRET_KEYS:
        raise RuntimeError(
            "SECRET_KEY is unset or is a known placeholder, and this is a "
            "production config. Flask signs session cookies with it, so a "
            "known value lets anyone forge an admin session without a "
            "password. Generate one and put it in the environment:\n\n"
            "    python3 -c \"import secrets; "
            "print('SECRET_KEY=' + secrets.token_urlsafe(48))\" >> .env\n"
        )


# Hosts that are only reachable from inside the box or the compose network.
# The local stack runs with FLASK_ENV=production, so `db` -- the compose
# service name -- has to count as local or nothing starts.
LOCAL_DB_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "db", "postgres"})


def assert_database_url_is_safe(config_name, database_uri):
    """Refuse to talk to a remote database without proving who answered.

    `sslmode=require` encrypts the connection and validates nothing: any host
    that can win the DNS or routing race presents its own certificate and is
    handed the credentials. Only `verify-full` checks the chain *and* the
    hostname, and it needs a trust store to check against. The RDS instance
    holds every row the site has, so this is a boot condition, not advice.
    """
    if config_name != "production":
        return

    parsed = urlsplit(database_uri or "")
    host = (parsed.hostname or "").lower()
    if not host or host in LOCAL_DB_HOSTS:
        return

    query = parse_qs(parsed.query)
    sslmode = (query.get("sslmode") or [""])[0]
    sslrootcert = (query.get("sslrootcert") or [""])[0]
    if sslmode == "verify-full" and sslrootcert:
        return

    raise RuntimeError(
        f"DATABASE_URL points at the remote host {host!r} without "
        "sslmode=verify-full and an sslrootcert, and this is a production "
        "config. Anything weaker encrypts the wire without proving the "
        "server is the database, so an impostor collects the password. "
        "Append to the URL:\n\n"
        "    ?sslmode=verify-full&sslrootcert=/app/certs/global-bundle.pem\n\n"
        "The bundle is AWS's published CA list, committed at "
        "certs/global-bundle.pem.\n"
    )


def assert_test_database_is_local(config_name, database_uri):
    """Keep the suite off the real database now that RDS is the default.

    Fixtures roll their writes back, but that is a convention, not a wall: a
    test that opens its own engine, a run killed mid-transaction, or any DDL
    escapes it. The wall is here -- the testing config resolves its own
    TEST_DATABASE_URL, and pointing it at a remote host is refused outright.
    """
    if config_name != "testing":
        return

    host = (urlsplit(database_uri or "").hostname or "").lower()
    if not host or host in LOCAL_DB_HOSTS:
        return

    raise RuntimeError(
        f"TEST_DATABASE_URL points at the remote host {host!r}. The suite "
        "writes rows, drops nothing, and is not something to aim at the "
        "database the site serves from. Point it at the local Postgres "
        "instead, or unset it to take the default:\n\n"
        "    postgresql://postgres:<password>@db:5432/postgres\n"
    )


class Config:
    # No fallback on purpose. A default here is a default in production, and
    # this file is committed. Development and testing name their own below;
    # production has to be given one or it will not boot.
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    LOG_DIR = BASE_DIR / "logs"
    PORT = int(os.environ.get("PORT", 5002))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:mysecretpassword@localhost:5432/postgres",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Which half of the site this process serves ──
    # "public" registers the site blueprints and no admin; "admin" registers
    # the admin blueprint and nothing else; "all" is both, which is what local
    # development and the test suite want. In AWS the two roles are two ECS
    # services running the same image, so the public container has no /admin
    # routes at all -- not hidden behind a login, absent.
    APP_ROLE = os.environ.get("APP_ROLE", "all")

    # Where the public site lives, as seen from the outside. The admin app runs
    # on a different host from the public one, so it cannot build a link to a
    # published page with url_for -- it has no public routes to build from.
    # Empty means "no public site known", and the admin templates drop the
    # outbound links rather than emitting a broken href.
    PUBLIC_SITE_URL = os.environ.get("PUBLIC_SITE_URL", "").rstrip("/")

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

    # ── Running behind a reverse proxy (CloudFront, an ALB, nginx) ──
    # The number of proxies that prepend to X-Forwarded-For before a request
    # reaches gunicorn. One CloudFront distribution in front of the container
    # is 1. Zero -- the default -- means the headers are not trusted at all,
    # which is the only safe reading while the app is directly reachable:
    # otherwise any caller names their own client IP and their own scheme, and
    # the log, the rate limiter and every generated https:// URL believe them.
    TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS", "0"))

    # On ECS the container filesystem dies with the task and nobody ever reads
    # the rotated files, so the file handler is write cost with no reader.
    # stdout is what the awslogs driver collects.
    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT", "").lower() in (
        "1", "true", "yes",
    )

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
    # A fixed key so a restart does not sign you out mid-session. Safe only
    # because production refuses to boot on it -- see assert_secret_key_is_safe.
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-never-in-production"


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    SECRET_KEY = "testing-only-never-in-production"

    # Pinned, not inherited: the suite covers both halves of the site, and a
    # developer shelling into the admin container with APP_ROLE=admin exported
    # would otherwise watch every public test 404. Tests that want one role in
    # isolation pass role= to create_app.
    APP_ROLE = "all"

    # Its own variable, deliberately not DATABASE_URL. That one now names RDS
    # by default, and the suite must never be one stray `pytest` away from
    # writing to it. assert_test_database_is_local refuses a remote host here.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://postgres:mysecretpassword@db:5432/postgres",
    )
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
    # SECRET_KEY is inherited from Config -- environment or nothing.
    # create_app() calls assert_secret_key_is_safe() and refuses to build an
    # app on a key that is empty or published.


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
