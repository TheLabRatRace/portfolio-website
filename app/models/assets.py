"""The bucket prefix a content row owns.

Every post and every project gets one when it is created, whether or not
anything has been uploaded to it. That is deliberate: the prefix answers
"where would a picture of this go", and the answer has to exist before there
is a picture, otherwise the layout of the bucket is decided by whoever
happens to upload first.

The stored value has no category segment -- `Portfolio-Site/Blog/2026/08/30/
gpu-passthrough-proxmox` -- because one row's images, video and audio differ
only in that first segment. `asset_prefixes` puts it back for all three.
"""

from sqlalchemy import event

from app.extensions import db
from app.services import categorised, content_prefix


class AssetPrefixMixin:
    """Adds `asset_prefix`, filled in automatically on first insert.

    A subclass says which section of the bucket it belongs to and, if that
    section is dated, which date to file it under. Everything else -- the
    format of the prefix, when it is assigned, how it is split by category --
    is decided here and in `app.services.assets`, so the two content types
    cannot drift apart.
    """

    asset_prefix = db.Column(db.String(500))

    #: The key into `app.services.SECTIONS`. Subclasses override.
    def asset_section(self):
        raise NotImplementedError

    def asset_date(self):
        """The date the prefix is filed under; None means today."""
        return None

    def ensure_asset_prefix(self):
        """Assign a prefix if there is none. Never reassigns.

        A row that already has one keeps it even when its slug or date
        changes later, because objects are already sitting under it and
        rewriting the column would orphan them without moving anything.
        """
        if self.asset_prefix:
            return self.asset_prefix
        self.asset_prefix = content_prefix(
            self.asset_section(), slug=self.slug, when=self.asset_date()
        )
        return self.asset_prefix

    @property
    def asset_prefixes(self):
        """`{"Images": "Images/Portfolio-Site/...", "Video": ..., "Audio": ...}`."""
        return categorised(self.asset_prefix) if self.asset_prefix else {}


def _assign_prefix(mapper, connection, target):
    target.ensure_asset_prefix()


def tracks_assets(cls):
    """Class decorator: give this model a prefix before its first INSERT.

    A before_insert hook rather than a constructor argument, so a row created
    by the admin form, the CLI, a seed script or a test all get one -- the
    user's rule is that *every* new post gets a prefix, and the only place
    that covers every caller is the flush.
    """
    event.listen(cls, "before_insert", _assign_prefix)
    return cls
