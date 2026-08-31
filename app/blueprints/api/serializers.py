"""Model rows to JSON-safe dicts.

Two rules run through all of it:

  * Every image path goes through services.resolve(), so what a client gets is
    a URL it can fetch -- a CloudFront object, an S3 object, or a static file
    -- and never the `s3:` URI the column happens to hold. A client should not
    have to know where the bytes live.
  * A list serializer and a detail serializer are different functions, not one
    function with a flag. The list endpoints deliberately skip the
    relationships that the list queries deliberately did not load; sharing one
    serializer is how a page turns into fourteen round trips again.
"""

from app.services import resolve


def _iso(value):
    return value.isoformat() if value is not None else None


def _image(path):
    """A stored asset path as a fetchable URL. None stays None -- a missing
    image is an absent field, not an empty string that renders as a broken
    <img>."""
    return resolve(path) if path else None


def tag(row):
    return {"name": row.name, "slug": row.slug}


def gallery_image(row, *, with_project=False):
    data = {
        "id": row.id,
        "label": row.label,
        "url": _image(row.image_path),
        "thumbnail_url": _image(row.thumbnail_path),
        "display_order": row.display_order,
    }
    if with_project:
        data["project"] = {"slug": row.project.slug, "title": row.project.title}
    return data


def attachment(row):
    """A document or a download.

    `url` is the stored value put through resolve() like any other asset: the
    column holds a path or an `s3:` URI depending on where the file was saved,
    and a client should get something it can fetch either way.
    """
    return {
        "id": row.id,
        "name": row.name,
        "category": row.category,
        "url": _image(row.url),
        "file_type": row.file_type,
        "file_size": row.file_size,
        "display_order": row.display_order,
    }


def project_summary(row):
    """What a card shows. No gallery, no attachments -- see the module note."""
    return {
        "slug": row.slug,
        "url": row.public_path,
        "title": row.title,
        "type": row.type,
        "category": row.category,
        "status": row.status,
        "description": row.description,
        "tags": row.tags,
        "display_order": row.display_order,
        "created_at": _iso(row.created_at),
    }


def project_detail(row):
    data = project_summary(row)
    data.update(
        {
            "long_description": row.long_description,
            "specs": list(row.specs or []),
            "gallery": [gallery_image(i) for i in row.gallery],
            "documents": [attachment(a) for a in row.documents],
            "downloads": [attachment(a) for a in row.downloads],
            "updated_at": _iso(row.updated_at),
        }
    )
    return data


def post_summary(row):
    return {
        "slug": row.slug,
        "url": row.public_path,
        "title": row.title,
        "excerpt": row.excerpt,
        "date": _iso(row.date),
        "tags": row.tags,
    }


def post_detail(row):
    data = post_summary(row)
    data["content"] = row.content
    data["updated_at"] = _iso(row.updated_at)
    return data


def skill(row):
    return {
        "name": row.name,
        "category": row.category,
        "display_order": row.display_order,
    }


def certification(row):
    return {
        "name": row.name,
        "issuer": row.issuer,
        "status": row.status,
        "year": row.year,
        "display_order": row.display_order,
    }
