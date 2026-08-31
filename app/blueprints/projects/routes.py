from flask import abort, render_template, request, url_for
from sqlalchemy.orm import joinedload

from app.blueprints.projects import projects_bp
from app.models import GalleryImage, Project

PER_PAGE = 10
TABS = ("work", "sidequests", "gallery")
CATEGORIES = ("all", "infrastructure", "code")


def _ordered(query, sort):
    """Apply a *total* ordering.

    Neither display_order nor created_at is unique here, and a partial sort key
    lets Postgres return tied rows in any order -- so a row can land on two
    pages or on none. Project.id breaks every tie.
    """
    if sort == "curated":
        return query.order_by(Project.display_order.asc(), Project.id.asc())
    return query.order_by(Project.created_at.desc(), Project.id.desc())


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

    work_query = Project.query.filter_by(type="work", published=True)
    if category != "all":
        work_query = work_query.filter_by(category=category)
    work = _ordered(work_query, sort).paginate(
        page=_page("work_page"), per_page=PER_PAGE, error_out=False
    )

    quests = _ordered(
        Project.query.filter_by(type="sidequest", published=True), sort
    ).paginate(page=_page("quest_page"), per_page=PER_PAGE, error_out=False)

    # Its own collection: paginating projects and then walking their images
    # would show only the images of the ten projects currently on screen.
    gallery = (
        GalleryImage.query
        .join(Project)
        .filter(Project.published.is_(True))
        .options(joinedload(GalleryImage.project))
        .order_by(
            Project.display_order.asc(),
            GalleryImage.display_order.asc(),
            GalleryImage.id.asc(),
        )
        .paginate(page=_page("gallery_page"), per_page=PER_PAGE, error_out=False)
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
