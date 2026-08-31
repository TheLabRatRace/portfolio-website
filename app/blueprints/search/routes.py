"""The search page.

Everything about how the search actually runs -- the tsquery grammar, the
ranking, the eager-load overrides that keep it to five round trips -- lives in
app/services/search.py, because the JSON API runs the same search. This module
is the HTML view over it and nothing else.
"""

from flask import render_template, request

from app.blueprints.search import search_bp
from app.services.search import LIMIT, run_search


# "" rather than "/", so the canonical URL is /search?q= -- the spelling people
# type and paste. strict_slashes=False lets /search/ answer as well.
@search_bp.route("", strict_slashes=False)
def index():
    raw = (request.args.get("q") or "").strip()
    results, total, too_short = run_search(raw)

    return render_template(
        "search/results.html",
        active_section="search",
        q=raw,
        results=results,
        total=total,
        too_short=too_short,
        limit=LIMIT,
    )
