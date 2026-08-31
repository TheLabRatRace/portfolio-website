"""Sign-in: the credential check, the session, and the redirect."""

import pytest

from app.models import User


def test_login_page_renders(client):
    assert client.get("/admin/login").status_code == 200


def test_wrong_password_is_rejected(client, admin_user):
    response = client.post(
        "/admin/login",
        data={"username": admin_user.username, "password": "not the password"},
    )
    # A re-rendered form, not a redirect: no session was issued.
    assert response.status_code == 200
    assert client.get("/admin/").status_code == 302


def test_unknown_user_is_rejected(client, db_session):
    response = client.post(
        "/admin/login", data={"username": "nobody-at-all", "password": "x"}
    )
    assert response.status_code == 200


def test_failure_message_does_not_reveal_which_half_was_wrong(client, admin_user):
    """Both failures must read identically, or the form is a username oracle."""
    unknown = client.post(
        "/admin/login", data={"username": "nobody-at-all", "password": "x"}
    ).get_data(as_text=True)
    bad_password = client.post(
        "/admin/login", data={"username": admin_user.username, "password": "x"}
    ).get_data(as_text=True)
    assert "Wrong username or password." in unknown
    assert "Wrong username or password." in bad_password


def test_login_succeeds_and_reaches_the_dashboard(as_admin):
    assert as_admin.get("/admin/").status_code == 200


def test_login_stamps_last_login(as_admin, admin_user, db_session):
    db_session.refresh(admin_user)
    assert admin_user.last_login_at is not None


def test_logout_ends_the_session(as_admin):
    assert as_admin.post("/admin/logout").status_code == 302
    assert as_admin.get("/admin/").status_code == 302


def test_password_is_not_stored_in_the_clear(admin_user):
    assert admin_user.password_hash != "correct horse battery staple"
    assert admin_user.check_password("correct horse battery staple")
    assert not admin_user.check_password("correct horse battery stapl")


@pytest.mark.parametrize("target", [
    "https://evil.example/phish",
    "//evil.example/phish",
    "http://evil.example",
])
def test_next_cannot_leave_the_site(client, admin_user, target):
    """An open redirect here would make the login page a credible phish."""
    response = client.post(
        f"/admin/login?next={target}",
        data={"username": admin_user.username,
              "password": "correct horse battery staple"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/admin/"


def test_next_is_honoured_for_a_local_path(client, admin_user):
    response = client.post(
        "/admin/login?next=/admin/posts",
        data={"username": admin_user.username,
              "password": "correct horse battery staple"},
    )
    assert response.headers["Location"] == "/admin/posts"


def test_signed_in_admin_skips_the_login_page(as_admin):
    assert as_admin.get("/admin/login").status_code == 302


def test_csrf_is_enforced_when_enabled(app, admin_user):
    """TestingConfig disables CSRF so the other tests can post forms.

    This one turns it back on, because a protection that is only ever
    switched off in tests is a protection nobody has tested.
    """
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        client = app.test_client()
        response = client.post(
            "/admin/login",
            data={"username": admin_user.username,
                  "password": "correct horse battery staple"},
        )
        # CSRFProtect rejects the request outright rather than re-rendering.
        assert response.status_code == 400
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_user_loader_round_trips(app, admin_user):
    assert app.login_manager._user_callback(str(admin_user.id)) is not None


def test_user_loader_survives_a_junk_cookie(app):
    """A tampered or stale cookie must be a signed-out visitor, not a 500."""
    assert app.login_manager._user_callback("not-an-integer") is None
    assert app.login_manager._user_callback(str(2**40)) is None


def test_no_second_user_shares_a_username(db_session, admin_user):
    assert User.query.filter_by(username=admin_user.username).count() == 1
