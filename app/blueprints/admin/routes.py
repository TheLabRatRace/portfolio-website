"""The admin area: everything that writes to the database lives here.

Three rules hold across every route:

  * `login_required` is applied once to the whole blueprint by the
    before_request hook below, so a route added later is protected by default.
  * Reads are GET, writes are POST, and every POST carries a CSRF token by way
    of a Flask-WTF form. There are no destructive GETs.
  * A save either commits or rolls back and says why.
"""

from datetime import datetime, timezone
from pathlib import Path

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_user, logout_user
from werkzeug.utils import secure_filename

from app import services as assets
from app.blueprints.admin import admin_bp
from app.blueprints.admin.forms import (
    AttachmentForm,
    CertificationForm,
    ConfirmForm,
    GalleryImageForm,
    LoginForm,
    PostForm,
    ProjectForm,
    SkillForm,
    TagForm,
    UniqueSlug,
    slugify,
)
from app.extensions import db
from app.models import (
    Attachment,
    Certification,
    GalleryImage,
    Post,
    Project,
    Skill,
    Tag,
    User,
)

PER_PAGE = 25

# Login is the one route an anonymous visitor must reach; static is served
# by the app in development and would otherwise 302 the stylesheet.
PUBLIC_ENDPOINTS = {"admin.login"}


@admin_bp.before_request
def require_login():
    """Gate the whole blueprint, so the default for a new route is protected
    and the only way to expose one is to name it above.
    """
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if not current_user.is_admin:
        abort(403)
    return None


# ── Auth ─────────────────────────────────────────────────────────────────

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        # One message for both failure modes: "wrong password" confirms the
        # username to an attacker and tells a real admin nothing new.
        if user is None or not user.check_password(form.password.data):
            flash("Wrong username or password.", "error")
            current_app.logger.warning(
                "Failed admin login for %r from %s",
                form.username.data, request.remote_addr,
            )
        else:
            login_user(user, remember=form.remember.data)
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
            current_app.logger.info("Admin login: %s", user.username)
            return redirect(_safe_next() or url_for("admin.dashboard"))

    return render_template("admin/login.html", form=form, hide_chrome=True)


@admin_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("Signed out.", "success")
    return redirect(url_for("admin.login"))


def _safe_next():
    """Honour ?next= only when it points back into this site: an open redirect
    turns the login page into a phishing link with a real domain and a real
    certificate. A path with no scheme and no host cannot leave.
    """
    target = request.args.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return target
    return None


# ── Dashboard ────────────────────────────────────────────────────────────

@admin_bp.route("/")
def dashboard():
    counts = {
        "work": Project.query.filter_by(type="work").count(),
        "sidequests": Project.query.filter_by(type="sidequest").count(),
        "gallery": GalleryImage.query.count(),
        "posts": Post.query.count(),
        "tags": Tag.query.count(),
        "skills": Skill.query.count(),
        "certifications": Certification.query.count(),
    }
    drafts = {
        "projects": Project.query.filter_by(published=False).count(),
        "posts": Post.query.filter_by(published=False).count(),
    }
    recent = Project.query.order_by(Project.updated_at.desc()).limit(5).all()
    return render_template(
        "admin/dashboard.html", counts=counts, drafts=drafts, recent=recent
    )


# ── Shared helpers ───────────────────────────────────────────────────────

def _sync_tags(obj, raw):
    """Set obj._tags from a comma-separated string, creating what is missing.

    Matched by slug rather than typed text, so "GPU Passthrough" and "gpu
    passthrough" resolve to one row rather than two that render identically.
    """
    names = [part.strip() for part in (raw or "").split(",")]
    names = [n for n in names if n]
    tags = []
    for name in names:
        slug = slugify(name)
        if not slug:
            continue
        tag = Tag.query.filter_by(slug=slug).first()
        if tag is None:
            tag = Tag(name=name, slug=slug)
            db.session.add(tag)
            # Flush, not commit: the tag needs an id for the association row,
            # but it must still roll back with everything else if the save fails.
            db.session.flush()
        tags.append(tag)
    obj._tags = tags


def _commit(what):
    """Commit, or roll back and report. Never leave the session dirty."""
    try:
        db.session.commit()
    except Exception as exc:  # noqa: BLE001 -- the message is for a human, not a handler
        db.session.rollback()
        current_app.logger.exception("Admin save failed: %s", what)
        flash(f"Could not save: {exc.__class__.__name__}", "error")
        return False
    flash(f"{what} saved.", "success")
    return True


