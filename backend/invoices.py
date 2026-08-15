"""Reading and writing the invoices table.

The row's `data` is the same payload backend/invoice_store.py writes to disk,
so nothing is transcribed between the two. Only `id` and `issued_on` are lifted
out of it, because those are what the database itself has to work with.
"""

from datetime import date, datetime

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.invoice_store import folder_name
from backend.models import Invoice

DEFAULT_PAGE = 50
# The largest page a caller may ask for. The dashboard renders one screenful at
# a time; without a ceiling, `?limit=1000000` is a whole-table dump.
MAX_PAGE = 200


def row_id(fields: dict, token: str) -> str:
    """Stable identity for an invoice — the same string that names its folder.

    `token` comes from invoice_store.mail_token: derived from the sender's
    Message-ID, so re-authorizing a mailbox does not change an invoice's key.
    """
    return folder_name(fields, token)


def issued_on(fields: dict) -> date | None:
    """The invoice's own date, or None when the parser could not find one."""
    value = fields.get("date")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def save(session: Session, invoice_id: str, payload: dict) -> bool:
    """Upsert one invoice. True when the row was created, False when it existed.

    Re-scanning a mailbox re-parses the same mail, so this has to be idempotent.
    `xmax = 0` is Postgres reporting which branch the upsert took, which is what
    separates "found" from "new" in a scan result.
    """
    parsed = payload.get("invoice") or {}
    statement = (
        insert(Invoice)
        .values(id=invoice_id, issued_on=issued_on(parsed), data=payload)
        .on_conflict_do_update(
            index_elements=[Invoice.id],
            set_={"issued_on": issued_on(parsed), "data": payload},
        )
        .returning(literal_column("xmax = 0").label("inserted"))
    )
    return bool(session.execute(statement).scalar())


def get(session: Session, invoice_id: str) -> dict | None:
    """One stored invoice payload, or None."""
    return session.execute(
        select(Invoice.data).where(Invoice.id == invoice_id)
    ).scalar_one_or_none()


def recent(session: Session, *, limit: int = DEFAULT_PAGE, offset: int = 0) -> list[dict]:
    """One page of invoices, newest first, as stored.

    Undated invoices sort last rather than first — the parser failing to find a
    date is no reason to lead the dashboard with it.
    """
    rows = session.execute(
        select(Invoice.id, Invoice.issued_on, Invoice.data)
        .order_by(Invoice.issued_on.desc().nullslast(), Invoice.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        {
            "id": row.id,
            "issued_on": row.issued_on.isoformat() if row.issued_on else None,
            **row.data,
        }
        for row in rows
    ]


def count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Invoice)) or 0
