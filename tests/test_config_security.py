"""The session cookie is the admin boundary, so its key is a boot condition.

Flask signs the session with SECRET_KEY. Anyone holding that value can forge
a cookie asserting any user id and `is_admin`, which walks straight past
`require_login` -- no password, nothing to brute-force. This repository is
public, so a committed default is not a bad habit, it is a working bypass.
These tests exist to make that impossible to reintroduce.
"""

import importlib
from pathlib import Path
from urllib.parse import urlsplit

import pytest

import config as config_module
from app import create_app
from config import INSECURE_SECRET_KEYS, ProductionConfig, assert_secret_key_is_safe


def test_no_committed_default_for_the_base_config():
    """The base Config must not name a fallback key in committed source.

    Asserted against the file's text rather than the loaded value: importing
    config.py runs load_dotenv(), so on any machine that has a real .env the
    attribute is populated and a value check would pass no matter what the
    source said. The source is the part that is public.
    """
    source = Path(config_module.__file__).read_text()
    body = source[source.index("class Config:"):source.index("class DevelopmentConfig")]
    line = next(ln for ln in body.splitlines() if ln.strip().startswith("SECRET_KEY"))
    assert line.strip() == 'SECRET_KEY = os.environ.get("SECRET_KEY", "")', (
        f"base Config must have no fallback secret, found: {line.strip()}"
    )


@pytest.mark.parametrize("key", sorted(INSECURE_SECRET_KEYS))
def test_production_refuses_every_known_bad_key(key):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        assert_secret_key_is_safe("production", key)


def test_production_refuses_none_and_whitespace():
    for key in (None, "   ", "\t"):
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            assert_secret_key_is_safe("production", key)


def test_production_accepts_a_real_key():
    assert_secret_key_is_safe("production", "Zx4-a-genuinely-random-48-byte-value")


def test_development_is_not_gated():
    """A placeholder is fine on localhost; blocking it would only teach people
    to export a real key into a shell that also runs the tests.
    """
    assert_secret_key_is_safe("development", "dev-only-never-in-production")
    assert_secret_key_is_safe("testing", "")


def test_create_app_production_fails_closed(monkeypatch):
    """The guard is wired into create_app, not merely available to it."""
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "", raising=False)
    with pytest.raises(RuntimeError, match="forge an admin session"):
        create_app("production")


def test_the_error_says_how_to_fix_it():
    """A refusal that does not say what to do gets worked around, not fixed."""
    with pytest.raises(RuntimeError) as exc:
        assert_secret_key_is_safe("production", "")
    message = str(exc.value)
    assert "token_urlsafe" in message
    assert ".env" in message


def test_env_example_ships_a_placeholder_not_a_usable_key():
    """.env.example is committed, so whatever is in it is public by definition."""
    text = Path(__file__).resolve().parent.parent.joinpath(".env.example").read_text()
    line = next(ln for ln in text.splitlines() if ln.startswith("SECRET_KEY="))
    assert line.split("=", 1)[1].strip() in INSECURE_SECRET_KEYS, (
        "a real-looking key in .env.example would be copied into a deployment"
    )


# ── DATABASE_URL: TLS is a boot condition for a remote database ─────────────
#
# The RDS instance is reachable from outside the VPC, so the only thing
# standing between the app's password and anyone who can answer for that
# hostname is certificate validation. `require` does not do it; `verify-full`
# does. These lock the distinction in place.

RDS_HOST = "example.abcdefghijkl.us-east-2.rds.amazonaws.com"
VERIFIED = (
    f"postgresql://app:pw@{RDS_HOST}:5432/portfolio"
    "?sslmode=verify-full&sslrootcert=/app/certs/global-bundle.pem"
)