def _save_upload(storage, owner=None):
    """Store an uploaded image and return the value to put in the database.

    `owner` is the post or project the image belongs to; its `asset_prefix`
    decides where in the bucket the object lands, so an image uploaded on a
    project's page is filed under that project. Without an owner the upload
    goes to the section's undated prefix, which is what the general uploads
    on Home and Contact want.

    The return is an `s3:` URI or a static-relative path depending on the
    configured backend -- the caller stores whichever it gets and hands it
    to `asset_url()` to render.
    """
    if not storage or not storage.filename:
        return None
    original = secure_filename(storage.filename)
    ext = Path(original).suffix.lower()
    if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        flash(f"Refused {original!r}: {ext or 'no extension'} is not an image.", "error")
        return None

    try:
        name = assets.unique_filename(original)
        category = assets.category_for(name)
        if owner is not None and owner.asset_prefix:
            key = f"{category}/{owner.asset_prefix}/{name}"
        else:
            key = assets.build_key(name, "home")
        return assets.save(storage, key)
    except (assets.AssetKeyError, assets.StorageError) as exc:
        current_app.logger.warning("Upload of %s failed: %s", original, exc)
        flash(f"Could not store {original!r}: {exc}", "error")
        return None


def _pagenum():
    return max(request.args.get("page", 1, type=int), 1)


# ── Projects (work and side quests are one table) ────────────────────────

@admin_bp.route("/projects")
def project_list():
    kind = request.args.get("type", "work")
    if kind not in ("work", "sidequest"):
        kind = "work"
    q = (request.args.get("q") or "").strip()

    query = Project.query.filter_by(type=kind)
    if q:
        query = query.filter(Project.title.ilike(f"%{q}%"))
    page = query.order_by(
        Project.display_order.asc(), Project.id.asc()
    ).paginate(page=_pagenum(), per_page=PER_PAGE, error_out=False)

    return render_template(
        "admin/project_list.html",
        page=page, kind=kind, q=q, confirm=ConfirmForm(),
    )


@admin_bp.route("/projects/new", methods=["GET", "POST"])
def project_new():
    kind = request.args.get("type", "work")
    if kind not in ("work", "sidequest"):
        kind = "work"

    form = ProjectForm()
    form.slug.validators = [*form.slug.validators, UniqueSlug(Project)]
    if form.validate_on_submit():
        project = Project(type=kind)
        _apply_project(project, form)
        db.session.add(project)
        if _commit(form.title.data):
            return redirect(url_for("admin.project_edit", project_id=project.id))

    return render_template(
        "admin/project_form.html", form=form, project=None, kind=kind
    )


@admin_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
def project_edit(project_id):
    project = db.session.get(Project, project_id) or abort(404)
    form = ProjectForm(obj=project)
    form.slug.validators = [*form.slug.validators, UniqueSlug(Project, project.id)]

    if request.method == "GET":
        form.status.data = project._status or ""
        form.category.data = project.category or ""
        form.specs.data = "\n".join(project.specs or [])
        form.tags.data = ", ".join(project.tags)
    elif form.validate_on_submit():
        _apply_project(project, form)
        if _commit(project.title):
            return redirect(url_for("admin.project_edit", project_id=project.id))

    return render_template(
        "admin/project_form.html",
        form=form, project=project, kind=project.type,
        gallery_form=GalleryImageForm(), attachment_form=AttachmentForm(),
        confirm=ConfirmForm(),
    )


def _apply_project(project, form):
    project.title = form.title.data.strip()
    project.slug = form.slug.data.strip()
    project.category = form.category.data or None
    project._status = form.status.data or None
    project.description = form.description.data or None
    project.long_description = form.long_description.data or None
    # A text[] column, entered one per line; blanks would render as gaps.
    project.specs = [s.strip() for s in (form.specs.data or "").splitlines() if s.strip()]
    project.display_order = form.display_order.data or 0
    project.published = bool(form.published.data)
    _sync_tags(project, form.tags.data)


@admin_bp.route("/projects/<int:project_id>/delete", methods=["POST"])
def project_delete(project_id):
    project = db.session.get(Project, project_id) or abort(404)
    if not ConfirmForm().validate_on_submit():
        abort(400)
    kind, title = project.type, project.title
    # The relationships cascade, so images and attachments go with it.
    db.session.delete(project)
    _commit(f"{title} deleted")
    return redirect(url_for("admin.project_list", type=kind))


# ── Gallery images (always attached to a project) ────────────────────────

@admin_bp.route("/gallery")
def gallery_list():
    page = (
        GalleryImage.query.join(Project)
        .order_by(Project.display_order.asc(), GalleryImage.display_order.asc(),
                  GalleryImage.id.asc())
        .paginate(page=_pagenum(), per_page=PER_PAGE, error_out=False)
    )
    return render_template("admin/gallery_list.html", page=page, confirm=ConfirmForm())


