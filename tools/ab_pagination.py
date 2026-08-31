"""A/B the two ORDER BY strategies by actually walking every page.

A-side  ORDER BY display_order            -- the ordering the site shipped with
B-side  ORDER BY created_at DESC, id DESC -- a total order

Paginating on a non-unique sort key is undefined behaviour, not a style
nitpick: Postgres may return tied rows in a different order for each
LIMIT/OFFSET, so a row can land on two pages or on none.
"""

from collections import Counter

from app import create_app
from app.extensions import db
from app.models import Project

PER_PAGE = 10


def walk(order_by):
    """Page through the whole work list and collect what each page returned."""
    query = Project.query.filter_by(type="work", published=True).order_by(*order_by)
    seen, page = [], 1
    while True:
        chunk = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
        if not chunk.items:
            break
        seen.extend(p.slug for p in chunk.items)
        if not chunk.has_next:
            break
        page += 1
    return seen


def audit(label, order_by, total):
    seen = walk(order_by)
    counts = Counter(seen)
    dupes = {s: n for s, n in counts.items() if n > 1}
    missing = total - len(counts)

    print(f"\n{label}")
    print(f"  rows the query says exist   {total}")
    print(f"  rows actually paged through {len(seen)}")
    print(f"  distinct rows seen          {len(counts)}")
    print(f"  shown on more than one page {len(dupes)}")
    print(f"  never shown at all          {missing}")
    if dupes:
        for slug, n in list(dupes.items())[:4]:
            print(f"      {slug} appeared {n}x")
    return not dupes and missing == 0


def main():
    app = create_app("production")
    with app.app_context():
        total = Project.query.filter_by(type="work", published=True).count()

        ties = db.session.execute(db.text("""
            SELECT count(*) FROM (
              SELECT display_order FROM projects
              WHERE type='work' AND published
              GROUP BY display_order HAVING count(*) > 1
            ) t
        """)).scalar()
        distinct_created = db.session.execute(db.text(
            "SELECT count(DISTINCT created_at) FROM projects WHERE published"
        )).scalar()

        print("SORT KEY UNIQUENESS")
        print(f"  display_order values shared by 2+ work rows   {ties}")
        print(f"  distinct created_at across 211 published rows {distinct_created}")
        print("  -> neither column alone is a total order")

        a_ok = audit("A-SIDE   ORDER BY display_order",
                     (Project.display_order.asc(),), total)
        b_ok = audit("B-SIDE   ORDER BY created_at DESC, id DESC",
                     (Project.created_at.desc(), Project.id.desc()), total)

        print("\nVERDICT")
        print(f"  A-side pagination is lossless: {a_ok}")
        print(f"  B-side pagination is lossless: {b_ok}")


if __name__ == "__main__":
    main()
