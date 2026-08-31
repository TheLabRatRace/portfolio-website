"""The public/admin split.

The public container and the admin container run the same image and differ
only by APP_ROLE. What these tests defend is that the separation is real --
that the public process has no admin routes to find, not merely admin routes
behind a login -- and that neither half renders a template that reaches for an
endpoint the other half owns.
"""

import pytest
from flask import render_template, url_for

from app import create_app
from app.models import Post, Project

PUBLIC_PATHS = ["/", "/contact", "/blog/", "/projects/", "/search"]
ADMIN_PATHS = ["/admin/", "/admin/login", "/admin/posts", "/admin/projects"]


@pytest.fixture
def public_app():
    app = create_app("testing", role="public")
    with app.app_context():
        yield app


@pytest.fixture
def admin_app():
    app = create_app("testing", role="admin")
    with app.app_context():
        yield app


def test_bad_role_is_rejected():
    with pytest.raises(ValueError):
        create_app("testing", role="publick")


@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_public_app_has_no_admin_routes(public_app, path):
    """404, not 302-to-login. The route does not exist in this process."""
    assert public_app.test_client().get(path).status_code == 404


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_admin_app_has_no_public_routes(admin_app, path):
    assert admin_app.test_client().get(path).status_code == 404


def test_admin_app_serves_its_login_page(admin_app, db_session):
    """The template that used to extend the public base. If it still did, this
    would be a BuildError on main.home rather than a form."""
    response = admin_app.test_client().get("/admin/login")
    assert response.status_code == 200
    assert b"admin-login-form" in response.data


def test_admin_app_renders_404_without_a_public_nav(admin_app):
    """errors/404.html picks its skeleton by role. Getting that wrong turns
    every admin 404 into a 500, which is exactly the sort of thing that only
    shows up in production."""
    response = admin_app.test_client().get("/admin/nothing-here")
    assert response.status_code == 404


def test_public_app_still_serves_the_site(public_app, db_session):
    for path in PUBLIC_PATHS:
        assert public_app.test_client().get(path).status_code == 200


def test_default_role_registers_both(app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "main.home" in endpoints
    assert "admin.login" in endpoints


def test_public_paths_match_the_real_routes(app, db_session):
    """Project.public_path and Post.public_path are hand-written because the
    admin app has no public endpoints to build from. This is the lock that
    stops them drifting from the routes they duplicate."""
    project = Project(title="T", slug="a-slug", type="work")
    post = Post(title="T", slug="b-slug", date="2026-01-01")
    with app.test_request_context():
        assert project.public_path == url_for("projects.detail", slug=project.slug)
        assert post.public_path == url_for("blog.detail", slug=post.slug)


def test_public_url_is_absolute_when_configured(admin_app):
    admin_app.config["PUBLIC_SITE_URL"] = "https://example.test"
    with admin_app.test_request_context():
        rendered = render_template("admin/_shell.html")
    assert "https://example.test" in rendered


def test_public_url_is_empty_for_an_admin_app_with_no_public_site(admin_app):
    """No PUBLIC_SITE_URL and no public routes: there is no address to link
    to, and the templates must drop the link rather than emit a broken one."""
    admin_app.config["PUBLIC_SITE_URL"] = ""
    with admin_app.test_request_context():
        assert admin_app.jinja_env.globals["public_url"]("/blog/x") == ""
