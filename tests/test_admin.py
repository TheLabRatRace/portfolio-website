"""The admin surface: who may reach it, and what editing actually writes."""

import pytest

from app.models import Certification, Post, Project, Skill, Tag

# Every admin URL that answers a GET. The gate is a blueprint-wide
# before_request, so this list is really one assertion repeated -- but it is
# the assertion that catches a future route added outside the gate.
PROTECTED = [
    "/admin/",
    "/admin/projects",
    "/admin/projects/new",
    "/admin/gallery",
    "/admin/posts",
    "/admin/posts/new",
    "/admin/tags",
    "/admin/skills",
    "/admin/certifications",
]


@pytest.mark.parametrize("url", PROTECTED)
def test_anonymous_is_sent_to_login(client, url):
    response = client.get(url)
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


@pytest.mark.parametrize("url", PROTECTED)
def test_admin_reaches_every_page(as_admin, url):
    assert as_admin.get(url).status_code == 200


def test_authenticated_non_admin_gets_403(client, plain_user):
    """Signed in is not the same as allowed."""
    client.post(
        "/admin/login",
        data={"username": plain_user.username,
              "password": "correct horse battery staple"},
    )
    assert client.get("/admin/").status_code == 403


def test_login_is_the_only_public_endpoint(app):
    from app.blueprints.admin.routes import PUBLIC_ENDPOINTS

    assert PUBLIC_ENDPOINTS == {"admin.login"}


# ── Projects ─────────────────────────────────────────────────────────────

def test_create_project(as_admin, db_session):
    response = as_admin.post("/admin/projects/new", data={
        "title": "Test Rack Rebuild",
        "slug": "test-rack-rebuild",
        "type": "work",
        "category": "infrastructure",
        "description": "A short description.",
        "tags": "Proxmox, Testing",
        "display_order": "5",
        "published": "y",
    })
    assert response.status_code == 302

    project = Project.query.filter_by(slug="test-rack-rebuild").one()
    assert project.title == "Test Rack Rebuild"
    assert project.published is True
    assert project.display_order == 5
    assert set(project.tags) >= {"Proxmox", "Testing"}


def test_slug_is_derived_from_the_title_when_left_blank(as_admin, db_session):
    as_admin.post("/admin/projects/new", data={
        "title": "Slug From Title Please",
        "slug": "",
        "type": "sidequest",
        "description": "x",
    })
    assert Project.query.filter_by(slug="slug-from-title-please").count() == 1


def test_duplicate_slug_is_refused(as_admin, db_session):
    data = {"title": "First", "slug": "dupe-check", "type": "work",
            "description": "x"}
    assert as_admin.post("/admin/projects/new", data=data).status_code == 302
    again = as_admin.post("/admin/projects/new",
                          data={**data, "title": "Second"})
    # Re-rendered with an error, not a second row.
    assert again.status_code == 200
    assert Project.query.filter_by(slug="dupe-check").count() == 1


def test_edit_project(as_admin, db_session):
    as_admin.post("/admin/projects/new", data={
        "title": "Before", "slug": "edit-me", "type": "work",
        "description": "old", "published": "y",
    })
    project = Project.query.filter_by(slug="edit-me").one()

    as_admin.post(f"/admin/projects/{project.id}/edit", data={
        "title": "After", "slug": "edit-me", "type": "work",
        "description": "new", "published": "y",
    })
    db_session.refresh(project)
    assert project.title == "After"
    assert project.description == "new"


def test_unpublishing_hides_a_project_from_the_public_site(as_admin, db_session):
    as_admin.post("/admin/projects/new", data={
        "title": "Draft Rack", "slug": "draft-rack", "type": "work",
        "description": "x", "published": "y",
    })
    assert as_admin.get("/projects/draft-rack").status_code == 200

    project = Project.query.filter_by(slug="draft-rack").one()
    as_admin.post(f"/admin/projects/{project.id}/edit", data={
        "title": "Draft Rack", "slug": "draft-rack", "type": "work",
        "description": "x",  # `published` omitted == unticked
    })
    # Unpublished is a 404 even for the admin who wrote it: the public route
    # has one rule, and "I can see it because I am signed in" is not it.
    assert as_admin.get("/projects/draft-rack").status_code == 404


def test_delete_project(as_admin, db_session):
    as_admin.post("/admin/projects/new", data={
        "title": "Doomed", "slug": "doomed", "type": "work", "description": "x",
    })
    project = Project.query.filter_by(slug="doomed").one()
    assert as_admin.post(f"/admin/projects/{project.id}/delete").status_code == 302
    assert Project.query.filter_by(slug="doomed").count() == 0


# ── Posts ────────────────────────────────────────────────────────────────

def test_create_post(as_admin, db_session):
    response = as_admin.post("/admin/posts/new", data={
        "title": "A Test Post",
        "slug": "a-test-post",
        "date": "2026-05-01",
        "excerpt": "Testing.",
        "content": "The body of the post.",
        "tags": "Testing",
        "published": "y",
    })
    assert response.status_code == 302
    post = Post.query.filter_by(slug="a-test-post").one()
    assert post.content == "The body of the post."
    assert str(post.date) == "2026-05-01"
    assert as_admin.get("/blog/a-test-post").status_code == 200


