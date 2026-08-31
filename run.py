import os
from app import create_app

# Production is the safe default. Development turns on DEBUG -- the Werkzeug
# debugger is a remote shell -- and accepts a placeholder SECRET_KEY, so a
# deployment that forgets to set FLASK_ENV must not land there by accident.
app = create_app(os.environ.get("FLASK_ENV") or "production")

if __name__ == "__main__":
    app.run(port=app.config["PORT"])
