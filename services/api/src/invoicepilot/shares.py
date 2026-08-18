"""Share links: the row, the snapshot it freezes, and what a link resolves to.

One click writes one row. The token in it is the URL and the credential —
having the link is what grants access — and the seven columns are everything a
recipient can be told, because they have no account and nothing else travels
with a link.

Nothing here is precomputed. The filename, the period, the counts and the
manifest are all derived from the snapshot at read time, so there is no stored
summary that can drift from the invoices it describes.
"""

import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from sqlalchemy.orm import Session

from invoicepilot import invoices
from invoicepilot.core.config import get_settings
from invoicepilot.invoice_store import document_path, workspace_root
from invoicepilot.models import Share

# 16 bytes is 22 urlsafe characters — the token is the whole credential, so it
# is sized to be guessed at never rather than to be typed.
TOKEN_BYTES = 16
OWNER_KEY_BYTES = 32

# A share lapses on its own. There is no revoke, and so nothing to clean up.
TTL = timedelta(days=7)


@dataclass(frozen=True)
class Entry:
    """One invoice's document: where it is, and what it is called in the zip."""

    path: Path
    name: str
    bytes: int


@dataclass(frozen=True)
class Summary:
    """The four facts a share page leads with, and the names the mail uses."""

    filename: str
    # "Q2" / "2026" / "2024 to 2026" / "" — how the mail's heading says which
    # invoices these are.
    label: str
    # "Apr to Jun 2026" — the subject line and the band in the mail.
    months: str
    # "Apr 1 - Jun 30, 2026" — the Period fact, on the page and in the mail.
    period: str
    invoices: int
    documents: int
    bytes: int


@dataclass(frozen=True)
class Snapshot:
    """A share and everything the ids in it resolve to, read in one go.

    The manifest, the zip and the mail are three renderings of this, which is
    what keeps the page, the download and the email quoting the same numbers.
    """

    share: Share
    items: list[dict]
    entries: dict[str, Entry]
    summary: Summary


def mint(
    session: Session, *, workspace_id: str, invoice_ids: list[str], owner: tuple[str, str]
) -> tuple[Share, str]:
    """Write one share row. Returns it and the owner key, which is not stored.

    Only the key's sha256 is kept, and the key itself is returned exactly once:
    the creating browser holds it, and that is what separates the owner from a
    recipient holding the same link.

    The workspace is recorded because the ids alone stop being enough to find
    the invoices once the same id can exist in two workspaces.
    """
    owner_key = secrets.token_urlsafe(OWNER_KEY_BYTES)
    name, email = owner
    share = Share(
        token=secrets.token_urlsafe(TOKEN_BYTES),
        workspace_id=workspace_id,
        owner_key_hash=key_hash(owner_key),
        invoice_ids=invoice_ids,
        owner_name=name,
        owner_email=email,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + TTL,
    )
    session.add(share)
    session.flush()
    return share, owner_key


def get(session: Session, token: str) -> Share | None:
    """The row for a token, expired or not.

    Deliberately unfiltered: `WHERE expires_at > now()` would fold an expired
    share into a missing one, and the caller could then only ever answer 404.
    A link that has lapsed and a link that never existed are different dead
    ends, and the person holding one needs to know which they have.
    """
    return session.get(Share, token)


def expired(share: Share, now: datetime | None = None) -> bool:
    return share.expires_at <= (now or datetime.now(UTC))


def key_hash(owner_key: str) -> str:
    return sha256(owner_key.encode()).hexdigest()


def authorized(share: Share, owner_key: str) -> bool:
    """Whether a caller holds the key this share was created with."""
    return hmac.compare_digest(key_hash(owner_key), share.owner_key_hash)


def url(token: str) -> str:
    """The link itself — the page a recipient opens, not the API behind it."""
    return f"{get_settings().public_base_url.rstrip('/')}/s/{token}"


def snapshot(session: Session, share: Share) -> Snapshot:
    """Resolve a share's frozen ids into the invoices, files and figures it covers.

    Scoped by `share.workspace_id` throughout, and never by who is asking. The
    caller here is usually a recipient: they hold the link, they have no
    account, and the workspace cookie their browser carries is their own empty
    one or nothing at all. Reading the scope off the request instead would make
    every link ever sent resolve to an empty manifest.
    """
    items = invoices.by_ids(session, share.workspace_id, share.invoice_ids)
    entries = documents(items, workspace_root(share.workspace_id))
    return Snapshot(share, items, entries, summarise(items, entries))