def test_a_post_with_no_date_still_renders(as_admin, db_session):
    """The date field is optional, so both templates must survive a null."""
    as_admin.post("/admin/posts/new", data={
        "title": "Undated", "slug": "undated", "date": "",
        "content": "Body.", "published": "y",
    })
    assert Post.query.filter_by(slug="undated").one().date is None
    assert as_admin.get("/blog/undated").status_code == 200
    assert as_admin.get("/blog/").status_code == 200


def test_unpublished_post_is_not_public(as_admin, db_session):
    as_admin.post("/admin/posts/new", data={
        "title": "Unfinished", "slug": "unfinished", "content": "Body.",
    })
    assert as_admin.get("/blog/unfinished").status_code == 404


def test_post_requires_content(as_admin, db_session):
    response = as_admin.post("/admin/posts/new", data={
        "title": "Empty", "slug": "empty", "content": "",
    })
    assert response.status_code == 200
    assert Post.query.filter_by(slug="empty").count() == 0


# ── Tags ─────────────────────────────────────────────────────────────────

def test_create_tag(as_admin, db_session):
    response = as_admin.post("/admin/tags", data={
        "name": "Test Tag", "slug": "test-tag", "color": "#c9a84c",
    })
    assert response.status_code == 302
    assert Tag.query.filter_by(slug="test-tag").count() == 1


def test_tags_are_reused_not_duplicated(as_admin, db_session):
    """Two projects tagged the same must share one row, or the tag pages lie."""
    for slug in ("shared-tag-a", "shared-tag-b"):
        as_admin.post("/admin/projects/new", data={
            "title": slug, "slug": slug, "type": "work",
            "description": "x", "tags": "Reused Tag",
        })
    assert Tag.query.filter_by(name="Reused Tag").count() == 1


# ── Skills and certifications ────────────────────────────────────────────

def test_create_skill(as_admin, db_session):
    response = as_admin.post("/admin/skills", data={
        "category": "Test Group", "name": "Test Skill", "display_order": "3",
    })
    assert response.status_code == 302
    skill = Skill.query.filter_by(name="Test Skill").one()
    assert skill.category == "Test Group"
    assert skill.display_order == 3


def test_editing_a_skill_updates_the_row_it_names(as_admin, db_session):
    """?edit= has to update, not insert -- the bug would be silent duplicates."""
    as_admin.post("/admin/skills", data={
        "category": "Before", "name": "Renameable", "display_order": "0",
    })
    skill = Skill.query.filter_by(name="Renameable").one()

    as_admin.post(f"/admin/skills?edit={skill.id}", data={
        "category": "After", "name": "Renamed", "display_order": "1",
    })
    assert Skill.query.filter_by(id=skill.id).one().category == "After"
    assert Skill.query.filter_by(name="Renameable").count() == 0


def test_editing_a_missing_skill_is_a_404(as_admin, db_session):
    assert as_admin.get("/admin/skills?edit=999999").status_code == 404


def test_skills_group_in_display_order(as_admin, db_session):
    """A group's position is its first member's, which is the whole ordering
    contract the about section depends on.
    """
    for order, (category, name) in enumerate([
        ("Zulu", "z-first"), ("Alpha", "a-second"), ("Zulu", "z-third"),
    ]):
        as_admin.post("/admin/skills", data={
            "category": category, "name": name, "display_order": str(900 + order),
        })
    groups = Skill.grouped()
    tail = [g for g in groups if g in ("Zulu", "Alpha")]
    assert tail == ["Zulu", "Alpha"]
    assert groups["Zulu"] == ["z-first", "z-third"]


def test_create_certification(as_admin, db_session):
    response = as_admin.post("/admin/certifications", data={
        "name": "Test Cert", "issuer": "Test Issuer",
        "status": "in_progress", "year": "2026", "display_order": "9",
    })
    assert response.status_code == 302
    cert = Certification.query.filter_by(name="Test Cert").one()
    assert cert.status == "in_progress"
    assert cert.year == 2026


def test_certification_status_is_limited_to_the_three_with_a_dot(as_admin, db_session):
    """A fourth status renders an invisible dot, so the form must refuse it."""
    as_admin.post("/admin/certifications", data={
        "name": "Bad Status Cert", "issuer": "x", "status": "revoked",
    })
    assert Certification.query.filter_by(name="Bad Status Cert").count() == 0


def test_delete_certification(as_admin, db_session):
    as_admin.post("/admin/certifications", data={
        "name": "Doomed Cert", "issuer": "x", "status": "active",
    })
    cert = Certification.query.filter_by(name="Doomed Cert").one()
    assert as_admin.post(f"/admin/certifications/{cert.id}/delete").status_code == 302
    assert Certification.query.filter_by(id=cert.id).count() == 0


# ── Pagination ───────────────────────────────────────────────────────────

def test_list_pages_accept_a_page_number(as_admin):
    assert as_admin.get("/admin/projects?page=2").status_code == 200
    # Past the end is an empty page, not a 404 -- error_out=False.
    assert as_admin.get("/admin/projects?page=9999").status_code == 200


def test_project_list_filters_by_type(as_admin):
    for kind in ("work", "sidequest"):
        assert as_admin.get(f"/admin/projects?type={kind}").status_code == 200
