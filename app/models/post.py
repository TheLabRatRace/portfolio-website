from app.models.assets import AssetPrefixMixin, tracks_assets
from app.models.search import search_vector_column
from app.models.tag import post_tags

from app.extensions import db


@tracks_assets
class Post(AssetPrefixMixin, db.Model):
    """A blog post, as rows rather than as YAML.

    `date` and `created_at` are separate facts: created_at is when the row was
    written, date is when the author says it was published. The list orders by
    the second, so a post can be backdated without lying about the first.
    """

    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    excerpt = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)
    published = db.Column(db.Boolean, default=False)
    date = db.Column(db.Date)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    search_vector = search_vector_column()

    # Same shape as Project._tags: templates want strings, the admin wants Tag
    # rows, so the relationship is private and `tags` is the reader-facing view.
    _tags = db.relationship(
        "Tag", secondary=post_tags, order_by="Tag.name", lazy="selectin",
    )

    @property
    def tags(self):
        return [t.name for t in self._tags]

    # ── Assets ──
    def asset_section(self):
        return "blog"

    def asset_date(self):
        """The publication date, so a backdated post files under its own day.

        Falling back to today rather than to created_at: created_at is not set
        until the INSERT that this runs before, so reading it here would give
        None on exactly the rows that need a date.
        """
        return self.date

    @property
    def public_path(self):
        """Where this post lives on the public site, as a root-relative path.

        Spelled out here rather than built with url_for because the admin app
        does not register the blog blueprint -- it has no such endpoint to
        build from. test_public_paths asserts this stays equal to what
        url_for produces, so the two cannot drift apart quietly.
        """
        return f"/blog/{self.slug}"

    def __repr__(self):
        return f"<Post {self.slug}>"
