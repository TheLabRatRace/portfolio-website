"""Site-wide search, as a function rather than as a route.

This is the query half of app/blueprints/search: the HTML page and the JSON
API both call run_search() and differ only in what they do with the result.
Keeping one copy matters more here than in most places -- the eager-load
overrides below are the difference between five round trips and fourteen, and
a second copy would drift out of that tuning silently.

The index is the generated `search_vector` column on each table
(schema_admin_search.sql), which decides most of what this module can do:

  * Matching is by stem, not substring -- "deploying" finds "deploy", "prox"
    does not find "Proxmox". Tags cover the prefix case via a trigram index.
  * Ranking is ts_rank against the weights baked into the column at write
    time (title A > summary B > body C). Nothing here re-ranks.
  * Results are grouped by type, not interleaved: a relevance score is not
    comparable across tables, so a merged list would sort by document length.
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload, lazyload

from app.extensions import db
from app.models import GalleryImage, Post, Project, Tag

# Project and Post load their relationships eagerly (lazy="selectin"), which is
# a round trip apiece on every query that touches them -- and this runs five.
# Against a database on the far side of a WAN link those trips are the entire
# cost of the page, so each query below asks for exactly what the results need
# and refuses the rest.
# lazyload rather than noload throughout: noload does not merely skip a load,
# it blanks the collection on an instance that may already have it, which is a
# silently wrong page. lazyload costs the same nothing when the attribute is
# never touched, and if one ever is, the symptom is a slow page instead.
_PROJECT_RESULT = (
    # results.html shows item.title, .slug, .description and .tags.
    joinedload(Project._tags),
    lazyload(Project.gallery_images),
    lazyload(Project.attachments),
)

# Per type, per page. Search is a way into the site, not a second index of
# it -- someone who wants all 63 gallery images wants the gallery tab.
LIMIT = 8

# Below this, the query is a fragment rather than a search: one or two
# letters match a stem in almost everything and rank in nothing.
MIN_QUERY = 2

KINDS = ("work", "sidequests", "gallery", "posts", "tags")


def _tsquery(text):
    """websearch_to_tsquery: accepts the grammar people already type ("quoted
    phrases", OR, -excluded) and never raises, so a typo is a poor result
    rather than a 500. to_tsquery raises on an unbalanced quote or a bare `&`.
    """
    return func.websearch_to_tsquery("english", text)


def _rank(column, query):
    return func.ts_rank(column, query)


def run_search(raw, limit=LIMIT):
    """Search every indexed table for `raw`.

    Returns (results, total, too_short): a dict keyed by KINDS holding model
    instances, the count across all of them, and whether the query was
    rejected as too short to rank.
    """
    raw = (raw or "").strip()
    results = {kind: [] for kind in KINDS}
    too_short = bool(raw) and len(raw) < MIN_QUERY

    if not raw or too_short:
        return results, 0, too_short

    tsq = _tsquery(raw)

    def projects_of(kind):
        rank = _rank(Project.search_vector, tsq)
        return (
            Project.query
            .options(*_PROJECT_RESULT)
            .filter(
                Project.type == kind,
                Project.published.is_(True),
                Project.search_vector.op("@@")(tsq),
            )
            .order_by(rank.desc(), Project.id.asc())
            .limit(limit)
            .all()
        )

    results["work"] = projects_of("work")
    results["sidequests"] = projects_of("sidequest")

    gallery_rank = _rank(GalleryImage.search_vector, tsq)
    results["gallery"] = (
        GalleryImage.query
        .join(Project)
        # _gallery_card.html links back through img.project, and the join
        # above does not populate the relationship -- without this each
        # card on screen is its own round trip. It needs only slug and
        # title, so the project arrives without its own collections.
        # lazyload, not noload: a project can be both a gallery hit's
        # owner and a search hit in its own right, and noload does not
        # merely skip the load -- it blanks the collection on an instance
        # that already has it, so the same project's tags vanish from the
        # results above. lazyload leaves a loaded collection alone and
        # never fires for the two columns the card actually reads.
        .options(
            joinedload(GalleryImage.project).options(
                lazyload(Project._tags),
                lazyload(Project.gallery_images),
                lazyload(Project.attachments),
            )
        )
        .filter(
            Project.published.is_(True),
            GalleryImage.search_vector.op("@@")(tsq),
        )
        .order_by(gallery_rank.desc(), GalleryImage.id.asc())
        .limit(limit)
        .all()
    )

    post_rank = _rank(Post.search_vector, tsq)
    results["posts"] = (
        Post.query
        # results.html shows title, slug, excerpt and date, not tags.
        .options(lazyload(Post._tags))
        .filter(Post.published.is_(True), Post.search_vector.op("@@")(tsq))
        .order_by(post_rank.desc(), Post.id.desc())
        .limit(limit)
        .all()
    )

    # Substring, unlike everything else: a tag is a short label people
    # half-type, and stemming "prox" gets nowhere (idx_tags_name_trgm).
    pattern = f"%{raw}%"
    results["tags"] = (
        db.session.query(Tag)
        .filter(or_(Tag.name.ilike(pattern), Tag.slug.ilike(pattern)))
        .order_by(func.length(Tag.name).asc(), Tag.name.asc())
        .limit(limit)
        .all()
    )

    return results, sum(len(v) for v in results.values()), too_short
