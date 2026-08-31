from app.extensions import db


class Certification(db.Model):
    """A certification row in the about section.

    `status` is constrained in the schema to the three values the stylesheet
    has a dot colour for -- a fourth would render a dot nobody can see.
    """

    __tablename__ = "certifications"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    issuer = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    year = db.Column(db.Integer)
    display_order = db.Column(db.Integer, nullable=False, default=0)

    STATUSES = ("active", "in_progress", "expired")

    @classmethod
    def ordered(cls):
        return cls.query.order_by(cls.display_order, cls.id).all()

    def __repr__(self):
        return f"<Certification {self.name}>"
