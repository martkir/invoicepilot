"""Create the schema, bring a pre-workspace database up to it, and file any
invoices already on disk into it.

The backfill exists because .data/ predates the database: invoices extracted by
earlier runs are on disk with no row to match. It reads each invoice.json and
upserts it, so running this twice is harmless.

The workspace migration exists because tenancy arrived after the data did.
`Base.metadata.create_all` creates tables that are missing but never alters one
that exists, so the columns and the two composite primary keys have to be
written out here. Every step is guarded on the catalog rather than on a version
number — there is no migration table, and adding one for a single step would
outweigh what it tracks.

Lives in the package rather than in scripts/ because the container runs it at
startup — an image that has to copy one file out of scripts/ to reach it is
carrying an ops directory it otherwise has no use for.
"""

import json
import secrets
from pathlib import Path

from sqlalchemy import Connection, text

from invoicepilot.core.db import get_engine, session_scope
from invoicepilot.core.logging import get_logger
from invoicepilot.invoice_store import DATA_ROOT, workspace_root
from invoicepilot.invoices import save
from invoicepilot.models import Base
from invoicepilot.workspaces import ID_BYTES

log = get_logger("migrate")

# The tables that gained a workspace, and what their key becomes. `shares`
# gained the column without changing its key: a token is already unique across
# the deployment.
SCOPED: dict[str, tuple[str, ...] | None] = {
    "invoices": ("workspace_id", "id"),
    "mailbox_scans": ("workspace_id", "mailbox"),
    "shares": None,
}


def _has_column(connection: Connection, table: str, column: str) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).scalar()
    )


def _table_exists(connection: Connection, table: str) -> bool:
    return bool(
        connection.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar()
    )


def _primary_key_name(connection: Connection, table: str) -> str | None:
    """The table's primary key constraint, read from the catalog rather than guessed.

    Postgres names it `<table>_pkey` by default, but a database that has been
    restored or hand-edited need not agree, and dropping the wrong constraint
    is not a mistake worth risking to save a query.
    """
    return connection.execute(
        text(
            "SELECT conname FROM pg_constraint WHERE conrelid = to_regclass(:t) AND contype = 'p'"
        ),
        {"t": f"public.{table}"},
    ).scalar()


def adopt_existing(connection: Connection) -> str | None:
    """Give every pre-workspace row a workspace. Returns its id, or None.

    None means there was nothing to adopt — a fresh database, or one already
    migrated — and is the ordinary answer on every run after the first.

    The id is random, exactly like one a browser would be given. A memorable
    one would be a real weakness: the id *is* the credential, so `legacy` as an
    id would mean anyone who typed it into a cookie held the invoices.
    """
    pending = [
        table
        for table in SCOPED
        if _table_exists(connection, table) and not _has_column(connection, table, "workspace_id")
    ]
    if not pending:
        return None

    workspace_id = secrets.token_urlsafe(ID_BYTES)
    connection.execute(
        text("INSERT INTO workspaces (id, created_at) VALUES (:id, now())"), {"id": workspace_id}
    )

    for table in pending:
        key = SCOPED[table]
        log.info("adding workspace_id to %s", table)
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN workspace_id varchar"))  # noqa: S608
        connection.execute(
            text(f"UPDATE {table} SET workspace_id = :id"),  # noqa: S608
            {"id": workspace_id},
        )
        connection.execute(
            text(f"ALTER TABLE {table} ALTER COLUMN workspace_id SET NOT NULL")  # noqa: S608
        )
        connection.execute(
            text(  # noqa: S608
                f"ALTER TABLE {table} ADD CONSTRAINT {table}_workspace_fkey "
                "FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE"
            )
        )

        if key is None:
            continue
        # The key has to be replaced, not extended: the id is derived from the
        # mail, so two workspaces scanning one mailbox agree on it exactly.
        current = _primary_key_name(connection, table)
        if current:
            connection.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT {current}"))  # noqa: S608
        connection.execute(
            text(f"ALTER TABLE {table} ADD PRIMARY KEY ({', '.join(key)})")  # noqa: S608
        )
        log.info("%s is now keyed on %s", table, " + ".join(key))

    # Led by workspace_id now, because every read narrows to one workspace
    # before it sorts. The old single-column index cannot serve that.
    connection.execute(text("DROP INDEX IF EXISTS invoices_issued_idx"))
    connection.execute(
        text(
            "CREATE INDEX invoices_issued_idx ON invoices (workspace_id, issued_on DESC NULLS LAST)"
        )
    )
    return workspace_id


def relocate_documents(workspace_id: str, root: Path = DATA_ROOT) -> int:
    """Move `<data>/<mailbox>/` under `<data>/<workspace>/<mailbox>/`. Returns moves.

    A mailbox address is not unique across the deployment once anyone can
    connect one, so the documents grew a level. Only directories that look like
    the old layout are moved — a mailbox folder holds invoice folders, which
    hold an invoice.json.
    """
    destination = workspace_root(workspace_id, root)
    if not root.is_dir():
        return 0

    moved = 0
    destination.mkdir(parents=True, exist_ok=True)
    for mailbox in sorted(root.iterdir()):
        if not mailbox.is_dir() or mailbox == destination:
            continue
        if not any(mailbox.glob("*/invoice.json")):
            continue
        mailbox.rename(destination / mailbox.name)
        moved += 1
    if moved:
        log.info("moved %d mailbox folder(s) under %s", moved, destination)
    return moved


def backfill(workspace_id: str, root: Path = DATA_ROOT) -> tuple[int, int]:
    """(filed, created) for every invoice.json in one workspace's tree.

    The directory name is the invoice's id — invoice_store derives both from
    the same fields, so the folder already carries that half of the key.
    """
    tree = workspace_root(workspace_id, root)
    if not tree.is_dir():
        log.info("no %s directory — nothing to backfill", tree)
        return 0, 0

    filed = created = 0
    with session_scope() as session:
        for path in sorted(tree.glob("*/*/invoice.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                log.warning("skipping %s: %s", path, exc)
                continue
            if save(session, workspace_id, path.parent.name, payload):
                created += 1
            filed += 1
    return filed, created


def run() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    log.info("schema is up to date")

    # One transaction: a half-applied key change is not a state to restart into.
    with engine.begin() as connection:
        adopted = adopt_existing(connection)

    if adopted is None:
        log.info("no pre-workspace data to migrate")
        return

    relocate_documents(adopted)
    filed, created = backfill(adopted)
    log.info("backfilled %d invoice(s), %d new", filed, created)

    # Printed, not just logged. This id is the only way back to the invoices
    # that predate workspaces: they now belong to a workspace no browser has
    # the cookie for, and nothing else in the system will ever name it again.
    log.warning("=" * 72)
    log.warning("Existing data was filed into workspace: %s", adopted)
    log.warning("To reach it, set this as the `ip_ws` cookie on the dashboard:")
    log.warning("  DevTools -> Application -> Cookies -> add `ip_ws` = the id above")
    log.warning("`invoicepilot workspaces` prints it again if this scrolls past.")
    log.warning("=" * 72)
