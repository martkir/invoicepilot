"""Reading and writing the invoices table.

The row's `data` is the same payload invoicepilot/invoice_store.py writes to disk,
so nothing is transcribed between the two. Only `id` and `issued_on` are lifted
out of it, because those are what the database itself has to work with.

Every function here takes a `workspace_id` and none of them will run without
one. That is deliberate: the dashboard is public, so an unscoped query is a
data leak rather than a bug to tidy up later, and a required argument is the
one form of that reminder the type checker can enforce.
"""

from datetime import date, datetime

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from invoicepilot.invoice_store import folder_name
from invoicepilot.models import Invoice

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


def save(session: Session, workspace_id: str, invoice_id: str, payload: dict) -> bool:
    """Upsert one invoice. True when the row was created, False when it existed.

    Re-scanning a mailbox re-parses the same mail, so this has to be idempotent.
    `xmax = 0` is Postgres reporting which branch the upsert took, which is what
    separates "found" from "new" in a scan result.

    The conflict target is both key columns. On `id` alone, a second workspace
    scanning the same mailbox would land on the first one's row and overwrite
    it — the id is derived from the mail, so the collision is guaranteed rather
    than unlikely.
    """
    parsed = payload.get("invoice") or {}
    statement = (
        insert(Invoice)
        .values(workspace_id=workspace_id, id=invoice_id, issued_on=issued_on(parsed), data=payload)
        .on_conflict_do_update(
            index_elements=[Invoice.workspace_id, Invoice.id],
            set_={"issued_on": issued_on(parsed), "data": payload},
        )
        .returning(literal_column("xmax = 0").label("inserted"))
    )
    return bool(session.execute(statement).scalar())


def get(session: Session, workspace_id: str, invoice_id: str) -> dict | None:
    """One stored invoice payload, or None.

    None covers both "no such invoice" and "not yours", and the caller answers
    404 either way: which of the two it is is itself something a stranger
    should not be able to learn.
    """
    return session.execute(
        select(Invoice.data).where(Invoice.workspace_id == workspace_id, Invoice.id == invoice_id)
    ).scalar_one_or_none()


def recent(
    session: Session, workspace_id: str, *, limit: int = DEFAULT_PAGE, offset: int = 0
) -> list[dict]:
    """One page of invoices, newest first, as stored.

    Undated invoices sort last rather than first — the parser failing to find a
    date is no reason to lead the dashboard with it.
    """
    rows = session.execute(
        _newest_first(workspace_id).limit(limit).offset(offset),
    ).all()
    return [_as_item(row) for row in rows]


def by_ids(session: Session, workspace_id: str, invoice_ids: list[str]) -> list[dict]:
    """The stored invoices for a set of ids, in the same order as a page of them.

    Ids that no longer exist are simply absent: a share freezes the ids it
    covers, so a row deleted afterwards drops out of the manifest rather than
    breaking it.

    The workspace comes from the share row, not from whoever is asking — a
    recipient resolving a link is not the owner. See models.Share.workspace_id.
    """
    if not invoice_ids:
        return []
    rows = session.execute(_newest_first(workspace_id).where(Invoice.id.in_(invoice_ids))).all()
    return [_as_item(row) for row in rows]


def all_ids(session: Session, workspace_id: str) -> list[str]:
    """Every invoice id, in the dashboard's own order — what a share of nothing snapshots."""
    return list(
        session.scalars(
            select(Invoice.id)
            .where(Invoice.workspace_id == workspace_id)
            .order_by(Invoice.issued_on.desc().nullslast(), Invoice.id)
        )
    )


def count(session: Session, workspace_id: str) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(Invoice).where(Invoice.workspace_id == workspace_id)
        )
        or 0
    )


def _newest_first(workspace_id: str):
    """The one row shape and the one order every reader of this table uses.

    The workspace filter lives here rather than in each caller so that adding a
    reader cannot accidentally add an unscoped one.
    """
    return (
        select(Invoice.id, Invoice.issued_on, Invoice.data)
        .where(Invoice.workspace_id == workspace_id)
        .order_by(Invoice.issued_on.desc().nullslast(), Invoice.id)
    )


def _as_item(row) -> dict:
    """The stored payload, with the two promoted columns put back on top of it."""
    return {
        "id": row.id,
        "issued_on": row.issued_on.isoformat() if row.issued_on else None,
        **row.data,
    }
