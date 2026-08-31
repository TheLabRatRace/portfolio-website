"""Reading and writing assets, over S3 or the local static directory.

Two backends behind one interface, chosen by configuration:

* **s3** -- what production uses. Objects go to the bucket under the key
  `assets.build_key` decided, and the database stores `s3:<key>`.
* **local** -- what a checkout with no AWS credentials uses, including CI.
  Files go to `static/images/uploads/` and the database stores a bare
  relative path, exactly as it did before this module existed.

The `s3:` marker on the stored value is what lets one column hold both. A
row written before S3 existed is a bare path and still resolves; a row
written after is a URI and resolves through the bucket. No migration of
existing data, no second column to keep in step, and `resolve()` is the one
place that has to know the difference.
"""

import posixpath
import secrets
from pathlib import Path
from urllib.parse import quote

from flask import current_app

from app.services.assets import AssetKeyError, category_for, safe_segment

S3_SCHEME = "s3:"


class StorageError(RuntimeError):
    """An asset could not be stored."""


def is_s3_uri(value):
    return bool(value) and str(value).startswith(S3_SCHEME)


def key_of(value):
    """The bucket key inside an `s3:` URI."""
    return str(value)[len(S3_SCHEME):] if is_s3_uri(value) else None


def backend():
    """`"s3"` or `"local"`, from config."""
    return "s3" if current_app.config.get("S3_BUCKET") else "local"


def _client():
    """A boto3 S3 client, built on first use.

    Credentials come from the standard boto3 chain -- environment, shared
    config, instance role -- and never from this repository. Building the
    client lazily keeps `import app` working on a machine that has no
    credentials at all, which is every test run.
    """
    import boto3  # imported here so the dependency is optional at import time

    cfg = current_app.config
    return boto3.client(
        "s3",
        region_name=cfg.get("S3_REGION"),
        endpoint_url=cfg.get("S3_ENDPOINT_URL") or None,
    )


# ── writing ──────────────────────────────────────────────────────────────

def save(storage, key):
    """Store an uploaded file at `key`; return the value to put in the database.

    `storage` is a Werkzeug FileStorage. The return is an `s3:` URI on the S3
    backend and a static-relative path on the local one -- callers store it and
    hand it back to `resolve()` without caring which.
    """
    if backend() == "local":
        return _save_local(storage, key)
    return _save_s3(storage, key)


def _save_local(storage, key):
    """Write under static/images/uploads/, keeping only the key's filename.

    The dated prefix is an S3 idea. Reproducing it on disk would create deep
    empty trees in every checkout for no gain, so the local backend keeps its
    flat directory and the random name that already made collisions
    impossible.
    """
    name = posixpath.basename(key)
    ext = Path(name).suffix.lower()
    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    local_name = f"{secrets.token_hex(8)}{ext}"
    storage.save(upload_dir / local_name)
    return f"{current_app.config['UPLOAD_SUBDIR']}/{local_name}"


def _save_s3(storage, key):
    from botocore.exceptions import BotoCoreError, ClientError

    extra = {"ContentType": storage.mimetype or "application/octet-stream"}
    # Cache hard: every key carries a random component in its filename, so a
    # given key's bytes never change. A new upload is a new key.
    extra["CacheControl"] = current_app.config["S3_CACHE_CONTROL"]
    if current_app.config.get("S3_OBJECT_ACL"):
        extra["ACL"] = current_app.config["S3_OBJECT_ACL"]

    storage.stream.seek(0)
    try:
        _client().upload_fileobj(
            storage.stream, current_app.config["S3_BUCKET"], key, ExtraArgs=extra
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(f"upload of {key!r} failed: {exc}") from exc
    return f"{S3_SCHEME}{key}"


def delete(value):
    """Remove a stored asset. Returns True if the backend reported success.

    Deliberately not called when a row is deleted: two rows may point at the
    same key, and an image that is gone from the bucket is unrecoverable
    while a row that still points at a live object is not. This exists for
    the caller that knows it owns the object.
    """
    if not value:
        return False
    if not is_s3_uri(value):
        path = Path(current_app.config["UPLOAD_DIR"]).parent / str(value).lstrip("/")
        try:
            path.unlink()
        except OSError as exc:
            current_app.logger.warning("delete failed for %s: %s", value, exc)
            return False
        return True

    from botocore.exceptions import BotoCoreError, ClientError

    try:
        _client().delete_object(
            Bucket=current_app.config["S3_BUCKET"], Key=key_of(value)
        )
    except (BotoCoreError, ClientError) as exc:
        current_app.logger.warning("delete failed for %s: %s", value, exc)
        return False
    return True


def unique_filename(original):
    """`<token>-<original>`, so two uploads named cover.webp coexist.

    The token is a prefix rather than the whole name because a key is also
    something a person reads in the S3 console; `a1b2c3d4-cover.webp` says
    what it is and `a1b2c3d4.webp` does not.
    """
    name = safe_segment(original or "file")
    if category_for(name) is None:
        raise AssetKeyError(f"{original!r} is not an image, video or audio file")
    return f"{secrets.token_hex(4)}-{name}"


# ── reading ──────────────────────────────────────────────────────────────

def resolve(value):
    """The URL for a stored asset value, whichever backend wrote it.

    Bare paths are static files. `s3:` URIs become a public URL when one is
    configured -- a CDN, or a bucket that allows anonymous reads -- and a
    presigned URL otherwise, because a private bucket is the default a new
    bucket has and a broken image is a bad way to discover it.
    """
    if not value:
        return ""
    if not is_s3_uri(value):
        # static_url, not url_for: when STATIC_BASE_URL is set these bytes come
        # from the CDN in front of the static bucket, not from this process.
        return current_app.extensions["static_url"]("images/" + str(value).lstrip("/"))

    key = key_of(value)
    base = current_app.config.get("S3_PUBLIC_BASE_URL")
    if base:
        return f"{base.rstrip('/')}/{quote(key)}"
    return presigned_url(key)


def presigned_url(key):
    """A time-limited GET URL for a private object.

    Correct but not free: the URL is unique per signature, so a browser cache
    and a CDN both miss on every page load. Set S3_PUBLIC_BASE_URL for
    anything a visitor loads repeatedly.
    """
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": current_app.config["S3_BUCKET"], "Key": key},
            ExpiresIn=current_app.config["S3_URL_EXPIRY_SECONDS"],
        )
    except (BotoCoreError, ClientError) as exc:
        current_app.logger.warning("presign failed for %s: %s", key, exc)
        return ""
