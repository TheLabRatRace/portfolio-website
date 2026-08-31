"""The bucket layout and the two storage backends.

The key convention is the part of this feature that is expensive to change
later -- once objects are written under a prefix, the prefix is what the
bucket is. So the shape of a key is asserted literally here rather than
recomputed from the same function that produces it.
"""

import io
from datetime import date

import pytest
from werkzeug.datastructures import FileStorage

from app import services
from app.models import Post, Project
from app.services import assets, storage


# ── The key convention ───────────────────────────────────────────────────

def test_blog_prefix_is_dated_then_named():
    """The user's rule: Year/Month/Day, then the post's name."""
    assert assets.build_prefix(
        "Images", "blog", slug="gpu-passthrough", when=date(2026, 8, 30)
    ) == "Images/Portfolio-Site/Blog/2026/08/30/gpu-passthrough"


def test_two_posts_on_one_day_get_sibling_prefixes():
    """The second post of a day nests under the day, it does not replace it."""
    first, second = (
        assets.build_prefix("Images", "blog", slug=s, when=date(2026, 8, 30))
        for s in ("first-post", "second-post")
    )
    assert first != second
    assert first.rsplit("/", 1)[0] == second.rsplit("/", 1)[0]


@pytest.mark.parametrize(
    ("section", "expected"),
    [
        ("work", "Images/Portfolio-Site/Projects/Work/2026/08/30/x"),
        ("sidequest", "Images/Portfolio-Site/Projects/SideQuests/2026/08/30/x"),
        ("gallery", "Images/Portfolio-Site/Projects/Project-Gallery/2026/08/30/x"),
    ],
)
def test_project_sections_match_the_bucket(section, expected):
    assert assets.build_prefix(
        "Images", section, slug="x", when=date(2026, 8, 30)
    ) == expected


def test_undated_sections_take_no_date():
    """Home and Contact have one set of images; a date on them would be noise."""
    assert assets.build_prefix("Images", "home") == "Images/Portfolio-Site/Home"
    assert assets.build_prefix("Images", "contact") == "Images/Portfolio-Site/Contact"


def test_category_follows_the_extension():
    assert assets.category_for("a.webp") == "Images"
    assert assets.category_for("a.MP4") == "Video"
    assert assets.category_for("a.flac") == "Audio"
    assert assets.category_for("a.exe") is None


def test_key_refuses_a_file_it_cannot_categorise():
    with pytest.raises(assets.AssetKeyError):
        assets.build_key("payload.exe", "home")


def test_traversal_cannot_escape_the_prefix():
    """A slug is not always a slug -- an admin can type anything into the field."""
    key = assets.build_key("shell.png", "blog", slug="../../etc", when=date(2026, 1, 2))
    assert ".." not in key
    assert key.startswith("Images/Portfolio-Site/Blog/2026/01/02/")


def test_one_prefix_serves_all_three_categories():
    prefixes = assets.prefixes_for("blog", slug="p", when=date(2026, 1, 2))
    assert set(prefixes) == {"Images", "Video", "Audio"}
    tails = {p.split("/", 1)[1] for p in prefixes.values()}
    assert len(tails) == 1, "the categories must differ only in the first segment"


# ── The stored value ─────────────────────────────────────────────────────

def test_s3_uri_round_trips():
    assert storage.is_s3_uri("s3:Images/a.webp")
    assert storage.key_of("s3:Images/a.webp") == "Images/a.webp"
    assert not storage.is_s3_uri("uploads/a.webp")
    assert storage.key_of("uploads/a.webp") is None


def test_local_paths_resolve_to_static(app):
    """A row written before S3 existed still renders. No migration."""
    with app.test_request_context():
        assert services.resolve("uploads/a.webp").endswith(
            "/static/images/uploads/a.webp"
        )


def test_s3_uri_resolves_through_the_public_base(app):
    app.config["S3_BUCKET"] = "thelabratrace-assets"
    app.config["S3_PUBLIC_BASE_URL"] = "https://cdn.example.com/"
    with app.test_request_context():
        assert services.resolve("s3:Images/Portfolio-Site/Home/a.webp") == (
            "https://cdn.example.com/Images/Portfolio-Site/Home/a.webp"
        )


def test_resolve_is_empty_for_nothing(app):
    with app.test_request_context():
        assert services.resolve(None) == ""
        assert services.resolve("") == ""


