"""Create the schema, and file any invoices already on disk into it.

Ops script — run and exit. Never imported by the application.
Usage: python scripts/migrate_db.py

The backfill exists because .data/ predates the database: invoices extracted by
earlier runs are on disk with no row to match. It reads each invoice.json and
upserts it, so running this twice is harmless.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.db import get_engine, session_scope  # noqa: E402
from backend.core.logging import get_logger  # noqa: E402
from backend.invoice_store import DATA_ROOT  # noqa: E402
from backend.invoices import save  # noqa: E402
from backend.models import Base  # noqa: E402

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


def main() -> None:
    Base.metadata.create_all(get_engine())
    log.info("schema is up to date")

    filed, created = backfill(DATA_ROOT)
    log.info("backfilled %d invoice(s) from %s, %d new", filed, DATA_ROOT, created)


if __name__ == "__main__":
    main()
