from flask_login import LoginManager

from app.extensions.database import db

login_manager = LoginManager()

# Where an anonymous visitor is sent when they hit an @login_required view.
login_manager.login_view = "admin.login"
login_manager.login_message = "Sign in to reach the admin area."
login_manager.login_message_category = "error"

# "strong" ties the session to a hash of the user agent and IP, so a stolen
# cookie replayed elsewhere is rejected. A network change signs the admin out.
login_manager.session_protection = "strong"


@login_manager.user_loader
def load_user(user_id):
    # Inside the function: app.models imports db from this package.
    from app.models import User

    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        # A tampered or stale cookie -- treat it as signed out, not as a 500.
        return None
