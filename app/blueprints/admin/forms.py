"""Admin forms.

Flask-WTF throughout, so the CSRF token is part of the form object and a form
added later is protected by construction. Two conventions run through the file:

  * A blank slug is filled in from the title.
  * Tags and specs are entered as text -- comma-separated and one-per-line --
    because a multi-select of 60 tags is unusable. The routes convert.
"""

import re

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    DateField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional, Regexp, ValidationError

SLUG_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
SLUG_MESSAGE = "Lowercase letters, numbers and single hyphens only."


def slugify(text):
    """The Python twin of the `slugify` Jinja filter -- same rules, same output."""
    text = re.sub(r"[^a-z0-9]+", "-", str(text).lower())
    return text.strip("-")


class SlugFromTitleMixin:
    """Fill an empty slug from the title before validation sees it, so the
    Regexp validator checks the generated slug too -- a title of "!!!" is
    rejected rather than saved as a row with no URL.
    """

    def validate(self, extra_validators=None):
        if not (self.slug.data or "").strip() and self.title.data:
            self.slug.data = slugify(self.title.data)
        return super().validate(extra_validators=extra_validators)


class UniqueSlug:
    """Reject a slug another row already owns. The UNIQUE constraint is what
    guarantees it; this turns a 500 into a message next to the field.
    """

    def __init__(self, model, current_id=None):
        self.model = model
        self.current_id = current_id

    def __call__(self, form, field):
        row = self.model.query.filter_by(slug=field.data).first()
        if row is not None and row.id != self.current_id:
            raise ValidationError(f"'{field.data}' is already used by {row.title!r}.")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Stay signed in")
    submit = SubmitField("Sign in")


class ProjectForm(SlugFromTitleMixin, FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    slug = StringField(
        "Slug",
        validators=[Optional(), Length(max=200), Regexp(SLUG_RE, message=SLUG_MESSAGE)],
        description="Leave blank to build it from the title.",
    )
    # The empty option is a real value: side quests have no category.
    category = SelectField(
        "Category",
        choices=[("", "—"), ("infrastructure", "Infrastructure"), ("code", "Code")],
        validators=[Optional()],
    )
    status = SelectField(
        "Status",
        choices=[("", "—"), ("active", "Active"), ("in_progress", "In progress")],
        validators=[Optional()],
    )
    description = TextAreaField("Short description", validators=[Optional()])
    long_description = TextAreaField("Long description", validators=[Optional()])
    specs = TextAreaField(
        "Specs", validators=[Optional()], description="One per line."
    )
    tags = StringField(
        "Tags", validators=[Optional()], description="Comma-separated. New tags are created."
    )
    display_order = IntegerField("Display order", validators=[Optional()], default=0)
    published = BooleanField("Published")
    submit = SubmitField("Save")


class PostForm(SlugFromTitleMixin, FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    slug = StringField(
        "Slug",
        validators=[Optional(), Length(max=200), Regexp(SLUG_RE, message=SLUG_MESSAGE)],
        description="Leave blank to build it from the title.",
    )
    date = DateField("Date", validators=[Optional()])
    excerpt = TextAreaField("Excerpt", validators=[Optional()])
    content = TextAreaField("Content", validators=[DataRequired()])
    tags = StringField("Tags", validators=[Optional()], description="Comma-separated.")
    display_order = IntegerField("Display order", validators=[Optional()], default=0)
    published = BooleanField("Published")
    submit = SubmitField("Save")


class GalleryImageForm(FlaskForm):
    label = StringField("Label", validators=[DataRequired(), Length(max=200)])
    upload = FileField(
        "Upload",
        validators=[
            FileAllowed(
                ["png", "jpg", "jpeg", "webp", "gif", "svg"],
                "Images only (png, jpg, webp, gif, svg).",
            )
        ],
        description="Saved under static/images/uploads/.",
    )
    image_path = StringField(
        "Existing path",
        validators=[Optional(), Length(max=500)],
        description="Relative to static/images/ -- use this instead of uploading.",
    )
    display_order = IntegerField("Display order", validators=[Optional()], default=0)
    submit = SubmitField("Save")


class AttachmentForm(FlaskForm):
    category = SelectField(
        "Kind",
        choices=[("document", "Document"), ("download", "Download")],
        validators=[DataRequired()],
    )
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    url = StringField("URL", validators=[DataRequired(), Length(max=500)])
    file_type = StringField("File type", validators=[Optional(), Length(max=50)])
    file_size = StringField("File size", validators=[Optional(), Length(max=20)])
    display_order = IntegerField("Display order", validators=[Optional()], default=0)
    submit = SubmitField("Save")


class TagForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=64)])
    slug = StringField(
        "Slug",
        validators=[Optional(), Length(max=64), Regexp(SLUG_RE, message=SLUG_MESSAGE)],
    )
    color = StringField(
        "Colour",
        validators=[Optional(), Regexp(r"^#[0-9a-fA-F]{6}$", message="Hex, e.g. #c9a84c.")],
    )
    submit = SubmitField("Save")

    def validate(self, extra_validators=None):
        if not (self.slug.data or "").strip() and self.name.data:
            self.slug.data = slugify(self.name.data)
        return super().validate(extra_validators=extra_validators)


class SkillForm(FlaskForm):
    """The group heading is a free-text field, not a select.

    A select would need its options built from the rows it is about to add to,
    which makes the first skill in a new group unenterable. Typing the heading
    again is the price of being able to type it once.
    """

    category = StringField(
        "Group", validators=[DataRequired(), Length(max=80)],
        description="The heading it appears under, e.g. Networking.",
    )
    name = StringField("Skill", validators=[DataRequired(), Length(max=200)])
    display_order = IntegerField("Display order", validators=[Optional()], default=0)
    submit = SubmitField("Save")


class CertificationForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    issuer = StringField("Issuer", validators=[DataRequired(), Length(max=120)])
    status = SelectField(
        "Status",
        choices=[("active", "Active"), ("in_progress", "In progress"),
                 ("expired", "Expired")],
        validators=[DataRequired()],
    )
    year = IntegerField("Year", validators=[Optional()])
    display_order = IntegerField("Display order", validators=[Optional()], default=0)
    submit = SubmitField("Save")


class ConfirmForm(FlaskForm):
    """A form with nothing in it but its CSRF token, so no destructive action
    is ever a bare link a crawler or a prefetch can follow.
    """

    submit = SubmitField("Delete")
