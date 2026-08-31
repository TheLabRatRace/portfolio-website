"""Put a placeholder object under every content prefix in the bucket.

The bucket is empty, which makes it impossible to tell a prefix that is
wrong from one that simply has nothing in it yet. This walks the posts and
projects, uploads one placeholder image under each row's Images prefix, and
points the gallery rows that have no picture at what it uploaded -- so the
site renders from S3 end to end and the bucket shows the layout the code
believes in.

    docker compose exec -T web python tools/seed_s3_placeholders.py --check
    docker compose exec -T web python tools/seed_s3_placeholders.py --dry-run
    docker compose exec -T web python tools/seed_s3_placeholders.py --commit

Nothing is written without --commit. Credentials come from boto3's own chain
(AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY in the environment, ~/.aws, or an
instance role) and never from this repository.

Re-running is safe: an existing placeholder is skipped, and a gallery row
that already has a picture is left alone.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import GalleryImage, Post, Project  # noqa: E402

PLACEHOLDER = (
    Path(__file__).resolve().parent.parent
    / "app" / "static" / "images" / "PRIVATE_1135x.webp"
)
PLACEHOLDER_NAME = "placeholder.webp"


def client(app):
    import boto3

    return boto3.client(
        "s3",
        region_name=app.config["S3_REGION"],
        endpoint_url=app.config["S3_ENDPOINT_URL"] or None,
    )


def check(app, s3):
    """Prove the credentials can read and write before anything is uploaded.

    A run that uploads forty objects and then discovers it cannot set an
    object's ACL leaves the bucket half seeded; failing on the first call is
    cheaper to recover from.
    """
    from botocore.exceptions import ClientError

    bucket = app.config["S3_BUCKET"]
    probe = "Images/Portfolio-Site/.seed-probe"
    try:
        s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        s3.put_object(Bucket=bucket, Key=probe, Body=b"probe")
        s3.delete_object(Bucket=bucket, Key=probe)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "?")
        print(f"FAIL {bucket}: {code} -- the IAM user needs s3:ListBucket on the")
        print("     bucket and s3:PutObject/GetObject/DeleteObject on its objects.")
        return False
    print(f"OK   {bucket}: list, put and delete all succeed")
    return True


def exists(s3, bucket, key):
    from botocore.exceptions import ClientError

    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError:
        return False
    return True


def targets():
    """Every row that owns a prefix, as (label, Images key)."""
    for post in Post.query.order_by(Post.id):
        if post.asset_prefix:
            yield f"post {post.slug}", f"{post.asset_prefixes['Images']}/{PLACEHOLDER_NAME}"
    for project in Project.query.order_by(Project.id):
        if project.asset_prefix:
            yield (
                f"project {project.slug}",
                f"{project.asset_prefixes['Images']}/{PLACEHOLDER_NAME}",
            )


def upload(s3, bucket, key, app):
    extra = {
        "ContentType": "image/webp",
        "CacheControl": app.config["S3_CACHE_CONTROL"],
    }
    if app.config["S3_OBJECT_ACL"]:
        extra["ACL"] = app.config["S3_OBJECT_ACL"]
    with PLACEHOLDER.open("rb") as handle:
        s3.upload_fileobj(handle, bucket, key, ExtraArgs=extra)


def point_gallery_rows(commit):
    """Give every pictureless gallery row its project's placeholder."""
    changed = 0
    for image in GalleryImage.query.filter(GalleryImage.image_path.is_(None)):
        prefix = image.project.asset_prefixes.get("Images") if image.project else None
        if not prefix:
            continue
        image.image_path = f"s3:{prefix}/{PLACEHOLDER_NAME}"
        changed += 1
    if commit and changed:
        db.session.commit()
    else:
        db.session.rollback()
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="probe access and stop")
    parser.add_argument("--dry-run", action="store_true", help="list what would happen")
    parser.add_argument("--commit", action="store_true", help="actually write")
    args = parser.parse_args()

    app = create_app("development")
    with app.app_context():
        if not app.config["S3_BUCKET"]:
            print("S3_BUCKET is unset -- nothing to seed.")
            return 1
        if not PLACEHOLDER.exists():
            print(f"Missing placeholder image: {PLACEHOLDER}")
            return 1

        s3 = client(app)
        if not check(app, s3):
            return 1
        if args.check:
            return 0

        bucket = app.config["S3_BUCKET"]
        uploaded = skipped = 0
        for label, key in targets():
            if exists(s3, bucket, key):
                skipped += 1
                continue
            if args.commit:
                upload(s3, bucket, key, app)
            print(f"{'PUT ' if args.commit else 'WOULD PUT'} {key}  ({label})")
            uploaded += 1

        rows = point_gallery_rows(args.commit)
        verb = "pointed" if args.commit else "would point"
        print(f"\n{uploaded} uploaded, {skipped} already there; {verb} {rows} gallery row(s)")
        if not args.commit:
            print("Nothing was written. Re-run with --commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
