import hashlib
import json
import logging
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, request

from config import assert_secret_key_is_safe, config


def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Before anything else: an app whose session cookies are forgeable has no
    # admin boundary at all, so it must not get as far as serving a request.
    assert_secret_key_is_safe(config_name, app.config.get("SECRET_KEY"))

    _register_extensions(app)

    # Jinja caches compiled templates independently of gunicorn --reload, so
    # without this a template edit is invisible until the container restarts.
    app.config["TEMPLATES_AUTO_RELOAD"] = app.config["DEV_RELOAD"]

    _setup_compression(app)

    _setup_logging(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_template_filters(app)
    _register_image_variants(app)
    _register_asset_urls(app)
    _register_stylesheet(app)
    _register_hooks(app)
    _register_context(app)
    _register_cli(app)

    app.logger.info("App created with config: %s", config_name)
    return app


def _register_extensions(app):
    """Bind the unbound singletons to this app.

    Order is not significant, but every extension must be here: a missing
    init_app() does not raise, it fails later at the first request that needs it.
    """
    from app.extensions import csrf, db, login_manager

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Registers every mapper up front, so no query can hit a relationship whose
    # target class has not been imported yet.
    with app.app_context():
        import app.models  # noqa: F401


def _setup_compression(app):
    """gzip text responses in-process. Images and fonts are already compressed
    and are left alone -- re-compressing them burns CPU to add bytes.
    """
    from flask_compress import Compress

    app.config.setdefault("COMPRESS_MIMETYPES", [
        "text/html",
        "text/css",
        "text/xml",
        "application/json",
        "application/javascript",
        "text/javascript",
        "image/svg+xml",
    ])
    # Static files are served as streams, and the streaming algorithm list
    # ships without gzip -- so a client that advertises only gzip gets the
    # stylesheet uncompressed. Every modern browser asks for br, but the ones
    # that do not are exactly the ones that can least afford 44KB.
    app.config.setdefault("COMPRESS_ALGORITHM_STREAMING", ["zstd", "br", "gzip", "deflate"])
    app.config.setdefault("COMPRESS_LEVEL", 6)
    # Brotli's default level 4 loses to gzip on this stylesheet. 7 wins by
    # 1.1KB and still costs under a millisecond; 11 saves another 500 bytes
    # and costs 30ms, which is not a trade worth making without a cache.
    app.config.setdefault("COMPRESS_BR_LEVEL", 7)
    app.config.setdefault("COMPRESS_MIN_SIZE", 500)
    Compress(app)


def _setup_logging(app):
    log_dir = Path(app.config["LOG_DIR"])
    log_dir.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.DEBUG)

    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)

    logging.getLogger("werkzeug").addHandler(file_handler)


def _register_blueprints(app):
    from app.blueprints.admin import admin_bp
    from app.blueprints.main import main_bp
    from app.blueprints.blog import blog_bp
    from app.blueprints.projects import projects_bp
    from app.blueprints.search import search_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(blog_bp, url_prefix="/blog")
    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(admin_bp, url_prefix="/admin")


def _register_error_handlers(app):
    from flask import render_template

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        app.logger.error("500 error: %s", error)
        return render_template("errors/500.html"), 500


def _register_template_filters(app):
    @app.template_filter("slugify")
    def slugify_filter(s):
        s = str(s).lower()
        s = re.sub(r"[^a-z0-9]+", "-", s)
        return s.strip("-")

    @app.template_filter("format_date")
    def format_date_filter(date_str):
        d = datetime.strptime(str(date_str), "%Y-%m-%d")
        return d.strftime("%B %d, %Y")


