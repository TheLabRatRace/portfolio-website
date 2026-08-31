"""The session cookie is the admin boundary, so its key is a boot condition.

Flask signs the session with SECRET_KEY. Anyone holding that value can forge
a cookie asserting any user id and `is_admin`, which walks straight past
`require_login` -- no password, nothing to brute-force. This repository is
public, so a committed default is not a bad habit, it is a working bypass.
These tests exist to make that impossible to reintroduce.
"""

from pathlib import Path

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
