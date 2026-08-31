"""The JSON API.

What these tests hold down is the contract a static shell depends on: that
unpublished rows never appear, that collections answer with an envelope rather
than a bare array, that an error under /api is JSON rather than an HTML page a
fetch() cannot read, and that CORS is opt-in.
"""

import json
from datetime import date

import pytest

from app import create_app
from app.models import Post, Project, Tag


@pytest.fixture
def seeded(db_session):
    """Two projects and two posts, one of each unpublished."""
    rows = [
        Project(
            type="work", title="Visible work", slug="api-visible-work",
            description="d", published=True, display_order=1,
        ),
        Project(
            type="work", title="Draft work", slug="api-draft-work",
            description="d", published=False, display_order=2,
        ),
        Post(
            title="Visible post", slug="api-visible-post", content="body",
            excerpt="e", published=True, date=date(2026, 1, 2),
        ),
        Post(
            title="Draft post", slug="api-draft-post", content="body",
            excerpt="e", published=False, date=date(2026, 1, 3),
        ),
    ]
    db_session.add_all(rows)
    db_session.flush()
    return rows


def _json(response):
    assert response.status_code == 200, response.data[:400]
    assert response.mimetype == "application/json"
    return json.loads(response.data)


@pytest.mark.parametrize(
    "path", ["/api/v1/projects", "/api/v1/posts", "/api/v1/gallery"]
)
def test_collections_answer_with_an_envelope(client, seeded, path):
    """An object, not a bare array. A top-level JSON array cannot grow a field
    later without breaking every client that already reads it."""
    body = _json(client.get(path))
    assert isinstance(body["items"], list)
    for key in ("page", "per_page", "pages", "total"):
        assert key in body


def test_projects_omits_unpublished(client, seeded):
    slugs = [p["slug"] for p in _json(client.get("/api/v1/projects"))["items"]]
    assert "api-visible-work" in slugs
    assert "api-draft-work" not in slugs


def test_posts_omits_unpublished(client, seeded):
    slugs = [p["slug"] for p in _json(client.get("/api/v1/posts"))["items"]]
    assert "api-visible-post" in slugs
    assert "api-draft-post" not in slugs


def test_an_unpublished_row_is_a_404_not_a_403(client, seeded):
    """403 would confirm the slug exists. A draft should be indistinguishable
    from a slug that was never used."""
    assert client.get("/api/v1/projects/api-draft-work").status_code == 404
    assert client.get("/api/v1/posts/api-draft-post").status_code == 404


def test_project_detail_carries_the_collections_the_list_omits(client, seeded):
    body = _json(client.get("/api/v1/projects/api-visible-work"))
    assert body["slug"] == "api-visible-work"
    for key in ("gallery", "documents", "downloads", "specs", "long_description"):
        assert key in body


def test_detail_url_matches_the_public_route(client, seeded):
    body = _json(client.get("/api/v1/projects/api-visible-work"))
    assert body["url"] == "/projects/api-visible-work"


def test_per_page_is_capped(client, seeded):
    """An uncapped per_page is a way to ask for the whole table in one query."""
    body = _json(client.get("/api/v1/projects?per_page=100000"))
    assert body["per_page"] == 100


def test_type_filter(client, seeded):
    body = _json(client.get("/api/v1/projects?type=sidequest"))
    assert all(p["type"] == "sidequest" for p in body["items"])


def test_tag_filter(client, db_session, seeded):
    project = next(r for r in seeded if getattr(r, "slug", "") == "api-visible-work")
    tag = Tag(name="api-tag", slug="api-tag")
    db_session.add(tag)
    project._tags.append(tag)
    db_session.flush()

    body = _json(client.get("/api/v1/projects?tag=api-tag"))
    assert [p["slug"] for p in body["items"]] == ["api-visible-work"]


def test_home_carries_skills_and_certifications(client, db_session):
    body = _json(client.get("/api/v1/home"))
    assert isinstance(body["skills"], list)
    assert isinstance(body["certifications"], list)


def test_search_groups_by_type(client, seeded):
    body = _json(client.get("/api/v1/search?q=visible"))
    assert set(body["results"]) == {"work", "sidequests", "gallery", "posts", "tags"}
    assert body["q"] == "visible"


def test_search_reports_its_group_cap(client, seeded):
    """The static shell shows a "see all" link on a group that came back full.
    Without the cap in the response it would have to hardcode the number and
    quietly stop offering the link the day the server's changed."""
    from app.services.search import LIMIT

    body = _json(client.get("/api/v1/search?q=visible"))
    assert body["limit"] == LIMIT


def test_a_one_letter_search_is_reported_not_ranked(client, seeded):
    body = _json(client.get("/api/v1/search?q=a"))
    assert body["too_short"] is True
    assert body["total"] == 0


def test_a_missing_route_under_api_is_json(client):
    """Keyed on the path, not on Accept: a fetch() sends Accept: */*, so
    content negotiation would hand a JavaScript client an HTML error page."""
    response = client.get("/api/v1/nothing-here")
    assert response.status_code == 404
    assert response.mimetype == "application/json"
    assert json.loads(response.data)["error"] == "not_found"


def test_a_missing_route_outside_api_is_still_html(client):
    response = client.get("/nothing-here")
    assert response.status_code == 404
    assert response.mimetype == "text/html"


def test_no_cors_header_without_an_allowlist(client, seeded):
    """Empty by default. A wildcard would be harmless while everything here is
    public and read-only, and exactly wrong the first time it is not."""
    response = client.get("/api/v1/projects", headers={"Origin": "https://evil.test"})
    assert "Access-Control-Allow-Origin" not in response.headers


def test_an_allowlisted_origin_is_echoed(db_session):
    app = create_app("testing")
    app.config["API_CORS_ORIGINS"] = ("https://shell.test",)
    with app.app_context():
        response = app.test_client().get(
            "/api/v1/projects", headers={"Origin": "https://shell.test"}
        )
    assert response.headers["Access-Control-Allow-Origin"] == "https://shell.test"
    assert "Origin" in response.headers["Vary"]


def test_an_unlisted_origin_is_not_echoed(db_session):
    app = create_app("testing")
    app.config["API_CORS_ORIGINS"] = ("https://shell.test",)
    with app.app_context():
        response = app.test_client().get(
            "/api/v1/projects", headers={"Origin": "https://evil.test"}
        )
    assert "Access-Control-Allow-Origin" not in response.headers


def test_the_admin_app_serves_no_api(db_session):
    """The API is the public site's JSON view. The admin process has no
    business answering it, and does not register it."""
    app = create_app("testing", role="admin")
    with app.app_context():
        assert app.test_client().get("/api/v1/projects").status_code == 404