def test_backend_follows_the_bucket_setting(app):
    assert services.backend() == "local", "a test run must never touch a bucket"
    app.config["S3_BUCKET"] = "thelabratrace-assets"
    assert services.backend() == "s3"


def test_unique_filename_keeps_the_original_readable():
    name = services.unique_filename("Screen Shot 2026.PNG")
    assert name.endswith("-screen-shot-2026.png")
    assert services.unique_filename("a.png") != services.unique_filename("a.png")


# ── Writing ──────────────────────────────────────────────────────────────

def _upload(name="cover.webp"):
    return FileStorage(
        stream=io.BytesIO(b"not really an image"),
        filename=name,
        content_type="image/webp",
    )


def test_local_save_flattens_the_key(app):
    """The dated tree is an S3 idea; on disk it would be empty directories."""
    with app.test_request_context():
        value = services.save(_upload(), "Images/Portfolio-Site/Blog/2026/01/02/p/a.webp")
    assert value.startswith("uploads/")
    assert value.endswith(".webp")
    (app.config["UPLOAD_DIR"] / value.split("/", 1)[1]).unlink()


def test_s3_save_stores_the_uri_not_the_url(app, monkeypatch):
    """The database holds a key. URLs are built at render time, so a bucket
    move or a CDN in front of it is a config change, not a data migration.
    """
    sent = {}

    class FakeClient:
        def upload_fileobj(self, stream, bucket, key, ExtraArgs=None):  # noqa: N803
            sent.update(bucket=bucket, key=key, extra=ExtraArgs)

    app.config["S3_BUCKET"] = "thelabratrace-assets"
    monkeypatch.setattr(storage, "_client", lambda: FakeClient())

    key = "Images/Portfolio-Site/Blog/2026/01/02/p/a.webp"
    with app.test_request_context():
        value = services.save(_upload(), key)

    assert value == f"s3:{key}"
    assert sent["bucket"] == "thelabratrace-assets"
    assert sent["key"] == key
    assert sent["extra"]["ContentType"] == "image/webp"
    assert "immutable" in sent["extra"]["CacheControl"]


def test_upload_failure_raises_rather_than_storing_a_bad_row(app, monkeypatch):
    from botocore.exceptions import ClientError

    class BrokenClient:
        def upload_fileobj(self, *a, **k):
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")

    app.config["S3_BUCKET"] = "thelabratrace-assets"
    monkeypatch.setattr(storage, "_client", lambda: BrokenClient())
    with app.test_request_context(), pytest.raises(services.StorageError):
        services.save(_upload(), "Images/Portfolio-Site/Home/a.webp")


# ── The prefix on a row ──────────────────────────────────────────────────

def test_a_new_post_gets_a_prefix_without_any_upload(db_session):
    """The user's rule: every new post, asset or no asset."""
    post = Post(
        title="T", slug="prefix-test-post", content="c", date=date(2026, 8, 30),
    )
    db_session.add(post)
    db_session.flush()
    assert post.asset_prefix == "Portfolio-Site/Blog/2026/08/30/prefix-test-post"


def test_a_new_project_files_under_its_type(db_session):
    project = Project(type="sidequest", title="T", slug="prefix-test-quest")
    db_session.add(project)
    db_session.flush()
    assert project.asset_prefix.startswith("Portfolio-Site/Projects/SideQuests/")
    assert project.asset_prefix.endswith("/prefix-test-quest")


def test_a_prefix_survives_a_rename(db_session):
    """Objects already sit under it; rewriting the column would orphan them."""
    post = Post(title="T", slug="prefix-keep", content="c", date=date(2026, 8, 30))
    db_session.add(post)
    db_session.flush()
    original = post.asset_prefix
    post.slug = "prefix-keep-renamed"
    post.ensure_asset_prefix()
    assert post.asset_prefix == original


def test_row_prefix_expands_to_three_categories(db_session):
    post = Post(title="T", slug="prefix-three", content="c", date=date(2026, 8, 30))
    db_session.add(post)
    db_session.flush()
    assert post.asset_prefixes["Images"] == (
        "Images/Portfolio-Site/Blog/2026/08/30/prefix-three"
    )
    assert post.asset_prefixes["Audio"].startswith("Audio/")
