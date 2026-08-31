"""Where the page tells a browser to fetch CSS, JS and images from.

Two answers, and the templates must not know which one is in force: this
process when STATIC_BASE_URL is empty, the CDN in front of the static bucket
when it is set. The tests below pin both, and pin that flipping the config is
all it takes to move between them.
"""

import pytest

from app.services import resolve

CDN = "https://d111111abcdef8.cloudfront.net"


@pytest.fixture
def static_url(app):
    return app.jinja_env.globals["static_url"]


# ── serving our own assets ───────────────────────────────────────────────────

def test_falls_back_to_flasks_own_static_route(app, static_url):
    with app.test_request_context():
        assert static_url("js/main.js") == "/static/js/main.js"


def test_cache_bust_appends_a_content_digest(app, static_url):
    with app.test_request_context():
        url = static_url("js/main.js", cache_bust=True)
    assert url.startswith("/static/js/main.js?v=")
    assert len(url.rsplit("=", 1)[1]) == 8


def test_a_missing_file_still_yields_a_url(app, static_url):
    """Broken either way -- but a broken <img> beats a 500 on the whole page."""
    with app.test_request_context():
        assert static_url("js/nope.js", cache_bust=True) == "/static/js/nope.js"


# ── serving them from the edge ───────────────────────────────────────────────

def test_base_url_wins_and_needs_no_request_context(app, static_url):
    app.config["STATIC_BASE_URL"] = CDN
    # No test_request_context: outside a request url_for cannot build a static
    # path at all, and the CDN branch must not need one. This is what makes the
    # URL usable from a CLI command or a background job.
    assert static_url("css/style.css") == f"{CDN}/css/style.css"


def test_base_url_keeps_the_digest(app, static_url):
    app.config["STATIC_BASE_URL"] = CDN
    url = static_url("js/main.js", cache_bust=True)
    assert url.startswith(f"{CDN}/js/main.js?v=")


def test_leading_slash_does_not_double_up(app, static_url):
    app.config["STATIC_BASE_URL"] = CDN + "/"
    assert static_url("/js/main.js") == f"{CDN}/js/main.js"


# ── the callers ──────────────────────────────────────────────────────────────

def test_stylesheet_follows_the_base_url(app):
    app.config["STATIC_BASE_URL"] = CDN
    url = app.jinja_env.globals["stylesheet_url"]()
    assert url.startswith(f"{CDN}/css/style")
    assert "?v=" in url


def test_stored_image_paths_follow_the_base_url(app):
    """resolve() is Python, not a template, and reaches static_url through
    app.extensions. If that wiring breaks, images stay on the origin while
    everything else moves -- which nothing else here would catch."""
    app.config["STATIC_BASE_URL"] = CDN
    assert resolve("gallery/shot.webp") == f"{CDN}/images/gallery/shot.webp"


def test_s3_uris_are_not_touched_by_the_static_base_url(app):
    """The assets bucket and the static bucket are different things."""
    app.config["STATIC_BASE_URL"] = CDN
    app.config["S3_PUBLIC_BASE_URL"] = "https://assets.example"
    assert resolve("s3:uploads/a.webp") == "https://assets.example/uploads/a.webp"


def test_rendered_pages_point_at_the_edge(app, client):
    app.config["STATIC_BASE_URL"] = CDN
    html = client.get("/").get_data(as_text=True)
    assert f'href="{CDN}/css/style' in html
    assert f'src="{CDN}/js/main.js?v=' in html
    assert "/static/" not in html


def test_testing_config_pins_the_base_url_empty(app):
    """An exported STATIC_BASE_URL must not rewrite every URL the suite asserts on."""
    assert app.config["STATIC_BASE_URL"] == ""
