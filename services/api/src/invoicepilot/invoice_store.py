"""Where extracted invoices land on disk.

One directory per invoice, under one directory per mailbox:

    .data/<mailbox>/<date>__<issuer>__<amount><currency>__<mail token>/
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
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from invoicepilot.core.config import get_settings

DATA_ROOT = get_settings().data_dir

SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")
# Enough of the mail token to separate two invoices that agree on every other
# part of the name; the full ids live in invoice.json.
ID_PREFIX = 6

THUMB_NAME = "thumb.webp"
# Page one of an invoice is recognisable at this width — logo, layout, big
# total — which is the highest signal per pixel a preview can offer.
THUMB_WIDTH = 240


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


def mail_token(message_id: str | None, fallback: str = "") -> str:
    """A short, stable handle for the message an invoice arrived in.

    Derived from the RFC822 Message-ID, which the *sender* assigns and which
    therefore survives anything done at our end. Unipile's own id does not:
    disconnecting and reconnecting a mailbox mints a new account, every message
    is issued a fresh id, and keying on that files every invoice a second time.

    Hashed rather than used raw because a Message-ID is long and contains
    characters a directory name cannot carry.
    """
    if message_id:
        return hashlib.sha256(message_id.encode("utf-8")).hexdigest()[:ID_PREFIX]
    # No Message-ID at all is rare and non-standard; fall back to the provider
    # id so such a mail still gets a name, accepting that it may re-file once.
    return fallback[:ID_PREFIX] or "unknown"


def folder_name(fields: dict, token: str) -> str:
    """Deterministic directory name, so a re-run overwrites rather than duplicates."""
    return "__".join(
        (
            invoice_date(fields),
            slug(fields.get("issuer") or "unknown issuer"),
            slug(invoice_amount(fields), limit=16),
            token,
        )
    )


def document_path(payload: dict, root: Path = DATA_ROOT) -> Path | None:
    """The vendor's own file for a stored invoice, or None if it has none.

    Built from the payload rather than from anything a caller passed in: the
    id in a request URL must never be able to steer a filesystem read. The
    resolved path is checked to be inside `root` regardless, because the
    mailbox and filename are only as trustworthy as the mail they came from.
    """
    document = payload.get("document") or {}
    name = document.get("file")
    email = payload.get("email") or {}
    mailbox = email.get("mailbox")
    folder = folder_name(
        payload.get("invoice") or {},
        mail_token(email.get("message_id"), email.get("id") or ""),
    )
    if not name or not mailbox:
        return None

    root = root.resolve()
    candidate = (root / mailbox / folder / name).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


def thumbnail(payload: dict, root: Path = DATA_ROOT) -> Path | None:
    """The invoice's first page as a small WebP, rendered on first request.

    None when the invoice has no document: some were read out of an email body
    and there is nothing to render.

    Rendered on demand rather than during extraction, so invoices filed before
    this shipped need no backfill and a scan does not pay for images nobody may
    ever look at. The file is kept beside the document, so it is rendered once.
    """
    document = document_path(payload, root)
    if document is None:
        return None

    thumb = document.parent / THUMB_NAME
    if not thumb.is_file():
        _render_thumbnail(document, thumb)
    return thumb


def _render_thumbnail(document: Path, destination: Path) -> None:
    """Page one of a PDF — or the document itself, when it is already an image.

    Written to a temporary name and moved into place, because two people
    opening the same share at once would otherwise both write this file and the
    reader in between would be served half of it.
    """
    if document.suffix.lower() == ".pdf":
        page = pdfium.PdfDocument(document)[0]
        image = page.render(scale=THUMB_WIDTH / page.get_width()).to_pil()
    else:
        image = Image.open(document)
        if image.width > THUMB_WIDTH:
            height = round(image.height * THUMB_WIDTH / image.width)
            image = image.resize((THUMB_WIDTH, height))

    staged = destination.with_suffix(f".{os.getpid()}.tmp")
    image.convert("RGB").save(staged, "WEBP", quality=80)
    os.replace(staged, destination)


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
) -> tuple[Path, dict]:
    """Write one invoice folder; return its path and the payload written.

    The payload is handed back rather than rebuilt by callers, so the row in
    Postgres and the file on disk cannot drift apart.
    """
    directory = (
        root
        / mailbox
        / folder_name(fields, mail_token(item.get("message_id"), item.get("id") or ""))
    )
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
    return directory, payload
