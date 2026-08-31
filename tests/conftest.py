"""Shared fixtures.

The tests run against a real Postgres, not SQLite: the search they exercise is
a generated tsvector with a GIN index and websearch_to_tsquery behind it, none
of which SQLite has.

So they point at whatever DATABASE_URL points at -- a service container in CI,
the dev database locally -- and no test may leave a row behind: `db_session`
runs each test in a transaction that is always rolled back.
"""

import uuid

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import User


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        yield app


@pytest.fixture
def db_session(app):
    """Give a test a session whose writes are discarded when it ends.

    A connection holds an outer transaction that is never committed, and the
    session runs inside it. `create_savepoint` turns the session's own
    commit() into a SAVEPOINT release rather than a real COMMIT -- which
    matters because every admin view under test calls commit() itself.

    Binding it takes two steps, not one. Flask-SQLAlchemy 3.1 subclasses
    Session and overrides get_bind() to look the engine up in `db.engines`,
    so a bind passed to session.configure() is silently ignored and the
    session keeps writing to the real database -- a green suite that leaves
    rows behind. Swapping the entry in `db.engines` is what actually
    redirects it; configure() is only there for join_transaction_mode.
    """
    connection = _db.engine.connect()
    transaction = connection.begin()

    engines = _db.engines
    original = engines[None]
    engines[None] = connection

    _db.session.remove()
    _db.session.configure(join_transaction_mode="create_savepoint")

    yield _db.session

    _db.session.remove()
    _db.session.configure(join_transaction_mode="conditional_savepoint")
    engines[None] = original
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(app):
    return app.test_client()


def _make_user(db_session, *, is_admin):
    """A user with a name nothing else can collide with, so a crashed test that
    escapes the rollback cannot poison later runs with a duplicate username.
    """
    user = User(username=f"t-{uuid.uuid4().hex[:12]}", is_admin=is_admin)
    user.set_password("correct horse battery staple")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def admin_user(db_session):
    return _make_user(db_session, is_admin=True)


@pytest.fixture
def plain_user(db_session):
    """Authenticated but not an admin -- the case that must get a 403."""
    return _make_user(db_session, is_admin=False)


@pytest.fixture
def as_admin(client, admin_user):
    """A client that has already signed in, by the real login POST rather than
    by writing to the session -- so the form, the check and the cookie are
    exercised too.
    """
    response = client.post(
        "/admin/login",
        data={"username": admin_user.username,
              "password": "correct horse battery staple"},
        follow_redirects=False,
    )
    assert response.status_code == 302, "login should redirect, not re-render"
    return client