def documents(items: list[dict], root: Path) -> dict[str, Entry]:
    """The document each invoice carries, keyed by invoice id.

    An invoice read out of an email body has none, and is simply absent here —
    it still rides along in the manifest and in invoices.csv.

    The entry name drops the mail token the id ends in, so the recipient's
    folder reads `2026-08-03__bolt-operations-ou__1-63eur.pdf` and sorts by
    date. Two invoices that agree on every other part of the name get the token
    back, because a zip with a name in it twice loses one of them.
    """
    entries: dict[str, Entry] = {}
    taken: set[str] = set()
    for item in items:
        path = document_path(item, root)
        if path is None:
            continue
        base, _, token = item["id"].rpartition("__")
        name = f"{base or item['id']}{path.suffix}"
        if name in taken:
            name = f"{base}__{token}{path.suffix}"
        taken.add(name)
        entries[item["id"]] = Entry(path, name, path.stat().st_size)
    return entries


def summarise(items: list[dict], entries: dict[str, Entry]) -> Summary:
    """The batch's own name and figures, worked out from the invoices in it.

    There is no `title` column and no stored size: a batch that names itself
    from its own dates has nothing to keep in step.
    """
    dates = sorted(date.fromisoformat(item["issued_on"]) for item in items if item.get("issued_on"))
    slug, label, months, period = _naming(dates[0], dates[-1]) if dates else ("", "", "", "")
    return Summary(
        filename=f"invoices-{slug}.zip" if slug else "invoices.zip",
        label=label,
        months=months,
        period=period,
        invoices=len(items),
        documents=len(entries),
        # What the zip will weigh, near enough: it is stored uncompressed, and
        # invoices.csv adds a few kilobytes to this.
        bytes=sum(entry.bytes for entry in entries.values()),
    )


def manifest(items: list[dict], entries: dict[str, Entry]) -> list[dict]:
    """One row per invoice, holding only what a recipient may see.

    A projection rather than the stored payload, which carries the owner's
    mailbox, the message it arrived in and the extraction's own record. The
    share page is public; the payload is not.
    """
    rows = []
    for item in items:
        invoice = item.get("invoice") or {}
        entry = entries.get(item["id"])
        rows.append(
            {
                "id": item["id"],
                "vendor": text(invoice.get("issuer")),
                "invoice_number": text(invoice.get("invoice_number")),
                "file": entry.name if entry else None,
                "issued_on": item.get("issued_on"),
                "currency": text(invoice.get("currency")),
                "amount_net": text(invoice.get("amount_untaxed")),
                "amount_vat": text(invoice.get("amount_tax")),
                "amount_total": text(invoice.get("amount")),
            }
        )
    return rows


def text(value: object) -> str | None:
    """A stored field as a string, or None when the parser never found it.

    Half these fields are empty on any real batch — a ride receipt has no
    invoice number and no VAT split — and blank is the honest answer rather
    than an error.
    """
    if value is None or value == "":
        return None
    return str(value)


def _naming(first: date, last: date) -> tuple[str, str, str, str]:
    """(filename slug, label, months, period) for a batch spanning two dates."""
    if first.year != last.year:
        return (
            f"{first.year}-{last.year}",
            f"{first.year} to {last.year}",
            f"{first:%b} {first.year} to {last:%b} {last.year}",
            f"{first:%b} {first.day}, {first.year} - {last:%b} {last.day}, {last.year}",
        )

    quarter = (first.month - 1) // 3 + 1
    whole_quarter = quarter == (last.month - 1) // 3 + 1
    months = (
        f"{first:%b} {first.year}"
        if first.month == last.month
        else f"{first:%b} to {last:%b} {first.year}"
    )
    return (
        f"{first.year}-Q{quarter}" if whole_quarter else f"{first.year}",
        f"Q{quarter}" if whole_quarter else f"{first.year}",
        months,
        f"{first:%b} {first.day} - {last:%b} {last.day}, {first.year}",
    )