@admin_bp.route("/projects/<int:project_id>/gallery", methods=["POST"])
def gallery_add(project_id):
    project = db.session.get(Project, project_id) or abort(404)
    form = GalleryImageForm()
    if form.validate_on_submit():
        image = GalleryImage(
            project=project,
            label=form.label.data.strip(),
            display_order=form.display_order.data or 0,
        )
        image.image_path = _save_upload(form.upload.data, project) or (
            form.image_path.data or "").strip() or None
        db.session.add(image)
        _commit(image.label)
    else:
        _flash_errors(form)
    return redirect(url_for("admin.project_edit", project_id=project.id))


@admin_bp.route("/gallery/<int:image_id>/edit", methods=["GET", "POST"])
def gallery_edit(image_id):
    image = db.session.get(GalleryImage, image_id) or abort(404)
    form = GalleryImageForm(obj=image)
    if form.validate_on_submit():
        image.label = form.label.data.strip()
        image.display_order = form.display_order.data or 0
        uploaded = _save_upload(form.upload.data, image.project)
        if uploaded:
            image.image_path = uploaded
        else:
            image.image_path = (form.image_path.data or "").strip() or None
        if _commit(image.label):
            return redirect(url_for("admin.project_edit", project_id=image.project_id))
    return render_template("admin/gallery_form.html", form=form, image=image)


@admin_bp.route("/gallery/<int:image_id>/delete", methods=["POST"])
def gallery_delete(image_id):
    image = db.session.get(GalleryImage, image_id) or abort(404)
    if not ConfirmForm().validate_on_submit():
        abort(400)
    project_id, label = image.project_id, image.label
    db.session.delete(image)
    _commit(f"{label} deleted")
    # The file on disk stays: another row may point at the same path.
    return redirect(request.referrer or url_for("admin.project_edit", project_id=project_id))


# ── Attachments ──────────────────────────────────────────────────────────

@admin_bp.route("/projects/<int:project_id>/attachments", methods=["POST"])
def attachment_add(project_id):
    project = db.session.get(Project, project_id) or abort(404)
    form = AttachmentForm()
    if form.validate_on_submit():
        db.session.add(Attachment(
            project=project,
            category=form.category.data,
            name=form.name.data.strip(),
            url=form.url.data.strip(),
            file_type=form.file_type.data or None,
            file_size=form.file_size.data or None,
            display_order=form.display_order.data or 0,
        ))
        _commit(form.name.data)
    else:
        _flash_errors(form)
    return redirect(url_for("admin.project_edit", project_id=project.id))


@admin_bp.route("/attachments/<int:attachment_id>/delete", methods=["POST"])
def attachment_delete(attachment_id):
    attachment = db.session.get(Attachment, attachment_id) or abort(404)
    if not ConfirmForm().validate_on_submit():
        abort(400)
    project_id, name = attachment.project_id, attachment.name
    db.session.delete(attachment)
    _commit(f"{name} deleted")
    return redirect(url_for("admin.project_edit", project_id=project_id))


# ── Blog posts ───────────────────────────────────────────────────────────

@admin_bp.route("/posts")
def post_list():
    q = (request.args.get("q") or "").strip()
    query = Post.query
    if q:
        query = query.filter(Post.title.ilike(f"%{q}%"))
    page = query.order_by(Post.date.desc().nulls_last(), Post.id.desc()).paginate(
        page=_pagenum(), per_page=PER_PAGE, error_out=False
    )
    return render_template("admin/post_list.html", page=page, q=q, confirm=ConfirmForm())


@admin_bp.route("/posts/new", methods=["GET", "POST"])
def post_new():
    form = PostForm()
    form.slug.validators = [*form.slug.validators, UniqueSlug(Post)]
    if form.validate_on_submit():
        post = Post()
        _apply_post(post, form)
        db.session.add(post)
        if _commit(form.title.data):
            return redirect(url_for("admin.post_edit", post_id=post.id))
    return render_template("admin/post_form.html", form=form, post=None)


@admin_bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
def post_edit(post_id):
    post = db.session.get(Post, post_id) or abort(404)
    form = PostForm(obj=post)
    form.slug.validators = [*form.slug.validators, UniqueSlug(Post, post.id)]
    if request.method == "GET":
        form.tags.data = ", ".join(post.tags)
    elif form.validate_on_submit():
        _apply_post(post, form)
        if _commit(post.title):
            return redirect(url_for("admin.post_edit", post_id=post.id))
    return render_template("admin/post_form.html", form=form, post=post, confirm=ConfirmForm())


