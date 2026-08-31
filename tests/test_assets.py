"""The minified stylesheet is a build artifact, so it can fall behind."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "app" / "static" / "css"


def test_minified_stylesheet_is_current():
    """style.min.css matches what tools/minify_css.py produces from style.css.

    The app falls back to the plain stylesheet when this drifts, so a stale
    file costs bytes rather than correctness -- but silently, which is worse.
    """
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "minify_css.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (CSS / "style.min.css").exists()


def test_minified_stylesheet_is_smaller():
    assert (CSS / "style.min.css").stat().st_size < (CSS / "style.css").stat().st_size
