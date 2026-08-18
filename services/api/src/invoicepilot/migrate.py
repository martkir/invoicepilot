"""Create the schema, and file any invoices already on disk into it.

The backfill exists because .data/ predates the database: invoices extracted by
earlier runs are on disk with no row to match. It reads each invoice.json and
upserts it, so running this twice is harmless.

Lives in the package rather than in scripts/ because the container runs it at
startup — an image that has to copy one file out of scripts/ to reach it is
carrying an ops directory it otherwise has no use for.
"""

import json
from pathlib import Path

from invoicepilot.core.db import get_engine, session_scope
from invoicepilot.core.logging import get_logger
from invoicepilot.invoice_store import DATA_ROOT
from invoicepilot.invoices import save
from invoicepilot.models import Base

log = get_logger("migrate")


def backfill(root: Path) -> tuple[int, int]:
    """(filed, created) for every invoice.json under `root`.

    The directory name is the invoice's id — invoice_store derives both from
    the same fields, so the folder already carries the primary key.
    """
    if not root.is_dir():
        log.info("no %s directory — nothing to backfill", root)
        return 0, 0

    filed = created = 0
    with session_scope() as session:
        for path in sorted(root.glob("*/*/invoice.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                log.warning("skipping %s: %s", path, exc)
                continue
            if save(session, path.parent.name, payload):
                created += 1
            filed += 1
    return filed, created


def run() -> None:
    Base.metadata.create_all(get_engine())
    log.info("schema is up to date")

    filed, created = backfill(DATA_ROOT)
    log.info("backfilled %d invoice(s) from %s, %d new", filed, DATA_ROOT, created)
