"""Point the generated gallery rows at real image files.

seed_stress.py only fills image_path when it is given --image-files, so a
default stress run leaves every generated GalleryImage with a NULL path and
the gallery tab renders 600 placeholder tiles. That is fine for measuring row
cost and useless for looking at responsive images: srcset cannot be checked
against a placeholder.

This attaches the files already in app/static/images/<dir> to those rows, in
a stable rotation so the same row keeps the same picture across runs.

    docker compose exec -T web python tools/backfill_image_paths.py
    docker compose exec -T web python tools/backfill_image_paths.py --clear

Only rows belonging to generated projects are touched -- the real portfolio
entries from migrate.sql keep whatever they have, including nothing.
"""

import argparse
import os
import re
from pathlib import Path

import psycopg2

SLUG_PREFIX = "stress-"
IMAGE_ROOT = Path(__file__).resolve().parent.parent / "app" / "static" / "images"
VARIANT_RE = re.compile(r"-\d+w$")


def available(subdir):
    """Source images under `subdir`, ignoring generated width variants."""
    base = IMAGE_ROOT / subdir
    return sorted(
        p.relative_to(IMAGE_ROOT).as_posix()
        for p in base.glob("*.webp")
        if not VARIANT_RE.search(p.stem)
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="stress",
                    help="subdirectory of app/static/images to draw from")
    ap.add_argument("--clear", action="store_true",
                    help="set the generated rows back to NULL")
    args = ap.parse_args()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    if args.clear:
        cur.execute(
            "UPDATE gallery_images g SET image_path = NULL, thumbnail_path = NULL "
            "FROM projects p WHERE p.id = g.project_id AND p.slug LIKE %s",
            (SLUG_PREFIX + "%",),
        )
        conn.commit()
        print(f"cleared {cur.rowcount} generated gallery rows")
        return

    files = available(args.dir)
    if not files:
        raise SystemExit(f"no source images in app/static/images/{args.dir}")

    # Rotating by row_number rather than by id keeps the assignment stable and
    # even; id % n would clump wherever the id sequence has gaps.
    cur.execute(
        """
        WITH ordered AS (
            SELECT g.id, row_number() OVER (ORDER BY g.id) - 1 AS n
            FROM gallery_images g
            JOIN projects p ON p.id = g.project_id
            WHERE p.slug LIKE %s
        )
        UPDATE gallery_images g
        SET image_path = f.path, thumbnail_path = f.path
        FROM ordered o
        JOIN LATERAL (SELECT (%s::text[])[(o.n %% %s) + 1] AS path) f ON TRUE
        WHERE g.id = o.id
        """,
        (SLUG_PREFIX + "%", files, len(files)),
    )
    conn.commit()
    print(f"attached {len(files)} image(s) to {cur.rowcount} generated gallery rows")


if __name__ == "__main__":
    main()
