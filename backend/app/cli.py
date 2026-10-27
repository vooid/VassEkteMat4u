"""Command-line tools: `flask --app app <command>` from the backend folder."""
import click
from flask import Flask
from flask.cli import with_appcontext

from . import auth
from .repositories import staff


@click.command("create-staff")
@click.argument("email")
@click.option("--name", required=True, help="Full name shown in the header.")
@click.option("--role", type=click.Choice(auth.STAFF_ROLES), default="admin", show_default=True)
@click.password_option(help="Asked for if left out (recommended, so it isn't saved in the shell history).")
@with_appcontext
def create_staff(email: str, name: str, role: str, password: str) -> None:
    """Create an Ekte Mat staff account (admin, kitchen or driver)."""
    email = auth.normalise_email(email)
    if not auth.EMAIL_RE.match(email):
        raise click.ClickException("Not a valid e-mail address.")
    if auth.password_errors(password, password):
        raise click.ClickException(
            f"The password must be {auth.MIN_PASSWORD_LENGTH}–{auth.MAX_PASSWORD_LENGTH} characters.")
    if staff.create(email, auth.hash_password(password), name.strip(), role) is None:
        raise click.ClickException(f"There's already a staff account for {email}.")
    click.echo(f"Created {role} account for {email}.")


def init_app(app: Flask) -> None:
    app.cli.add_command(create_staff)
