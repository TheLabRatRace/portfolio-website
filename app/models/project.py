from app.models.assets import AssetPrefixMixin, tracks_assets
from app.models.search import search_vector_column
from app.models.tag import project_tags

from app.extensions import db
from app.services import section_for_project


@tracks_assets
class Project(AssetPrefixMixin, db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(20))
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text)
    long_description = db.Column(db.Text)
    _status = db.Column("status", db.String(20))
    specs = db.Column(db.ARRAY(db.Text))
    display_order = db.Column(db.Integer, default=0)
    published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    search_vector = search_vector_column()

    _tags = db.relationship(
        "Tag", secondary=project_tags,
        # Must be the string form: SQLAlchemy aliases the table inside the
        # generated query, and a bare column object references the wrong FROM.
        order_by="Tag.name", lazy="selectin",
    )
    gallery_images = db.relationship(
        "GalleryImage", back_populates="project",
        order_by="GalleryImage.display_order", lazy="selectin",
        cascade="all, delete-orphan",
    )
    attachments = db.relationship(
        "Attachment", back_populates="project",
        order_by="Attachment.display_order", lazy="selectin",
        cascade="all, delete-orphan",
    )

    @property
    def status(self):
        if self._status and "_" in self._status:
            return self._status.replace("_", "-")
        return self._status

    @property
    def tags(self):
        return [t.name for t in self._tags]

    @property
    def details(self):
        return self

    @property
    def gallery(self):
        return self.gallery_images

    @property
    def documents(self):
        return [a for a in self.attachments if a.category == "document"]

    @property
    def downloads(self):
        return [a for a in self.attachments if a.category == "download"]

    # ── Assets ──
    def asset_section(self):
        """Work or SideQuests, following `type`.

        Not Project-Gallery: that page is a view over both, so filing a
        project's images there would store them a second time under a name
        that says less about where they came from.
        """
        return section_for_project(self.type) or "work"

    @property
    def public_path(self):
        """Where this project lives on the public site, root-relative.

        See Post.public_path: the admin app has no projects blueprint, so this
        cannot come from url_for. test_public_paths pins it to the real route.
        """
        return f"/projects/{self.slug}"

    def __repr__(self):
        return f"<Project {self.slug}>"
