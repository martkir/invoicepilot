"""Typer CLI — the run-and-exit entrypoint.

Installed as `invoicepilot`; also runnable as `python -m backend`.
"""

import typer

from backend import __version__
from backend.core.config import get_settings
from backend.core.logging import get_logger

log = get_logger(__name__)

cli = typer.Typer(
    name="invoicepilot",
    help="Invoice Pilot — Python CLI.",
    no_args_is_help=True,
)


@cli.command()
def version() -> None:
    """Print the version."""
    typer.echo(__version__)


@cli.command()
def config() -> None:
    """Show the resolved settings (secrets are not printed)."""
    settings = get_settings()
    typer.echo(f"database_url set : {bool(settings.database_url)}")
    typer.echo(f"api_host         : {settings.api_host}")
    typer.echo(f"api_port         : {settings.api_port}")
    typer.echo(f"debug_logs       : {settings.debug_logs_enabled}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
