"""A read-only JSON view of everything the public site renders.

This exists so the page shell can be a static file. The shell -- HTML, CSS,
JSON -- is cacheable at an edge and never touches the database; the text and
the image URLs come from here, out of Postgres, per request.

Three deliberate constraints:

  * **Read-only.** Every route is GET and every query filters on
    published=True. There is no write path, so there is nothing here for CSRF
    to protect and nothing an unauthenticated caller can change. Writing is
    what the admin service is for, and it is a different process.
  * **Same queries as the HTML pages.** The list endpoints reuse the eager-load
    overrides the templates' queries were tuned to, and search calls the same
    run_search(). A second, subtly different copy of those queries is how a
    75 ms page quietly becomes a 1 s one again.
  * **Shaped for pre-rendering.** Every collection answers with an envelope
    ({"items": [...], "page": ...}) rather than a bare array, so a build step
    or a server-side renderer can be added later without changing a response
    shape clients already read.
"""

from flask import current_app, jsonify, request
from sqlalchemy.orm import joinedload, lazyload

from app.blueprints.api import api_bp
from app.blueprints.api import serializers as ser
from app.models import Certification, GalleryImage, Post, Project, Skill, Tag
from app.services.search import run_search

# Matches the HTML listing pages, so a client paging the API and a visitor
# paging the site see the same boundaries.
PER_PAGE = 10
MAX_PER_PAGE = 100

# What a card needs and nothing else. Same overrides as projects/routes.py:
# the model eager-loads three relationships, and a list page renders one.
_PROJECT_LIST = (joinedload(Project._tags), lazyload(Project.attachments))


def _page():
    return max(request.args.get("page", 1, type=int), 1)


def _per_page():
    requested = request.args.get("per_page", PER_PAGE, type=int)
    return min(max(requested, 1), MAX_PER_PAGE)


def _envelope(pagination, serialize):
    """The shape every collection answers with.

    An object rather than a bare array, for two reasons: a top-level JSON array
    cannot grow a field later without breaking every client that reads it, and
    the paging numbers have to go somewhere a client can find them.
    """
    return jsonify(
        {
            "items": [serialize(row) for row in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "pages": pagination.pages,
            "total": pagination.total,
        }
    )


@api_bp.after_request
def allow_cross_origin(response):
    """Let a shell on another origin fetch this.

    The static shell is served from S3/CloudFront and the API from the
    container, so every fetch between them is cross-origin. The allowlist is
    API_CORS_ORIGINS and it is empty by default: a wildcard would be harmless
    today -- everything here is public and read-only -- and exactly wrong the
    first time someone adds an endpoint that is not. So it is named.

    Vary: Origin because the answer differs per caller, and a cache that
    missed that would hand one origin another's CORS headers.
    """
    allowed = current_app.config["API_CORS_ORIGINS"]
    origin = request.headers.get("Origin")
    response.headers["Vary"] = "Origin"
    if origin and origin in allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
    return response


# ── Projects ────────────────────────────────────────────────────────────────


@api_bp.route("/projects")
def projects():
    """Published projects, newest first, or curated order with ?sort=curated.

    ?type= filters to work or sidequest and ?tag= to one tag slug. Ordering is
    total -- display_order and created_at are both non-unique, and a partial
    sort key puts a row on two pages or on none.
    """
    query = Project.query.filter_by(published=True).options(*_PROJECT_LIST)

    kind = request.args.get("type")
    if kind in ("work", "sidequest"):
        query = query.filter(Project.type == kind)

    tag_slug = request.args.get("tag")
    if tag_slug:
        query = query.filter(Project._tags.any(Tag.slug == tag_slug))

    if request.args.get("sort") == "curated":
        query = query.order_by(Project.display_order.asc(), Project.id.asc())
    else:
        query = query.order_by(Project.created_at.desc(), Project.id.desc())

    page = query.paginate(page=_page(), per_page=_per_page(), error_out=False)
    return _envelope(page, ser.project_summary)


@api_bp.route("/projects/<slug>")
def project(slug):
    row = Project.query.filter_by(slug=slug, published=True).first_or_404()
    return jsonify(ser.project_detail(row))


@api_bp.route("/gallery")
def gallery():
    """Every published project's images as one collection.

    Its own endpoint rather than a walk over /projects: paginating projects and
    then reading their images would show only the images of the ten projects
    on the current page. The sort key is the SQL one, verbatim -- project
    position, then image position, then image id, which is what makes it a
    total order and therefore stable across pages.
    """
    query = (
        GalleryImage.query
        .join(Project)
        .options(
            joinedload(GalleryImage.project).options(
                lazyload(Project._tags),
                lazyload(Project.gallery_images),
                lazyload(Project.attachments),
            )
        )
        .filter(Project.published.is_(True))
        .order_by(
            Project.display_order.asc(),
            GalleryImage.display_order.asc(),
            GalleryImage.id.asc(),
        )
    )
    page = query.paginate(page=_page(), per_page=_per_page(), error_out=False)
    return _envelope(page, lambda row: ser.gallery_image(row, with_project=True))


# ── Blog ────────────────────────────────────────────────────────────────────


@api_bp.route("/posts")
def posts():
    """Published posts by `date`, not created_at -- see the note on the model:
    a backdated post files under the day the author claims, not the day the
    row was written."""
    query = Post.query.filter_by(published=True)

    tag_slug = request.args.get("tag")
    if tag_slug:
        query = query.filter(Post._tags.any(Tag.slug == tag_slug))

    query = query.order_by(Post.date.desc(), Post.id.desc())
    page = query.paginate(page=_page(), per_page=_per_page(), error_out=False)
    return _envelope(page, ser.post_summary)


@api_bp.route("/posts/<slug>")
def post(slug):
    row = Post.query.filter_by(slug=slug, published=True).first_or_404()
    return jsonify(ser.post_detail(row))


# ── The rest of the page ────────────────────────────────────────────────────


@api_bp.route("/home")
def home():
    """What the home page needs beyond its own copy: the skills grid and the
    certifications list. One request rather than two, because the shell cannot
    render the about section until it has both."""
    return jsonify(
        {
            "skills": [ser.skill(s) for s in Skill.query.order_by(
                Skill.display_order, Skill.id
            ).all()],
            "certifications": [ser.certification(c) for c in Certification.ordered()],
        }
    )


@api_bp.route("/tags")
def tags():
    rows = Tag.query.order_by(Tag.name.asc()).all()
    return jsonify({"items": [ser.tag(t) for t in rows], "total": len(rows)})


@api_bp.route("/search")
def search():
    """The same search the HTML page runs, grouped the same way.

    Grouped by type rather than interleaved because a ts_rank score is not
    comparable across tables -- merging them would sort by document length.
    """
    raw = (request.args.get("q") or "").strip()
    results, total, too_short = run_search(raw)

    return jsonify(
        {
            "q": raw,
            "total": total,
            "too_short": too_short,
            "results": {
                "work": [ser.project_summary(p) for p in results["work"]],
                "sidequests": [ser.project_summary(p) for p in results["sidequests"]],
                "gallery": [
                    ser.gallery_image(i, with_project=True) for i in results["gallery"]
                ],
                "posts": [ser.post_summary(p) for p in results["posts"]],
                "tags": [ser.tag(t) for t in results["tags"]],
            },
        }
    )
