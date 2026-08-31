"""The endpoints and middleware that exist for the platform, not the visitor.

Nothing here renders a page. These are the two things ECS and CloudFront rely
on -- a health check that survives a database outage, and forwarded headers
that are trusted only where something trustworthy set them -- and both fail
silently when broken: a health check that quietly starts querying the database
still returns 200 until the day RDS blinks and ECS kills the site.
"""

from flask import request
from sqlalchemy import event
from werkzeug.middleware.proxy_fix import ProxyFix

from app import _setup_proxy_fix
from app.extensions import db


def test_healthz_is_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    # A cached health check reports the state of whichever task answered first.
    assert response.headers["Cache-Control"] == "no-store"


def test_healthz_issues_no_queries(app, client):
    """The whole reason the endpoint exists.

    ECS restarts a task whose health check fails. If this one touched the
    database, an RDS failover would be reported as a broken container and ECS
    would spend the outage killing tasks.
    """
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    engine = db.engines[None]
    event.listen(engine, "before_cursor_execute", record)
    try:
        assert client.get("/healthz").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert statements == [], f"/healthz queried the database: {statements}"


def test_forwarded_headers_are_ignored_by_default(app, client):
    """Directly reachable app, so the header is just something a caller typed."""
    assert not isinstance(app.wsgi_app, ProxyFix)

    @app.route("/_whoami")
    def whoami():
        return {"ip": request.remote_addr, "scheme": request.scheme}

    body = client.get(
        "/_whoami",
        headers={"X-Forwarded-For": "203.0.113.7", "X-Forwarded-Proto": "https"},
    ).get_json()
    assert body["ip"] != "203.0.113.7"
    assert body["scheme"] == "http"


def test_forwarded_headers_are_read_when_a_proxy_is_declared(app, client):
    app.config["TRUSTED_PROXY_HOPS"] = 1
    _setup_proxy_fix(app)

    @app.route("/_whoami")
    def whoami():
        return {"ip": request.remote_addr, "scheme": request.scheme}

    body = client.get(
        "/_whoami",
        headers={"X-Forwarded-For": "203.0.113.7", "X-Forwarded-Proto": "https"},
    ).get_json()
    assert body == {"ip": "203.0.113.7", "scheme": "https"}
