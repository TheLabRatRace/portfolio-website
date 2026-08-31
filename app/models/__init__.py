"""Models, one domain per file, re-exported here.

`from app.models import Project` still works exactly as it did when this
was a single module -- the split is invisible to every caller. What it buys
is that the association tables live next to Tag, the two content types stop
sharing a 200-line file, and User arrives without enlarging anything that
already existed.

Import order matters: SQLAlchemy resolves relationships by class name at
mapper-configuration time, so every mapped class has to be imported before
the first query runs. Importing them all here guarantees that, whichever
model a caller happens to ask for first.
"""

from app.models.attachment import Attachment
from app.models.certification import Certification
from app.models.gallery import GalleryImage
from app.models.post import Post
from app.models.project import Project
from app.models.skill import Skill
from app.models.tag import Tag, post_tags, project_tags
from app.models.user import User

__all__ = [
    "Attachment",
    "Certification",
    "GalleryImage",
    "Post",
    "Project",
    "Skill",
    "Tag",
    "User",
    "post_tags",
    "project_tags",
]
