"""The download: `invoices.csv` and every document, zipped as they are read.

The zip is streamed rather than assembled — 37 invoices at 12 MB is small, but
the memory this costs should not depend on the batch. Stored, not deflated:
PDFs do not compress, so compression would spend CPU per byte to save none.
"""

import csv
import io
import zipfile
from collections.abc import Iterator

from invoicepilot.shares import Entry, Snapshot, text

CSV_NAME = "invoices.csv"
CHUNK = 64 * 1024

# Ordered for someone reading left to right who stops when they have what they
# need: what an accountant reconciles with, then the file it came out of, then
# the provenance that settles a disputed row.
CSV_COLUMNS = (
    "invoice_number",
    "issued_on",
    "vendor",
    "vendor_vat_number",
    "vendor_company_number",
    "currency",
    "amount_net",
    "amount_vat",
    "amount_total",
    "payment_reference",
    "service_date",
    "description",
    "file",
    "file_bytes",
    "file_sha256",
    "source",
    "source_mailbox",
    "email_subject",
    "email_received",
    "email_message_id",
    "extracted_at",
    "extracted_by",
)


def stream(snapshot: Snapshot) -> Iterator[bytes]:
    """The whole batch as zip bytes, yielded as each document is read off disk."""
    sink = _Sink()
    with zipfile.ZipFile(sink, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr(CSV_NAME, sheet(snapshot))
        yield sink.take()

        for item in snapshot.items:
            entry = snapshot.entries.get(item["id"])
            if entry is None:
                continue
            with archive.open(entry.name, "w") as target, entry.path.open("rb") as document:
                while chunk := document.read(CHUNK):
                    target.write(chunk)
                    yield sink.take()
            yield sink.take()
    yield sink.take()


def sheet(snapshot: Snapshot) -> bytes:
    """`invoices.csv`: one row per invoice, every extracted field the batch has.

    Encoded with a BOM because Excel otherwise reads a CSV in the local
    codepage, which mangles every vendor name carrying an accent.
    """
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    writer.writerows(_row(item, snapshot.entries.get(item["id"])) for item in snapshot.items)
    return out.getvalue().encode("utf-8-sig")


def _row(item: dict, entry: Entry | None) -> list[str | None]:
    """One invoice as the 22 columns above. Blank where the parser found nothing."""
    invoice = item.get("invoice") or {}
    email = item.get("email") or {}
    document = item.get("document") or {}
    source = item.get("source") or {}
    extraction = item.get("extraction") or {}

    tool = extraction.get("tool")
    templates = ", ".join(extraction.get("templates") or [])
    return [
        text(invoice.get("invoice_number")),
        item.get("issued_on"),
        text(invoice.get("issuer")),
        text(invoice.get("vat_number")),
        text(invoice.get("company_number")),
        text(invoice.get("currency")),
        text(invoice.get("amount_untaxed")),
        text(invoice.get("amount_tax")),
        text(invoice.get("amount")),
        text(invoice.get("reference")),
        text(invoice.get("service_start")),
        text(invoice.get("desc")),
        entry.name if entry else None,
        text(document.get("bytes")),
        text(document.get("sha256")),
        # Where the figures were read from: the document's own origin when
        # there is one, otherwise the kind of text that was parsed.
        text(document.get("origin") or source.get("kind")),
        text(email.get("mailbox")),
        text(email.get("subject")),
        text(email.get("date")),
        # The two that settle a disputed row: the exact message a figure came
        # from, and the template that read it.
        text(email.get("message_id")),
        text(extraction.get("extracted_at")),
        text(f"{tool} / {templates}" if tool and templates else tool),
    ]


class _Sink:
    """A write-only file for ZipFile, whose bytes the caller takes as they land.

    Nothing here seeks, which is what makes the zip streamable: ZipFile detects
    a file it cannot rewind and records each entry's size in a trailing
    descriptor instead of patching its header afterwards.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    def write(self, data: bytes) -> int:
        self._buffer += data
        return len(data)

    def flush(self) -> None:
        """ZipFile flushes on close; there is nowhere for this to flush to."""

    def take(self) -> bytes:
        chunk = bytes(self._buffer)
        del self._buffer[:]
        return chunk
