from app.models.search import search_vector_column

from app.extensions import db


class GalleryImage(db.Model):
    __tablename__ = "gallery_images"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    label = db.Column(db.String(200))
    thumbnail_path = db.Column(db.String(500))
    image_path = db.Column(db.String(500))
    display_order = db.Column(db.Integer, default=0)
    search_vector = search_vector_column()

    project = db.relationship("Project", back_populates="gallery_images")

    @property
    def path(self):
        return self.image_path

    def __repr__(self):
        return f"<GalleryImage {self.id} {self.label!r}>"
