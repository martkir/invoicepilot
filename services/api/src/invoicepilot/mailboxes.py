"""Reading and writing the mailbox_scans table — how far each mailbox is scanned.

Its own module rather than a second table bolted onto invoices.py, because the
split in this package is by domain: what a mailbox has been scanned through is
not a fact about an invoice, and the two are read at opposite ends of a scan.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from invoicepilot.models import MailboxScan


def watermark(session: Session, mailbox: str) -> datetime | None:
    """The date this mailbox is scanned through, or None if it never has been.

    Always timezone-aware. SQLAlchemy hands back whatever the column holds, and
    comparing a naive datetime against an aware one raises — much later, in the
    middle of a scan, rather than here.
    """
    at = session.scalars(
        select(MailboxScan.scanned_through).where(MailboxScan.mailbox == mailbox)
    ).one_or_none()
    if at is None:
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def set_watermark(session: Session, mailbox: str, at: datetime) -> None:
    """Record that this mailbox is scanned through `at`.

    GREATEST, so it never moves backwards: a --since backfill re-reads an old
    window, and letting that overwrite the mark would leave the mailbox
    claiming less progress than it has made and redo months of mail on the
    next ordinary scan.
    """
    session.execute(
        insert(MailboxScan)
        .values(mailbox=mailbox, scanned_through=at)
        .on_conflict_do_update(
            index_elements=[MailboxScan.mailbox],
            set_={"scanned_through": func.greatest(MailboxScan.scanned_through, at)},
        )
    )
