from flask import render_template

from app.blueprints.main import main_bp
from app.models import Certification, Skill


@main_bp.route("/")
def home():
    # The about content is a section of this page, so its data is this page's;
    # _about_content.html reads both names straight out of the context.
    return render_template(
        "main/home.html",
        active_section="home",
        skills=Skill.grouped(),
        certs=Certification.ordered(),
    )


@main_bp.route("/contact")
def contact():
    return render_template("main/contact.html", active_section="contact")
