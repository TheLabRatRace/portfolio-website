import html
import re
from urllib.parse import parse_qs, urlsplit

def test_home(client):
    assert client.get("/").status_code == 200


def test_home_carries_the_about_content(client):
    """It is the only place the about content lives now, so its absence is a
    silent loss of a whole section rather than a broken page."""
    body = client.get("/").get_data(as_text=True)
    assert 'id="about"' in body
    assert "Certifications" in body


def test_about_content_comes_from_the_database(client):
    """Skills and certifications were the last two things read off disk.

    A row rendered on the page is the proof the seed, the model and the
    template still agree; an empty grid would render as a valid page.
    """
    from app.models import Certification, Skill

    assert Skill.query.count() > 0
    assert Certification.query.count() > 0

    body = client.get("/").get_data(as_text=True)
    assert Skill.query.order_by(Skill.display_order).first().name in body
    assert Certification.ordered()[0].issuer in body


def test_contact(client):
    assert client.get("/contact").status_code == 200


def test_projects(client):
    assert client.get("/projects/").status_code == 200


def test_blog_listing(client):
    assert client.get("/blog/").status_code == 200


def test_blog_post(client):
    assert client.get("/blog/gpu-passthrough-proxmox").status_code == 200


def test_blog_post_404(client):
    assert client.get("/blog/does-not-exist").status_code == 404


TAB_PAGERS = (("work", "work_page"), ("sidequests", "quest_page"), ("gallery", "gallery_page"))


def _pager_links(body, tab):
    """Every pagination href belonging to `tab` -- the one in the tab bar and
    the one at the end of the list."""
    blocks = [
        m.group(2)
        for m in re.finditer(
            r'<div class="tab-pager[^"]*" data-tab="([a-z]+)">(.*?)</div>', body, re.S
        )
        if m.group(1) == tab
    ]
    blocks += [
        m.group(0)
        for m in re.finditer(
            r'<div id="tab-([a-z]+)" class="tab-panel.*?(?=<div id="tab-|\Z)', body, re.S
        )
        if m.group(1) == tab
    ]
    return [
        html.unescape(href)
        for block in blocks
        for href in re.findall(r'class="page-btn[^"]*" href="([^"]+)"', block)
    ]


def test_pagination_links_stay_in_their_tab(client, monkeypatch):
    """Paging the gallery used to land you back on Work.

    Which tab is showing lives in the query string, but these hrefs are built
    server-side at render time and the tab can also be switched client-side
    afterwards -- projects.js replaceStates the address bar without re-asking
    the server. So a pager that emitted only its own page number produced a URL
    with no tab in it, and the server answered with the default one.
    """
    from app.blueprints.projects import routes

    # One row per page, so every tab paginates whatever the seed data holds.
    monkeypatch.setattr(routes, "PER_PAGE", 1)

    body = client.get("/projects/").get_data(as_text=True)
    checked = 0
    for tab, param in TAB_PAGERS:
        for href in _pager_links(body, tab):
            checked += 1
            args = parse_qs(urlsplit(href).query)
            assert args.get("tab") == [tab], f"{tab} pager dropped its tab: {href}"
            assert param in args, f"{tab} pager dropped its page param: {href}"
            landed = client.get(href).get_data(as_text=True)
            shown = re.search(r'<div id="(tab-[a-z]+)" class="tab-panel(?! hidden)', landed)
            assert shown and shown.group(1) == f"tab-{tab}", (
                f"{href} opened {shown and shown.group(1)}, not tab-{tab}"
            )
    assert checked, "no pagination rendered at all -- this test proved nothing"