def _register_image_variants(app):
    """Expose the srcset ladder that tools/gen_image_variants.py wrote.

    A gallery card is ~347 CSS px wide and the sources are 1135px, so the
    360px variant is the right file for a phone. The manifest is a build
    artifact, so it is read once at startup. An image with no entry yields an
    empty string and the template's plain `src` still serves it.
    """
    from flask import url_for

    manifest_path = Path(app.static_folder) / "images" / "variants.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, ValueError):
        manifest = {}
        app.logger.info("No image variant manifest -- srcset disabled")
    else:
        app.logger.info("Image variants: %d image(s)", len(manifest))

    @app.template_global("image_srcset")
    def image_srcset(rel_path):
        widths = manifest.get(rel_path)
        # One candidate is not a choice; `srcset` would just repeat `src`.
        if not widths or len(widths) < 2:
            return ""
        stem, _, ext = rel_path.rpartition(".")
        source_width = widths[-1]
        parts = []
        for width in widths:
            # The widest candidate is the source; the tool never upscales.
            name = rel_path if width == source_width else f"{stem}-{width}w.{ext}"
            url = url_for("static", filename="images/" + name)
            parts.append(f"{url} {width}w")
        return ", ".join(parts)


def _register_asset_urls(app):
    """One way to turn a stored asset value into a URL.

    Templates used to write `url_for('static', filename='images/' + path)` in
    five places, which was correct while every image was a file in this repo.
    An asset in S3 is not, so the join moved behind a name: `asset_url(path)`
    resolves a bare path to the static file it always was, and an `s3:` URI to
    the bucket. Adding a third backend later is one function, not five
    templates.
    """
    from app.services import resolve

    app.add_template_global(resolve, name="asset_url")
    app.logger.info("Asset storage: %s", app.config.get("S3_BUCKET") or "local")


def _register_stylesheet(app):
    """Point every page at the minified stylesheet, fingerprinted.

    tools/minify_css.py writes style.min.css -- half the transferred bytes of
    the source, same 1670 rules. It is a build artifact, so a stale one is
    possible: when it is older than the file it came from the plain stylesheet
    is served instead. Bigger, never wrong.

    The digest is what makes the one-day max-age on static safe. Without it a
    returning visitor keeps yesterday's CSS for a day after a deploy.
    """
    from flask import url_for

    css_dir = Path(app.static_folder) / "css"
    source, minified = css_dir / "style.css", css_dir / "style.min.css"

    chosen = source
    if not app.config["DEV_RELOAD"] and minified.exists():
        if minified.stat().st_mtime >= source.stat().st_mtime:
            chosen = minified
        else:
            app.logger.warning("style.min.css is stale -- run tools/minify_css.py")
    digest = hashlib.sha256(chosen.read_bytes()).hexdigest()[:8]
    app.logger.info("Stylesheet: %s (%d bytes)", chosen.name, chosen.stat().st_size)

    @app.template_global("stylesheet_url")
    def stylesheet_url():
        return url_for("static", filename=f"css/{chosen.name}", v=digest)


def _register_cli(app):
    from app.cli import register_cli

    register_cli(app)


def _register_context(app):
    @app.context_processor
    def display_flags():
        """`?title=off` flips the heading for one request, so both versions can
        be compared without a restart. SHOW_PAGE_TITLE stays the real default.
        """
        show = app.config["SHOW_PAGE_TITLE"]
        override = request.args.get("title")
        if override is not None:
            show = override.lower() not in ("0", "false", "off", "no")
        return {"show_page_title": show}


def _register_hooks(app):
    @app.after_request
    def set_cache_headers(response):
        """Give every response a validator so a repeat visit can get a 304.

        HTML is revalidated per request -- no-cache means "ask first", not "do
        not store". Static assets carry an mtime ETag and are held for a day.
        """
        if response.direct_passthrough or response.status_code >= 400:
            return response

        if request.endpoint == "static":
            # In dev a day of caching means every CSS edit needs a force-reload.
            # The ETag is set either way, so dev still gets 304s -- after asking.
            max_age = "no-cache" if app.config["DEV_RELOAD"] else "public, max-age=86400"
            response.headers.setdefault("Cache-Control", max_age)
            return response

        response.headers.setdefault("Cache-Control", "no-cache")
        response.add_etag()
        return response.make_conditional(request)

    @app.after_request
    def log_request(response):
        app.logger.info(
            "%s %s %s — %d",
            request.method,
            request.path,
            request.remote_addr,
            response.status_code,
        )
        return response