def _apply_post(post, form):
    post.title = form.title.data.strip()
    post.slug = form.slug.data.strip()
    post.date = form.date.data
    post.excerpt = form.excerpt.data or None
    post.content = form.content.data
    post.display_order = form.display_order.data or 0
    post.published = bool(form.published.data)
    _sync_tags(post, form.tags.data)


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
def post_delete(post_id):
    post = db.session.get(Post, post_id) or abort(404)
    if not ConfirmForm().validate_on_submit():
        abort(400)
    title = post.title
    db.session.delete(post)
    _commit(f"{title} deleted")
    return redirect(url_for("admin.post_list"))


# ── Tags ─────────────────────────────────────────────────────────────────

@admin_bp.route("/tags", methods=["GET", "POST"])
def tag_list():
    form = TagForm()
    if form.validate_on_submit():
        if Tag.query.filter_by(slug=form.slug.data).first():
            flash(f"A tag with slug {form.slug.data!r} already exists.", "error")
        else:
            db.session.add(Tag(
                name=form.name.data.strip(),
                slug=form.slug.data,
                color=form.color.data or None,
            ))
            if _commit(form.name.data):
                return redirect(url_for("admin.tag_list"))
    tags = Tag.query.order_by(Tag.name.asc()).all()
    return render_template(
        "admin/tag_list.html", tags=tags, form=form, confirm=ConfirmForm()
    )


@admin_bp.route("/tags/<int:tag_id>/delete", methods=["POST"])
def tag_delete(tag_id):
    tag = db.session.get(Tag, tag_id) or abort(404)
    if not ConfirmForm().validate_on_submit():
        abort(400)
    name = tag.name
    # Association rows go via ON DELETE CASCADE; the projects just lose the tag.
    db.session.delete(tag)
    _commit(f"{name} deleted")
    return redirect(url_for("admin.tag_list"))


# ── Skills and certifications ────────────────────────────────────────────

def _editing(model):
    """The row `?edit=` names, or None for a blank form. A stale id is a 404
    rather than a silent new row -- the second is how a back button quietly
    duplicates the thing you were correcting.
    """
    row_id = request.args.get("edit", type=int)
    if not row_id:
        return None
    return db.session.get(model, row_id) or abort(404)


@admin_bp.route("/skills", methods=["GET", "POST"])
def skill_list():
    """Add and edit on one page.

    Sixteen rows across four groups did not need a list page, a create page and
    an edit page. `?edit=<id>` fills the same form the add button posts to, so
    there is one form, one template and one route covering both.
    """
    skill = _editing(Skill)
    form = SkillForm(obj=skill) if request.method == "GET" else SkillForm()
    if form.validate_on_submit():
        target = skill or Skill()
        target.category = form.category.data.strip()
        target.name = form.name.data.strip()
        target.display_order = form.display_order.data or 0
        db.session.add(target)
        if _commit(target.name):
            return redirect(url_for("admin.skill_list"))
    return render_template(
        "admin/skill_list.html",
        form=form,
        editing=skill,
        skills=Skill.query.order_by(Skill.display_order, Skill.id).all(),
        confirm=ConfirmForm(),
    )


@admin_bp.route("/skills/<int:skill_id>/delete", methods=["POST"])
def skill_delete(skill_id):
    skill = db.session.get(Skill, skill_id) or abort(404)
    if not ConfirmForm().validate_on_submit():
        abort(400)
    name = skill.name
    db.session.delete(skill)
    _commit(f"{name} deleted")
    return redirect(url_for("admin.skill_list"))


@admin_bp.route("/certifications", methods=["GET", "POST"])
def certification_list():
    cert = _editing(Certification)
    form = (
        CertificationForm(obj=cert)
        if request.method == "GET"
        else CertificationForm()
    )
    if form.validate_on_submit():
        target = cert or Certification()
        target.name = form.name.data.strip()
        target.issuer = form.issuer.data.strip()
        target.status = form.status.data
        target.year = form.year.data
        target.display_order = form.display_order.data or 0
        db.session.add(target)
        if _commit(target.name):
            return redirect(url_for("admin.certification_list"))
    return render_template(
        "admin/certification_list.html",
        form=form,
        editing=cert,
        certs=Certification.ordered(),
        confirm=ConfirmForm(),
    )


@admin_bp.route("/certifications/<int:cert_id>/delete", methods=["POST"])
def certification_delete(cert_id):
    cert = db.session.get(Certification, cert_id) or abort(404)
    if not ConfirmForm().validate_on_submit():
        abort(400)
    name = cert.name
    db.session.delete(cert)
    _commit(f"{name} deleted")
    return redirect(url_for("admin.certification_list"))


def _flash_errors(form):
    """Surface a failed sub-form that has no page of its own to render into."""
    for field, errors in form.errors.items():
        label = getattr(form, field).label.text
        for error in errors:
            flash(f"{label}: {error}", "error")
