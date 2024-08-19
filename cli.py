import asyncio
import secrets
import subprocess
from typing import Annotated, Optional

from rich import print
import typer

from app.core.config import settings
from app.crud.user import create_user, get_user_by_email, get_user_by_username
from app.db.config import AsyncSessionLocal
from app.db.models import User
from app.utils.security import get_password_hash

app = typer.Typer()


@app.command()
def secret(length: Annotated[int, typer.Argument()] = 32):
    print(f"[yellow]Generating a secret key with a length of {length}[/ yellow]")
    secret_key = secrets.token_hex(length)
    print(secret_key)


@app.command()
def create_admin(
    username: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
):
    """
    Create an admin user
    """
    if not username:
        username = settings.admin_username
    if not email:
        email = settings.admin_email
    if not password:
        password = settings.admin_password
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(create_admin_user(username, email, password))
    print(result)


async def create_admin_user(username: str, email: str, password: str):
    async with AsyncSessionLocal() as db:
        if await get_user_by_email(db, email) or await get_user_by_username(
            db, username
        ):
            print(
                f"[bold red]Alert:[/bold red] [bold]Email - {email} or Username - {username}[/bold] already exists"
            )
            return
        user = User(
            username=username,
            email=email,
            is_active=True,
            is_superuser=True,
            is_email_verified=True,
            hashed_password=await get_password_hash(password),
        )
        await create_user(session=db, user=user)
    return f"Admin user {email} created successfully"


@app.command()
def run_alembic(comment: Annotated[str, typer.Argument()] = "auto"):
    """
    Run Alembic migrations
    """
    try:
        revision_command = f"alembic revision --autogenerate -m {comment}"
        print(f"Running Alembic migrations: {revision_command}")
        subprocess.run(revision_command, shell=True, check=True)
        upgrade_command = "alembic upgrade head"
        print(f"Running Alembic upgrade: {upgrade_command}")
        subprocess.run(upgrade_command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[red]Error:[/red] {e}")
        return
    print("[green]Migration complete[/green]")


@app.callback()
def main(ctx: typer.Context):
    print(f"Executing the command: {ctx.invoked_subcommand}")


if __name__ == "__main__":
    app()
