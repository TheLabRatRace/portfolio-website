"""Site-wide search over projects, side quests, gallery labels and posts.

The index is the generated `search_vector` column on each of those tables
(schema_admin_search.sql), which decides most of what this module can do:

  * Matching is by stem, not substring -- "deploying" finds "deploy", "prox"
    does not find "Proxmox". Tags cover the prefix case via a trigram index.
  * Ranking is ts_rank against the weights baked into the column at write
    time (title A > summary B > body C). Nothing here re-ranks.
  * Results are grouped by type, not interleaved: a relevance score is not
    comparable across tables, so a merged list would sort by document length.
"""

from flask import render_template, request
from sqlalchemy import func, or_

from app.blueprints.search import search_bp
from app.extensions import db
from app.models import GalleryImage, Post, Project, Tag

# Per type, per page. Search is a way into the site, not a second index of
# it -- someone who wants all 63 gallery images wants the gallery tab.
LIMIT = 8

# Below this, the query is a fragment rather than a search: one or two
# letters match a stem in almost everything and rank in nothing.
MIN_QUERY = 2


def _tsquery(text):
    """websearch_to_tsquery: accepts the grammar people already type ("quoted
    phrases", OR, -excluded) and never raises, so a typo is a poor result
    rather than a 500. to_tsquery raises on an unbalanced quote or a bare `&`.
    """
    return func.websearch_to_tsquery("english", text)


def _rank(column, query):
    return func.ts_rank(column, query)


# "" rather than "/", so the canonical URL is /search?q= -- the spelling people
# type and paste. strict_slashes=False lets /search/ answer as well.
@search_bp.route("", strict_slashes=False)
def index():
    raw = (request.args.get("q") or "").strip()

    results = {"work": [], "sidequests": [], "gallery": [], "posts": [], "tags": []}
    total = 0
    too_short = bool(raw) and len(raw) < MIN_QUERY

    if raw and not too_short:
        tsq = _tsquery(raw)

        def projects_of(kind):
            rank = _rank(Project.search_vector, tsq)
            return (
                Project.query
                .filter(
                    Project.type == kind,
                    Project.published.is_(True),
                    Project.search_vector.op("@@")(tsq),
                )
                .order_by(rank.desc(), Project.id.asc())
                .limit(LIMIT)
                .all()
            )

        results["work"] = projects_of("work")
        results["sidequests"] = projects_of("sidequest")

        gallery_rank = _rank(GalleryImage.search_vector, tsq)
        results["gallery"] = (
            GalleryImage.query
            .join(Project)
            .filter(
                Project.published.is_(True),
                GalleryImage.search_vector.op("@@")(tsq),
            )
            .order_by(gallery_rank.desc(), GalleryImage.id.asc())
            .limit(LIMIT)
            .all()
        )

        post_rank = _rank(Post.search_vector, tsq)
        results["posts"] = (
            Post.query
            .filter(Post.published.is_(True), Post.search_vector.op("@@")(tsq))
            .order_by(post_rank.desc(), Post.id.desc())
            .limit(LIMIT)
            .all()
        )

        # Substring, unlike everything else: a tag is a short label people
        # half-type, and stemming "prox" gets nowhere (idx_tags_name_trgm).
        pattern = f"%{raw}%"
        results["tags"] = (
            db.session.query(Tag)
            .filter(or_(Tag.name.ilike(pattern), Tag.slug.ilike(pattern)))
            .order_by(func.length(Tag.name).asc(), Tag.name.asc())
            .limit(LIMIT)
            .all()
        )

        total = sum(len(v) for v in results.values())

    return render_template(
        "search/results.html",
        active_section="search",
        q=raw,
        results=results,
        total=total,
        too_short=too_short,
        limit=LIMIT,
    )
