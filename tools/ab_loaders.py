"""A/B the two SQLAlchemy loader strategies against the live V2 database.

A-side  lazy="joined"   -- one statement, every relationship joined together
B-side  selectinload    -- one statement per relationship, no row multiplication

Reports statement count, rows returned, wall time, and whether the two
strategies agree on tag ordering (they only do once Tag has an order_by).

    docker compose exec -T web python tools/ab_loaders.py
"""

import time

from sqlalchemy import event
from sqlalchemy.orm import selectinload

from app import create_app
from app.extensions import db
from app.models import Project


class Recorder:
    """Counts statements and rows for whatever runs inside the `with` block."""

    def __init__(self, engine):
        self.engine = engine
        self.statements = []

    def __enter__(self):
        event.listen(self.engine, "after_cursor_execute", self._record)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "after_cursor_execute", self._record)

    def _record(self, conn, cursor, statement, params, context, executemany):
        self.statements.append((statement, max(cursor.rowcount, 0)))

    @property
    def rows(self):
        return sum(rows for _, rows in self.statements)


def load(strategy):
    """Fetch the published work projects under one loader strategy."""
    query = Project.query.filter_by(type="work", published=True)
    if strategy == "selectin":
        query = query.options(
            selectinload(Project._tags),
            selectinload(Project.gallery_images),
            selectinload(Project.attachments),
        )
    return query.order_by(Project.display_order).all()


def measure(strategy):
    db.session.expire_all()
    db.session.close()
    with Recorder(db.engine) as rec:
        start = time.perf_counter()
        projects = load(strategy)
        # Touch every relationship the template touches, so lazy work is paid here.
        snapshot = {
            p.slug: (
                list(p.tags),
                [g.label for g in p.gallery_images],
                [a.name for a in p.attachments],
            )
            for p in projects
        }
        elapsed = (time.perf_counter() - start) * 1000
    return {
        "ms": elapsed,
        "statements": rec.statements,
        "rows": rec.rows,
        "count": len(projects),
        "snapshot": snapshot,
    }


def shape(statement):
    """Collapse a SQL statement to its FROM/JOIN skeleton."""
    words, parts = statement.split(), []
    for i, word in enumerate(words):
        upper = word.upper()
        if upper in ("FROM", "JOIN") and i + 1 < len(words):
            parts.append(f"{upper} {words[i + 1]}")
    return "  ".join(parts) or statement[:70]


def report(label, result):
    print(f"\n{label}")
    print(f"  {'projects':<14}{result['count']}")
    print(f"  {'statements':<14}{len(result['statements'])}")
    print(f"  {'rows returned':<14}{result['rows']:,}")
    print(f"  {'wall time':<14}{result['ms']:.1f} ms")
    for i, (statement, rows) in enumerate(result["statements"], 1):
        print(f"    {i}. {rows:>7,} rows   {shape(statement)}")


def main():
    app = create_app("production")
    with app.app_context():
        # Warm the connection pool and query cache so neither side pays setup cost.
        measure("joined")
        measure("selectin")

        a = measure("joined")
        b = measure("selectin")

        report('A-SIDE   lazy="joined"  (current)', a)
        report("B-SIDE   selectinload   (proposed)", b)

        print("\nDIFFERENCE")
        print(f"  rows      {a['rows']:,} -> {b['rows']:,}"
              f"   ({a['rows'] / max(b['rows'], 1):.0f}x fewer)")
        print(f"  time      {a['ms']:.1f} ms -> {b['ms']:.1f} ms"
              f"   ({a['ms'] / max(b['ms'], 0.01):.1f}x faster)")

        differing = [
            slug for slug, (tags, _, _) in a["snapshot"].items()
            if tags != b["snapshot"][slug][0]
        ]
        same_set = all(
            sorted(a["snapshot"][s][0]) == sorted(b["snapshot"][s][0])
            for s in differing
        )
        print("\nOUTPUT EQUALITY")
        if differing:
            print(f"  MISMATCH  {len(differing)} of {a['count']} projects "
                  f"disagree on tag ORDER")
            print(f"            same tag set every time: {same_set}")
            slug = differing[0]
            print(f"    e.g. {slug}")
            print(f"      A: {a['snapshot'][slug][0][:4]}")
            print(f"      B: {b['snapshot'][slug][0][:4]}")
            print("      -> the template renders tags[:3], so the visible tags change")
        else:
            print(f"  IDENTICAL  all {a['count']} projects agree on tags, "
                  "gallery, and attachments")


if __name__ == "__main__":
    main()
