"""Typer CLI — the run-and-exit entrypoint.

Installed as `invoicepilot`; also runnable as `python -m invoicepilot`.
"""

from datetime import UTC, datetime
from typing import Annotated

import typer

from invoicepilot import __version__
from invoicepilot.core.config import get_settings
from invoicepilot.core.logging import get_logger

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


@cli.command()
def migrate() -> None:
    """Create the schema and file any invoices already on disk into it."""
    # Imported here, not at module scope, so `version` and `config` keep
    # working without SQLAlchemy having to load first.
    from invoicepilot import migrate as migration

    migration.run()


@cli.command()
def workspaces() -> None:
    """List the workspaces, so a scan or a backfill can name one.

    A workspace is normally minted by a browser and identified only by its
    cookie, which nothing outside that browser can see. This is how an operator
    finds the id — including the one the migration filed the pre-workspace
    invoices into.
    """
    # Imported here rather than at module scope, for the same reason `migrate`
    # is: `version` and `config` must keep working without SQLAlchemy loading.
    from invoicepilot import workspaces as ws
    from invoicepilot.core.db import session_scope

    with session_scope() as session:
        rows = ws.summarise(session)

    if not rows:
        typer.echo("No workspaces yet.")
        return

    typer.echo(f"{'id':<45} {'created':<20} {'mailboxes':>9} {'invoices':>9}")
    for row in rows:
        created = row["created_at"].strftime("%Y-%m-%d %H:%M")
        typer.echo(f"{row['id']:<45} {created:<20} {row['accounts']:>9} {row['invoices']:>9}")


@cli.command()
def scan(
    workspace: Annotated[
        str,
        typer.Option(
            help="Which workspace to scan into. `invoicepilot workspaces` lists them. "
            "Required: a mailbox belongs to a workspace, and so do the invoices a "
            "scan files, so there is no sensible default to guess at.",
        ),
    ],
    since: Annotated[
        datetime | None,
        typer.Option(
            formats=["%Y-%m-%d"],
            help="Ignore the watermark and scan from this date — the way to work "
            "through history, or to re-parse a range after adding a template.",
        ),
    ] = None,
    keywords: Annotated[
        bool,
        typer.Option(
            help="Filter to mail whose text looks like an invoice. --no-keywords "
            "reads everything in the range, which is how you find out what the "
            "filter is skipping.",
        ),
    ] = True,
    follow_links: Annotated[
        bool,
        typer.Option(
            help="Fetch invoices linked from a message body. --no-follow-links stays offline."
        ),
    ] = True,
) -> None:
    """Scan connected mailboxes for invoices and file what parses.

    With no options this is exactly what the dashboard's Update button runs:
    whatever has arrived since each mailbox was last scanned through.

    Recognition is per-issuer — invoice2data reports a document only when one of
    its templates matches — so an invoice from an untaught vendor parses to
    nothing and looks like ordinary mail here. Add YAML under
    templates/invoice2data/ to teach a new issuer.
    """
    from invoicepilot import workspaces as ws
    from invoicepilot.core.db import session_scope
    from invoicepilot.invoice_store import workspace_root
    from invoicepilot.process import Progress, scan_all
    from invoicepilot.unipile import UnipileError

    def show(progress: Progress) -> None:
        subject = progress.subject[:52]
        typer.echo(
            f"  [{progress.messages_scanned}/{progress.messages_total}] {subject:54} "
            f"{progress.invoices_found} invoice(s) so far"
        )

    with session_scope() as session:
        if not ws.exists(session, workspace):
            log.error("no workspace %s — `invoicepilot workspaces` lists them", workspace)
            raise SystemExit(1)
        allowed = ws.account_ids(session, workspace)

    try:
        result = scan_all(
            workspace,
            allowed,
            follow_links=follow_links,
            keywords=keywords,
            since=since.replace(tzinfo=UTC) if since else None,
            on_progress=show,
        )
    except UnipileError as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc

    typer.echo(
        f"\nScanned {result.messages_scanned} message(s) across "
        f"{len(result.mailboxes)} mailbox(es): {', '.join(result.mailboxes)}."
    )
    if result.errors:
        typer.echo(f"\n{len(result.errors)} could not be read — these were NOT checked:")
        for error in result.errors:
            typer.echo(f"  {error.mailbox} | {error.subject[:40]}: {error.detail}")
    if not result.invoices_found:
        typer.echo("\nNo invoices recognised.")
        return
    typer.echo(
        f"\n{result.invoices_found} invoice(s) recognised, {result.invoices_new} of them new."
        f"\nFiled under {workspace_root(workspace)} and in the database."
    )


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
