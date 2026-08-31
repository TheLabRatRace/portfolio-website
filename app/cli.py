"""Command-line administration.

The only way an admin account comes into existence: no seeded row in the
schema and no sign-up page.

    docker compose exec web flask create-admin jeff
"""

import getpass
import sys

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import User

MIN_PASSWORD_LENGTH = 12


def register_cli(app):
    app.cli.add_command(create_admin)
    app.cli.add_command(reset_password)
    app.cli.add_command(list_admins)


def _prompt_password():
    """Read a password twice, from the terminal, without echoing it. Not a
    --password option, which lands in shell history and in `ps` output.
    """
    if not sys.stdin.isatty():
        raise click.ClickException(
            "Needs a terminal to read the password. Run with `docker compose "
            "exec` (interactive), not `exec -T`."
        )
    first = getpass.getpass("Password: ")
    if len(first) < MIN_PASSWORD_LENGTH:
        raise click.ClickException(
            f"Too short -- {MIN_PASSWORD_LENGTH} characters minimum."
        )
    if first != getpass.getpass("Repeat: "):
        raise click.ClickException("The two entries did not match.")
    return first


@click.command("create-admin")
@click.argument("username")
@click.option("--email", default=None, help="Optional, for your own reference.")
@with_appcontext
def create_admin(username, email):
    """Create an admin account, prompting for the password."""
    username = username.strip()
    if User.query.filter_by(username=username).first():
        raise click.ClickException(
            f"{username!r} already exists. Use `flask reset-password` instead."
        )
    user = User(username=username, email=email, is_admin=True)
    user.set_password(_prompt_password())
    db.session.add(user)
    db.session.commit()
    click.echo(f"Created admin {username!r}. Sign in at /admin/login.")


@click.command("reset-password")
@click.argument("username")
@with_appcontext
def reset_password(username):
    """Set a new password for an existing admin."""
    user = User.query.filter_by(username=username.strip()).first()
    if user is None:
        raise click.ClickException(f"No such user: {username!r}")
    user.set_password(_prompt_password())
    db.session.commit()
    click.echo(f"Password updated for {user.username!r}.")


@click.command("list-admins")
@with_appcontext
def list_admins():
    """Show the admin accounts. Hashes are never printed."""
    users = User.query.order_by(User.username).all()
    if not users:
        click.echo("No accounts yet -- run `flask create-admin <username>`.")
        return
    for user in users:
        last = user.last_login_at.strftime("%Y-%m-%d %H:%M") if user.last_login_at else "never"
        click.echo(f"{user.username:<20} admin={user.is_admin!s:<5} last login: {last}")
