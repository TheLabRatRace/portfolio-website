from app.extensions import db


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    category = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.String(20))
    url = db.Column(db.String(500), nullable=False)
    display_order = db.Column(db.Integer, default=0)

    project = db.relationship("Project", back_populates="attachments")

    @property
    def type(self):
        return self.file_type

    @property
    def size(self):
        return self.file_size

    def __repr__(self):
        return f"<Attachment {self.name!r}>"
