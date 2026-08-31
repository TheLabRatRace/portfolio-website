"""Shared plumbing for the generated `search_vector` columns.

Postgres computes and stores the column (schema_admin_search.sql); Python
never writes it and rarely reads it. `deferred` keeps it mapped, so
`Model.search_vector @@ q` still builds a WHERE clause, while leaving it out
of the default SELECT so a list of 10 rows does not drag 10 tsvectors over.
"""

from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import deferred

from app.extensions import db


def search_vector_column():
    return deferred(
        db.Column(
            "search_vector",
            TSVECTOR,
            # Postgres owns this value; keep the ORM out of INSERT/UPDATE.
            server_default=db.FetchedValue(),
            server_onupdate=db.FetchedValue(),
        )
    )
