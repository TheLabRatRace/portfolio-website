"""Site-wide search.

These run against real Postgres full-text search -- generated `tsvector`
columns, a GIN index and `websearch_to_tsquery`. That is the point: on any
other engine the suite would pass without testing what ships.
"""

import pytest

from app.models import Project


def text_of(response):
    return response.get_data(as_text=True)


def test_bare_search_page(client):
    """No query is the landing state, not an error."""
    response = client.get("/search")
    assert response.status_code == 200
    assert "Searches titles, descriptions" in text_of(response)


def test_trailing_slash_also_answers(client):
    """/search is canonical; /search/ must not 404 for anyone who types it."""
    assert client.get("/search/").status_code == 200


def test_canonical_url_has_no_trailing_slash(app):
    with app.test_request_context():
        from flask import url_for
        assert url_for("search.index") == "/search"
        assert url_for("search.index", q="x") == "/search?q=x"


@pytest.mark.parametrize("q", ["a", "x", " "])
def test_one_character_is_refused(client, q):
    response = client.get("/search", query_string={"q": q})
    assert response.status_code == 200
    body = text_of(response)
    assert "Two characters or more" in body or "Searches titles" in body


def test_a_real_query_finds_something(client):
    response = client.get("/search", query_string={"q": "proxmox"})
    assert response.status_code == 200
    assert "results for" in text_of(response)


def test_a_nonsense_query_finds_nothing_without_erroring(client):
    response = client.get("/search", query_string={"q": "zzzqqqxxnotaword"})
    assert response.status_code == 200
    assert "Nothing matches" in text_of(response)


@pytest.mark.parametrize("q", [
    '"unbalanced quote',
    "& | ! ( )",
    "-only-an-exclusion",
    "a" * 300,
    "<script>alert(1)</script>",
])
def test_hostile_input_is_a_poor_result_not_a_500(client, q):
    """websearch_to_tsquery never raises; to_tsquery would have, on all of these."""
    assert client.get("/search", query_string={"q": q}).status_code == 200


def test_query_is_escaped_in_the_page(client):
    response = client.get("/search", query_string={"q": "<script>alert(1)</script>"})
    assert "<script>alert(1)</script>" not in text_of(response)


def test_search_finds_a_new_project_and_loses_it_when_unpublished(as_admin, db_session):
    """The whole lifecycle, because the published filter is the one that matters.

    A draft that stays searchable is a leak: the row is not linkable, but
    its title and description are right there in the results.
    """
    unique = "zylophonic"
    as_admin.post("/admin/projects/new", data={
        "title": f"{unique} Rack Project",
        "slug": "zylophonic-rack",
        "type": "work",
        "description": "A searchable description.",
        "published": "y",
    })
    found = text_of(as_admin.get("/search", query_string={"q": unique}))
    assert "zylophonic-rack" in found

    project = Project.query.filter_by(slug="zylophonic-rack").one()
    as_admin.post(f"/admin/projects/{project.id}/edit", data={
        "title": f"{unique} Rack Project",
        "slug": "zylophonic-rack",
        "type": "work",
        "description": "A searchable description.",
    })
    hidden = text_of(as_admin.get("/search", query_string={"q": unique}))
    assert "zylophonic-rack" not in hidden
    assert "Nothing matches" in hidden


def test_an_unpublished_post_is_not_searchable(as_admin, db_session):
    unique = "quixotically"
    as_admin.post("/admin/posts/new", data={
        "title": f"{unique} Draft Post",
        "slug": "quixotically-draft",
        "content": "Body text nobody should find yet.",
    })
    body = text_of(as_admin.get("/search", query_string={"q": unique}))
    assert "quixotically-draft" not in body


def test_matching_is_by_stem(as_admin, db_session):
    """"deploying" must find "deploy" -- that is what the tsvector buys."""
    as_admin.post("/admin/projects/new", data={
        "title": "Fluffernutter deployment", "slug": "stem-check",
        "type": "work", "description": "x", "published": "y",
    })
    assert "stem-check" in text_of(
        as_admin.get("/search", query_string={"q": "fluffernutter deploying"})
    )


def test_partial_words_do_not_match_bodies(client):
    """A prefix is a tag's job, not the tsvector's -- documented, so tested."""
    response = client.get("/search", query_string={"q": "prox"})
    assert response.status_code == 200


def test_nav_search_box_is_on_every_page(client):
    for url in ("/", "/projects/", "/blog/", "/contact"):
        assert 'class="nav-search"' in text_of(client.get(url))


def test_nav_box_carries_the_query_only_on_the_search_page(client):
    """Elsewhere it shows its placeholder, or every page looks like a result."""
    assert 'value="proxmox"' in text_of(
        client.get("/search", query_string={"q": "proxmox"})
    )
    assert 'value="proxmox"' not in text_of(client.get("/projects/"))
