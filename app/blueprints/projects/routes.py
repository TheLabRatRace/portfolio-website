from flask import abort, render_template, request, url_for
from flask_sqlalchemy.pagination import Pagination
from sqlalchemy.orm import joinedload, lazyload

from app.blueprints.projects import projects_bp
from app.models import Project

PER_PAGE = 10
TABS = ("work", "sidequests", "gallery")
CATEGORIES = ("all", "infrastructure", "code")


class _ListPagination(Pagination):
    """Paginate a list that is already in memory.

    Subclassing the real Pagination rather than imitating it: `pages`,
    `iter_pages`, `has_next`, `prev_num` and the rest are inherited unchanged,
    so components/_pagination.html cannot tell the two apart.
    """

    def _query_items(self):
        first = (self.page - 1) * self.per_page
        return self._query_args["items"][first : first + self.per_page]

    def _query_count(self):
        return len(self._query_args["items"])


def _paginate(items, page):
    return _ListPagination(
        page=page, per_page=PER_PAGE, error_out=False, items=items
    )


def _ordered(projects, sort):
    """Apply a *total* ordering.

    Neither display_order nor created_at is unique here, and a partial sort key
    leaves tied rows in any order -- so a row can land on two pages or on none.
    Project.id breaks every tie.
    """
    if sort == "curated":
        return sorted(projects, key=lambda p: (p.display_order or 0, p.id))
    return sorted(projects, key=lambda p: (p.created_at, p.id), reverse=True)


def _page(name):
    return max(request.args.get(name, 1, type=int), 1)


def _page_url(**overrides):
    """Rebuild the current URL with some query params replaced, so one tab's
    controls do not reset the other tabs' state.
    """
    args = request.args.to_dict()
    args.update(overrides)
    # The page size is fixed now; drop a per_page from an old bookmark rather
    # than carrying a parameter nothing reads through every link.
    args.pop("per_page", None)
    args = {k: v for k, v in args.items() if v not in (None, "", "all")}
    return url_for("projects.index", **args)


@projects_bp.route("/")
def index():
    sort = "curated" if request.args.get("sort") == "curated" else "latest"
    category = request.args.get("category", "all")
    if category not in CATEGORIES:
        category = "all"
    tab = request.args.get("tab", "work")
    if tab not in TABS:
        tab = "work"

    # One page, three collections, all drawn from the same small set of rows.
    # Fetching that set once and slicing it in Python costs three round trips
    # instead of fourteen; against a database 60 ms away that is the whole
    # difference between a 1 s page and a 300 ms one, and in-region it is the
    # difference between 15 ms and 4 ms. The queries were never slow -- there
    # were just far too many of them.
    #
    # The model loads all three relationships eagerly (lazy="selectin"), which
    # is one extra round trip each:
    #   attachments  -- nothing here renders one, so lazyload drops the trip.
    #                   (lazyload, not noload: noload blanks the collection on
    #                   an instance that already has it, which is a silently
    #                   wrong page rather than a slow one.)
    #   _tags        -- every row shows up to three. Folded into the main query
    #                   with a join: a project has a handful of tags, so the
    #                   duplicated project columns cost far less than a trip.
    #   gallery_images -- left as selectin on purpose. Joining it too would
    #                   make the result tags x images per project, and images
    #                   are the collection that actually grows here.
    published = (
        Project.query
        .filter_by(published=True)
        .options(lazyload(Project.attachments), joinedload(Project._tags))
        .all()
    )

    work_items = [p for p in published if p.type == "work"]
    if category != "all":
        work_items = [p for p in work_items if p.category == category]
    work = _paginate(_ordered(work_items, sort), _page("work_page"))

    quests = _paginate(
        _ordered([p for p in published if p.type == "sidequest"], sort),
        _page("quest_page"),
    )

    # Its own collection: paginating projects and then walking their images
    # would show only the images of the ten projects currently on screen.
    #
    # The key is the SQL one, verbatim -- (project position, image position,
    # image id). Note it does not group by project: two projects can share a
    # display_order, and then their images interleave. That is already a total
    # order because image id is unique, so it is stable rather than a paging
    # bug, and reproducing it exactly keeps this a pure speed change.
    gallery = _paginate(
        sorted(
            (image for project in published for image in project.gallery_images),
            key=lambda i: (i.project.display_order or 0, i.display_order or 0, i.id),
        ),
        _page("gallery_page"),
    )

    return render_template(
        "projects/list.html",
        active_section="projects",
        work=work,
        quests=quests,
        gallery=gallery,
        tab=tab,
        category=category,
        sort=sort,
        page_url=_page_url,
    )


@projects_bp.route("/<slug>")
def detail(slug):
    """One route serves every project -- <slug> is a URL variable, not a literal."""
    project = Project.query.filter_by(slug=slug, published=True).first_or_404()
    return render_template(
        "projects/detail.html",
        active_section="projects",
        item=project,
    )


@projects_bp.route("/panel/<slug>")
def panel(slug):
    """The detail panel as a bare HTML fragment, fetched on click.

    Same template as the full page; only the chrome around it differs.
    """
    project = Project.query.filter_by(slug=slug, published=True).first_or_404()
    if not request.accept_mimetypes.accept_html:
        abort(406)
    return render_template("projects/_panel_fragment.html", item=project)
