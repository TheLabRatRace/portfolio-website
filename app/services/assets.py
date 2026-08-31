"""Where an asset lives in S3, decided in exactly one place.

The bucket is organised `<Category>/<Application>/<Section>/...`, so one
bucket can serve more than this site and a category is never mixed with
another. `Images/Portfolio-Site/Blog/...` and `Video/Portfolio-Site/Blog/...`
are the same shelf in two different rooms.

Content that has its own page -- a post, a project -- gets a dated prefix
under its section:

    Images/Portfolio-Site/Blog/2026/08/30/gpu-passthrough-proxmox/
    Images/Portfolio-Site/Projects/Work/2026/08/30/splunk-pipeline/

The date comes first so a prefix listing is chronological without a sort,
and the slug comes last so two posts published the same day cannot collide.
S3 has no directories -- a key is one flat string -- which is why "if the
day already exists, put the post under it" needs no check: writing
`.../08/30/second-post/cover.webp` puts it beside the first post's folder
because the two keys share a prefix, not because a directory was created.

Pages without their own slug (Home, Contact) take the section alone; there
is one set of images for the page and a date on them would be noise.
"""

import posixpath
import re
from datetime import date as date_cls

# The application segment. One bucket, many apps, this is ours.
APPLICATION = "Portfolio-Site"

# Category is chosen by extension rather than declared by the caller: the
# caller always knows the file, and does not always know the taxonomy.
CATEGORY_EXTENSIONS = {
    "Images": {".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".avif"},
    "Video": {".mp4", ".webm", ".mov", ".m4v"},
    "Audio": {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"},
}

# The sections under an application, and whether content there is dated.
# Project-Gallery is listed because the bucket has one and an upload may be
# aimed at it directly, but a project's own images belong under the section
# matching its type -- the gallery page is a view over Work and SideQuests,
# not a third place to store the same file twice.
SECTIONS = {
    "blog": (("Blog",), True),
    "work": (("Projects", "Work"), True),
    "sidequest": (("Projects", "SideQuests"), True),
    "gallery": (("Projects", "Project-Gallery"), True),
    "home": (("Home",), False),
    "contact": (("Contact",), False),
}

# Project.type is the site's word for it; the bucket uses its own names.
PROJECT_TYPE_SECTIONS = {"work": "work", "sidequest": "sidequest"}

_SLUG_SAFE = re.compile(r"[^a-z0-9._-]+")


class AssetKeyError(ValueError):
    """A key could not be built from what the caller supplied."""


def category_for(filename):
    """`Images`, `Video` or `Audio` for a filename, or None if unrecognised.

    Unrecognised is a refusal rather than a default: a file that lands in the
    wrong category is worse than one that never uploads, because the first is
    only noticed months later by someone browsing the bucket.
    """
    ext = posixpath.splitext(str(filename).lower())[1]
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if ext in extensions:
            return category
    return None


def section_for_project(project_type):
    """The section key for a Project.type value."""
    return PROJECT_TYPE_SECTIONS.get((project_type or "").lower())


def safe_segment(value):
    """One path segment, reduced to what is safe in a key and a URL.

    S3 accepts almost anything in a key, which is the problem: a space, a
    quote or a `../` in a title reaches a URL and a shell eventually. Slugs
    from the database are already tame; this exists for the ones that are not.
    """
    segment = _SLUG_SAFE.sub("-", str(value).strip().lower()).strip("-._")
    if not segment or segment in {".", ".."}:
        raise AssetKeyError(f"{value!r} does not reduce to a usable segment")
    return segment[:120]


def content_prefix(section, *, slug=None, when=None):
    """Everything after the category: `Portfolio-Site/Blog/2026/08/30/slug`.

    This is the half that identifies the content rather than the file type,
    which is why it is the half stored on the row. One column then answers
    for all three categories -- prepend `Images/`, `Video/` or `Audio/` --
    instead of three columns that can drift apart.

    `when` defaults to today for a dated section. Passing the content's own
    date keeps a post's assets with the post when it is backdated, which is
    the only reason the argument exists.
    """
    try:
        parts, dated = SECTIONS[section]
    except KeyError:
        raise AssetKeyError(f"unknown section {section!r}") from None

    segments = [APPLICATION, *parts]
    if dated:
        when = when or date_cls.today()
        segments += [f"{when.year:04d}", f"{when.month:02d}", f"{when.day:02d}"]
        if slug is None:
            raise AssetKeyError(f"section {section!r} is dated and needs a slug")
        segments.append(safe_segment(slug))
    elif slug:
        segments.append(safe_segment(slug))
    return "/".join(segments)


def build_prefix(category, section, *, slug=None, when=None):
    """The full prefix (no trailing slash) an asset for this content sits under."""
    if category not in CATEGORY_EXTENSIONS:
        raise AssetKeyError(f"unknown category {category!r}")
    return f"{category}/{content_prefix(section, slug=slug, when=when)}"


def categorised(prefix):
    """The three full prefixes for one stored `content_prefix` value."""
    return {category: f"{category}/{prefix}" for category in CATEGORY_EXTENSIONS}


def build_key(filename, section, *, slug=None, when=None, category=None):
    """The full object key for a file. Category is inferred from the name."""
    category = category or category_for(filename)
    if category is None:
        raise AssetKeyError(f"no asset category for {filename!r}")
    prefix = build_prefix(category, section, slug=slug, when=when)
    return f"{prefix}/{safe_segment(filename)}"


def prefixes_for(section, *, slug=None, when=None):
    """Every category's prefix for one piece of content.

    A post gets an Images prefix, a Video prefix and an Audio prefix at once.
    They cost nothing until something is written to them, and having all three
    recorded when the post is created is what makes the bucket predictable
    rather than a place where folders appear as people happen to need them.
    """
    return categorised(content_prefix(section, slug=slug, when=when))
