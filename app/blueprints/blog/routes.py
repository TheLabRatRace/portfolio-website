"""The blog, served from the posts table -- the one the admin UI writes to."""

from flask import abort, current_app, render_template

from app.blueprints.blog import blog_bp
from app.models import Post


def _published():
    """Newest first, with display_order then id as tiebreakers -- otherwise
    two posts from the same day come back in whatever order the planner likes.
    """
    return Post.query.filter_by(published=True).order_by(
        Post.date.desc().nulls_last(),
        Post.display_order.asc(),
        Post.id.desc(),
    )


@blog_bp.route("/")
def index():
    return render_template(
        "blog/list.html", active_section="blog", posts=_published().all()
    )


@blog_bp.route("/<slug>")
def detail(slug):
    post = _published().filter_by(slug=slug).first()
    if post is None:
        current_app.logger.warning("Blog post not found: %s", slug)
        abort(404)
    return render_template("blog/detail.html", active_section="blog", post=post)
