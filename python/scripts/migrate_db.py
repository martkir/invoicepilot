"""Placeholder migration runner.

Ops script — run and exit. Never imported by the application.
Usage: python scripts/migrate_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import get_logger  # noqa: E402

log = get_logger("migrate")


def main() -> None:
    log.info("No migrations defined yet.")


if __name__ == "__main__":
    main()
