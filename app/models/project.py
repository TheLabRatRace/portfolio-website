from app.models.search import search_vector_column
from app.models.tag import project_tags

from app.extensions import db


class Project(db.Model):
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

    def __repr__(self):
        return f"<Project {self.slug}>"
