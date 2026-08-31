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
