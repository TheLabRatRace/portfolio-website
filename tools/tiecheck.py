"""Show what paginating on a non-unique ORDER BY key actually costs."""
from collections import Counter

from app import create_app
from app.models import Project


def paged(order, per=10):
    out, page = [], 1
    q = Project.query.filter_by(type="work", published=True).order_by(*order)
    while True:
        c = q.paginate(page=page, per_page=per, error_out=False)
        if not c.items:
            break
        out += [p.slug for p in c.items]
        if not c.has_next:
            break
        page += 1
    return out


def main():
    app = create_app("production")
    with app.app_context():
        total = Project.query.filter_by(type="work", published=True).count()
        for label, order in [
            ("ORDER BY display_order", (Project.display_order.asc(),)),
            ("ORDER BY created_at DESC", (Project.created_at.desc(),)),
            ("ORDER BY created_at DESC, id DESC",
             (Project.created_at.desc(), Project.id.desc())),
        ]:
            counts = Counter(paged(order))
            dupes = sum(n - 1 for n in counts.values() if n > 1)
            print(f"\n{label}")
            print(f"  distinct rows seen across all pages  {len(counts)} / {total}")
            print(f"  rows shown twice                     {dupes}")
            print(f"  rows never shown                     {total - len(counts)}")


if __name__ == "__main__":
    main()
