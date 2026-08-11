"""Where extracted invoices land on disk.

One directory per invoice, under one directory per mailbox:

    .data/<mailbox>/<date>__<issuer>__<amount><currency>__<email id>/
        invoice.json    parsed fields, plus where they came from
        invoice.pdf     the vendor's own document, when the mail carried one
        source.html     exactly what was parsed, always kept

Documents are stored in whatever format the mail actually provided — a PDF
attachment stays a PDF, an image stays an image, and an invoice that only ever
existed as an email body has no document beside its source. Nothing is
rendered or converted, so anything named invoice.* here came from the vendor.

Directory names are derived from the invoice, so re-running an extraction
refreshes a folder in place instead of accumulating copies of it.
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1] / ".data"

SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")
# Enough of the email id to separate two invoices that agree on every other
# part of the name; the full id lives in invoice.json.
ID_PREFIX = 6


@dataclass
class Document:
    """A file to store beside the metadata."""

    name: str
    blob: bytes
    # Where it came from: "attachment", "nested-attachment" or "linked".
    origin: str


def slug(text: str, limit: int = 40) -> str:
    """Filesystem-safe ascii form of a name: 'Bolt Operations OÜ' -> 'bolt-operations-ou'."""
    folded = unicodedata.normalize("NFKD", text or "")
    ascii_only = folded.encode("ascii", "ignore").decode()
    cleaned = SLUG_STRIP_RE.sub("-", ascii_only.lower()).strip("-")
    return cleaned[:limit].strip("-") or "unknown"


def invoice_date(fields: dict) -> str:
    value = fields.get("date")
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    text = str(value or "").strip()
    return text[:10] if text else "undated"


def invoice_amount(fields: dict) -> str:
    amount = fields.get("amount")
    if amount is None:
        return "unknown"
    currency = (fields.get("currency") or "").strip()
    return f"{amount}{currency}"


def folder_name(fields: dict, email_id: str) -> str:
    """Deterministic directory name, so a re-run overwrites rather than duplicates."""
    return "__".join(
        (
            invoice_date(fields),
            slug(fields.get("issuer") or "unknown issuer"),
            slug(invoice_amount(fields), limit=16),
            email_id[:ID_PREFIX],
        )
    )


def _attendee(attendee: dict | None) -> dict | None:
    if not attendee:
        return None
    return {"name": attendee.get("display_name"), "address": attendee.get("identifier")}


def _serialisable(fields: dict) -> dict:
    """invoice2data returns datetimes and Decimals; JSON needs plain values."""
    out: dict[str, object] = {}
    for key, value in fields.items():
        if hasattr(value, "strftime"):
            out[key] = value.strftime("%Y-%m-%d")
        elif isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value
        else:
            out[key] = str(value)
    return out


def save_invoice(
    mailbox: str,
    item: dict,
    fields: dict,
    *,
    source_name: str,
    source_blob: bytes,
    source_kind: str,
    document: Document | None,
    tool: str,
    parsed_from: list[str] | None = None,
    templates: list[str] | None = None,
    root: Path = DATA_ROOT,
) -> Path:
    """Write one invoice folder and return its path."""
    directory = root / mailbox / folder_name(fields, item.get("id") or "unknown")
    directory.mkdir(parents=True, exist_ok=True)

    # A PDF attachment is both the source and the document; write it once.
    if not document or document.name != source_name:
        (directory / source_name).write_bytes(source_blob)
    if document:
        (directory / document.name).write_bytes(document.blob)

    payload = {
        "invoice": _serialisable(fields),
        "email": {
            "mailbox": mailbox,
            "account_id": item.get("account_id"),
            "id": item.get("id"),
            "provider_id": item.get("provider_id"),
            "subject": item.get("subject"),
            "from": _attendee(item.get("from_attendee")),
            "to": [_attendee(a) for a in (item.get("to_attendees") or [])],
            "date": item.get("date"),
            "message_id": item.get("message_id"),
        },
        "source": {
            "kind": source_kind,
            "file": source_name,
            "sha256": hashlib.sha256(source_blob).hexdigest(),
        },
        "document": (
            {
                "file": document.name,
                "origin": document.origin,
                "sha256": hashlib.sha256(document.blob).hexdigest(),
                "bytes": len(document.blob),
            }
            if document
            else None
        ),
        "extraction": {
            "extracted_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "tool": tool,
            # Which texts the fields came from, and which templates read them —
            # a merged record is only auditable if both are named.
            "parsed_from": parsed_from or [],
            "templates": templates or [],
        },
    }
    (directory / "invoice.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return directory
