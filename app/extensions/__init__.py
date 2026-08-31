"""Extension singletons, one per file, re-exported here.

Every extension is constructed unbound and wired to an app inside
create_app(). Keeping the objects out of the factory is what lets a model
or a blueprint import `db` without importing the application, which is
the circular-import that bites every Flask project eventually.

The re-export is the point of the package: callers still write
`from app.extensions import db`, unchanged from when this was one file,
while each extension's own setup lives beside the object it configures.
"""

from app.extensions.auth import login_manager
from app.extensions.csrf import csrf
from app.extensions.database import db

__all__ = ["csrf", "db", "login_manager"]
