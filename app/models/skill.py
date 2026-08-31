from app.extensions import db


class Skill(db.Model):
    """One line in the skills grid, with its group heading on the row.

    `display_order` is a single sequence over the whole list rather than one
    per group, which is what lets `grouped()` decide the order of the headings
    without a second table to hold it: a group appears where its first skill
    does. Moving a group means renumbering its members, and that is the whole
    cost of not having a categories table for four categories.
    """

    __tablename__ = "skills"
    __table_args__ = (db.UniqueConstraint("category", "name"),)

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)

    @classmethod
    def grouped(cls):
        """`{heading: [name, ...]}` -- the shape the about section renders.

        A dict preserves insertion order, so iterating rows already sorted by
        display_order puts both the groups and their contents in the author's
        order in one pass.
        """
        groups = {}
        for skill in cls.query.order_by(cls.display_order, cls.id).all():
            groups.setdefault(skill.category, []).append(skill.name)
        return groups

    def __repr__(self):
        return f"<Skill {self.category}: {self.name}>"