@pytest.mark.parametrize(
    "uri",
    [
        f"postgresql://app:pw@{RDS_HOST}:5432/portfolio",
        f"postgresql://app:pw@{RDS_HOST}:5432/portfolio?sslmode=require",
        f"postgresql://app:pw@{RDS_HOST}:5432/portfolio?sslmode=prefer",
        f"postgresql://app:pw@{RDS_HOST}:5432/portfolio?sslmode=verify-ca",
        # verify-full with nothing to verify against is not verification.
        f"postgresql://app:pw@{RDS_HOST}:5432/portfolio?sslmode=verify-full",
    ],
)
def test_remote_database_without_verify_full_is_refused(uri):
    with pytest.raises(RuntimeError, match="verify-full"):
        config_module.assert_database_url_is_safe("production", uri)


def test_remote_database_with_verify_full_and_a_trust_store_is_accepted():
    config_module.assert_database_url_is_safe("production", VERIFIED)


def test_the_error_never_echoes_the_password():
    with pytest.raises(RuntimeError) as exc:
        config_module.assert_database_url_is_safe(
            "production", f"postgresql://app:hunter2@{RDS_HOST}:5432/portfolio"
        )
    assert "hunter2" not in str(exc.value)
    assert RDS_HOST in str(exc.value)


@pytest.mark.parametrize("host", sorted(config_module.LOCAL_DB_HOSTS))
def test_local_hosts_are_exempt(host):
    """The compose stack runs FLASK_ENV=production against plaintext `db`."""
    config_module.assert_database_url_is_safe(
        "production", f"postgresql://postgres:pw@{host}:5432/postgres"
    )


@pytest.mark.parametrize("config_name", ["development", "testing"])
def test_non_production_configs_are_not_gated(config_name):
    config_module.assert_database_url_is_safe(
        config_name, f"postgresql://app:pw@{RDS_HOST}:5432/portfolio"
    )


def test_an_unparseable_url_is_not_treated_as_remote():
    """No host means nothing to impersonate; SQLAlchemy will fail on its own."""
    config_module.assert_database_url_is_safe("production", "")
    config_module.assert_database_url_is_safe("production", None)


def test_the_committed_trust_store_is_present_and_is_a_ca_bundle():
    bundle = Path(config_module.__file__).parent / "certs" / "global-bundle.pem"
    assert bundle.is_file(), "certs/global-bundle.pem is what verify-full reads"
    text = bundle.read_text()
    assert text.count("BEGIN CERTIFICATE") > 50
    assert "PRIVATE KEY" not in text, "a trust store holds no keys"


# ── TEST_DATABASE_URL: the suite never aims at the real database ────────────
#
# RDS is what `docker compose up` connects to now, so the distance between
# `pytest` and the rows the site serves is one environment variable. The
# fixtures roll back, but a test that opens its own engine or a run killed
# mid-transaction does not, so the refusal is a wall rather than a habit.


def test_the_testing_config_does_not_follow_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", VERIFIED)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    importlib.reload(config_module)
    try:
        assert RDS_HOST not in config_module.TestingConfig.SQLALCHEMY_DATABASE_URI
        assert "@db:5432" in config_module.TestingConfig.SQLALCHEMY_DATABASE_URI
    finally:
        importlib.reload(config_module)


def test_a_remote_test_database_is_refused():
    with pytest.raises(RuntimeError, match="writes rows"):
        config_module.assert_test_database_is_local("testing", VERIFIED)


@pytest.mark.parametrize("host", sorted(config_module.LOCAL_DB_HOSTS))
def test_a_local_test_database_is_accepted(host):
    config_module.assert_test_database_is_local(
        "testing", f"postgresql://postgres:pw@{host}:5432/postgres"
    )


@pytest.mark.parametrize("config_name", ["development", "production"])
def test_only_the_testing_config_is_gated(config_name):
    config_module.assert_test_database_is_local(config_name, VERIFIED)


def test_the_suite_this_assertion_runs_in_is_itself_local(app):
    """Belt and braces: whatever wired this run, it is not the real database."""
    host = urlsplit(app.config["SQLALCHEMY_DATABASE_URI"]).hostname or ""
    assert host.lower() in config_module.LOCAL_DB_HOSTS
