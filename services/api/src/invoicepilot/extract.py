"""Turning the documents attached to a message into invoice fields.

invoice2data only reports a document when one of its templates matches the
issuer, and that match is what separates an invoice from the rest of a mailbox.
Recognition is therefore per-issuer: an invoice from a vendor with no template
extracts to nothing, and looks identical to an ordinary email. There are ~215
built-in templates; project-specific issuers are taught by adding YAML under
this package's own templates/invoice2data/ rather than by touching the
installed invoice2data package.

This module is pure with one deliberate exception. It never prints, never
touches the invoice store, and reaches Unipile only through the `fetch`
callable its caller supplies — so it can be exercised against stored bytes with
no network at all. The exception is `linked_document`, which contacts the
vendor's own servers; it is opt-in per call and never invoked implicitly.
"""

import email
import email.policy
import html as html_module
import re
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

from invoicepilot.core.logging import get_logger
from invoicepilot.invoice_store import DATA_ROOT, Document

log = get_logger(__name__)

# Loaded on top of the built-ins when present. Package data, resolved downward
# from this module, so it is found the same way in a checkout and in a wheel.
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "invoice2data"

# Where learn.py writes the templates it drafts. Under the data directory
# rather than beside the package's own, because the package ships inside a
# container image: a template written there is lost on the next rebuild, while
# this sits on the volume that already holds the invoices.
GENERATED_TEMPLATE_DIR = DATA_ROOT / "templates"

# invoice2data reads images only through OCR (tesseract), which is not a
# dependency here — so images are never parsed. They are still filed when the
# invoice they belong to is recognised some other way.
PDF_EXTENSIONS = frozenset({"pdf"})
IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "webp", "tif", "tiff"})
EML_MIMES = frozenset({"message/rfc822"})

# <style>/<script> bodies survive naive tag stripping and bury the receipt in
# CSS, so they go before the tags do.
SCRIPT_RE = re.compile(r"<(style|script)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
BLANK_RE = re.compile(r"\n{3,}")
INVOICE_LINK_RE = re.compile(r"invoice|receipt|facture|rechnung|factura|billing|\.pdf", re.I)

# Enough links to cover a receipt that offers the document twice, few enough
# that a scan never turns into a crawl.
MAX_LINKS_PER_INVOICE = 5
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
LINK_TIMEOUT_SECONDS = 20

# Given an attachment id, its bytes. Injected so this module never imports a
# transport, and so tests can hand it stored blobs.
Fetch = Callable[[str], bytes]


@dataclass(frozen=True)
class Candidate:
    """One document to hand invoice2data, and what to keep if it parses."""

    # What gets parsed, and the extension invoice2data picks its reader from.
    blob: bytes
    suffix: str
    kind: str
    # What to file as the source: the original markup, not the stripped text.
    source_name: str
    source_blob: bytes
    # Original markup, kept so invoice links can be followed if this parses.
    html: str | None = None
    # The vendor's own file, when this candidate is one.
    document: Document | None = None


@dataclass(frozen=True)
class Extracted:
    """A recognised invoice, and the trail of how it was recognised."""

    fields: dict
    kind: str
    templates: tuple[str, ...] = ()
    parsed_from: tuple[str, ...] = ()
    document: Document | None = None
    # Documents that could not be read. Reported rather than logged away: an
    # unreadable PDF is not the same as an ordinary email, and a scan that
    # conflated them would silently under-report.
    errors: tuple[str, ...] = field(default=())


@lru_cache(maxsize=1)
def templates() -> list:
    """Built-in templates, then the repository's, then the generated ones.

    Cached because a server scans repeatedly and this reads ~215 YAML files.
    Generated templates come last and carry a lower `priority`, so they can
    never win a match over one a person wrote — which matters more than the
    ordering suggests, because invoice2data runs only the *first* template
    whose keywords match and does not fall through to the next when its fields
    come up empty. A sloppy generated template that outranked a curated one
    would not merely lose to it; it would silently block it.
    """
    from invoice2data.extract.loader import read_templates

    loaded = read_templates()
    for directory in (TEMPLATE_DIR, GENERATED_TEMPLATE_DIR):
        if not directory.is_dir():
            continue
        extra = read_templates(str(directory))
        log.debug("loaded %d template(s) from %s", len(extra), directory)
        loaded = loaded + extra
    return loaded


def forget_templates() -> None:
    """Drop the cache, so a template written since this process started loads.

    Only learn.py needs this, and only right after it saves one — a long-lived
    API process would otherwise go on failing to recognise the issuer it just
    taught itself until the next restart.
    """
    templates.cache_clear()


def parse_bytes(blob: bytes, suffix: str) -> tuple[dict | None, str | None]:
    """(fields, error). Both None means the document simply is not an invoice.

    invoice2data reads from a path, so one is materialised here rather than
    threaded through every caller as a working directory.
    """
    from invoice2data import extract_data
    from invoice2data.input import text as text_input

    with tempfile.NamedTemporaryFile(suffix=suffix, prefix="invoicepilot-") as handle:
        handle.write(blob)
        handle.flush()
        module = text_input if suffix == ".txt" else None
        try:
            result = extract_data(handle.name, templates=templates(), input_module=module)
        except Exception as exc:  # noqa: BLE001 — one bad document must not stop a scan
            return None, f"{type(exc).__name__}: {exc}"
    if not result:
        return None, None

    # invoice2data builds `desc` from the issuer the template *declares*, not
    # the one the document yielded. That is only the same thing for a template
    # written per vendor; the Stripe templates here capture the issuer, so
    # every vendor Stripe bills for would otherwise be described as Stripe.
    if result.get("issuer"):
        result["desc"] = f"Invoice from {result['issuer']}"
    return result, None


def readable_text(blob: bytes, is_html: bool) -> str:
    """Readable text from a body part, so a template has something to match."""
    text = blob.decode("utf-8", errors="replace")
    if is_html:
        text = SCRIPT_RE.sub(" ", text)
        text = TAG_RE.sub(" ", text)
        text = html_module.unescape(text)
        text = "\n".join(line.strip() for line in text.splitlines())
    return BLANK_RE.sub("\n\n", text).strip()


class _Anchors(HTMLParser):
    r"""Collects every `<a href>` in a body as (href, link text).

    A parser rather than a regex, because vendor mail is reliably malformed and
    a regex has to guess where an anchor ends. Bolt's receipts are the case in
    point: a formatter puts the closing bracket on its own line, `</a\n>`, so a
    `</a>` pattern misses that close and runs on to the next anchor's — eating
    the "Download PDF invoice" link, which is the one this module exists to
    follow. HTMLParser also unescapes attribute values on its own.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def _close_open_anchor(self) -> None:
        if self._href is not None:
            self.links.append((self._href, "".join(self._text)))
        self._href, self._text = None, []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        # An unclosed anchor is closed by the next one rather than discarded:
        # what it linked to is still a link, and its text is still its label.
        self._close_open_anchor()
        self._href = dict(attrs).get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._close_open_anchor()

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def close(self) -> None:
        super().close()
        self._close_open_anchor()


def invoice_links(markup: str) -> list[str]:
    """https links that advertise themselves as the invoice document."""
    parser = _Anchors()
    parser.feed(markup)
    parser.close()

    found: list[str] = []
    for raw, label in parser.links:
        href = (raw or "").strip()
        if not href.lower().startswith("https://"):
            continue
        if not (INVOICE_LINK_RE.search(label) or INVOICE_LINK_RE.search(href)):
            continue
        if href not in found:
            found.append(href)
        if len(found) >= MAX_LINKS_PER_INVOICE:
            break
    return found


def fetch_pdf(url: str) -> bytes | None:
    """The PDF behind a link, or None if it is anything else.

    Vendors hide invoices behind login walls and tracking redirects, so most of
    these return HTML. The magic bytes decide, not the content-type header.
    """
    request = urllib.request.Request(url, headers={"Accept": "application/pdf,*/*"})
    try:
        with urllib.request.urlopen(request, timeout=LINK_TIMEOUT_SECONDS) as response:
            blob = response.read(MAX_DOCUMENT_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.debug("could not fetch %s: %s", url, exc)
        return None
    if len(blob) > MAX_DOCUMENT_BYTES or not blob.startswith(b"%PDF-"):
        return None
    return blob


def linked_document(markup: str | None) -> Document | None:
    """Follow the invoice links in a body and keep the first real PDF.

    The one call here that contacts the vendor rather than Unipile — which also
    trips their tracking redirects. Callers opt in.
    """
    if not markup:
        return None
    for url in invoice_links(markup):
        blob = fetch_pdf(url)
        if blob:
            return Document(name="invoice.pdf", blob=blob, origin="linked")
    return None


def attached_image(message: dict, fetch: Fetch) -> Document | None:
    """A non-inline image attachment, worth downloading only once an invoice is confirmed."""
    for attachment in message.get("attachments") or []:
        extension = (attachment.get("extension") or "").lower()
        if extension not in IMAGE_EXTENSIONS or attachment.get("inline"):
            continue
        try:
            blob = fetch(attachment["id"])
        except Exception as exc:  # noqa: BLE001 — a failed download must not stop a scan
            log.warning("could not download %s: %s", attachment.get("name"), exc)
            continue
        return Document(name=f"invoice.{extension}", blob=blob, origin="attachment")
    return None


def nested_candidates(blob: bytes) -> list[Candidate]:
    """Candidates hiding inside a forwarded message: its PDFs and its own text."""
    found: list[Candidate] = []
    try:
        message = email.message_from_bytes(blob, policy=email.policy.default)
    except Exception as exc:  # noqa: BLE001 — a malformed .eml must not stop a scan
        log.debug("could not parse a nested message: %s", exc)
        return found

    bodies: list[tuple[str, bool]] = []
    for part in message.walk():
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        content_type = part.get_content_type()
        filename = (part.get_filename() or "").lower()
        if content_type == "application/pdf" or filename.endswith(".pdf"):
            found.append(
                Candidate(
                    blob=payload,
                    suffix=".pdf",
                    kind="eml-nested-pdf",
                    source_name="invoice.pdf",
                    source_blob=payload,
                    document=Document("invoice.pdf", payload, "nested-attachment"),
                )
            )
        elif content_type in ("text/plain", "text/html"):
            bodies.append((payload.decode("utf-8", errors="replace"), content_type == "text/html"))

    # The forwarded receipt is often the message body itself, not a file on it.
    if bodies:
        markup, is_html = max(bodies, key=lambda body: len(body[0]))
        found.append(
            Candidate(
                blob=readable_text(markup.encode(), is_html).encode(),
                suffix=".txt",
                kind="eml-nested-body",
                source_name="source.html" if is_html else "source.txt",
                source_blob=markup.encode(),
                html=markup if is_html else None,
            )
        )
    return found


def body_text(message: dict) -> str:
    """A message's body as readable text — the provider's, or the markup stripped.

    Shared with the gate, so what decides a message is worth teaching an issuer
    for is exactly what a template would have been matched against.
    """
    text = message.get("body_plain") or ""
    markup = message.get("body") or ""
    if not text.strip() and markup:
        text = readable_text(markup.encode(), is_html=True)
    return text


def candidates(message: dict, fetch: Fetch, *, include_body: bool = True) -> list[Candidate]:
    """Every document in one message worth handing to invoice2data."""
    found: list[Candidate] = []

    for attachment in message.get("attachments") or []:
        extension = (attachment.get("extension") or "").lower()
        mime = (attachment.get("mime") or "").lower()
        if extension not in PDF_EXTENSIONS and mime not in EML_MIMES:
            continue
        try:
            blob = fetch(attachment["id"])
        except Exception as exc:  # noqa: BLE001 — a failed download must not stop a scan
            log.warning("could not download %s: %s", attachment.get("name"), exc)
            continue

        if extension in PDF_EXTENSIONS:
            found.append(
                Candidate(
                    blob=blob,
                    suffix=".pdf",
                    kind="pdf-attachment",
                    source_name="invoice.pdf",
                    source_blob=blob,
                    document=Document("invoice.pdf", blob, "attachment"),
                )
            )
        else:
            found.extend(nested_candidates(blob))

    if include_body:
        markup = message.get("body") or ""
        text = body_text(message)
        if text.strip():
            found.append(
                Candidate(
                    blob=text.encode(),
                    suffix=".txt",
                    kind="email-body",
                    source_name="source.html" if markup else "source.txt",
                    source_blob=(markup or text).encode(),
                    html=markup or None,
                )
            )

    return found


def candidate_text(candidate: Candidate) -> str:
    """The text invoice2data would match this candidate against.

    What a generated template has to be written for, and what the model that
    drafts it is shown — never the raw bytes, which for a PDF say nothing.
    """
    if candidate.suffix == ".txt":
        return candidate.blob.decode("utf-8", errors="replace")

    from invoice2data.input import pdfium

    with tempfile.NamedTemporaryFile(suffix=candidate.suffix, prefix="invoicepilot-") as handle:
        handle.write(candidate.blob)
        handle.flush()
        try:
            return pdfium.to_text(handle.name) or ""
        except Exception as exc:  # noqa: BLE001 — an unreadable document is not an error here
            log.debug("could not read %s as text: %s", candidate.source_name, exc)
            return ""


def merge_fields(body: dict, document: dict) -> dict:
    """Body fields, overridden by anything the document states.

    The document is the authority: it is the invoice, while the body is a
    summary of it. Only non-empty values override, so a field the document
    omits keeps whatever the body found.
    """
    merged = dict(body)
    for key, value in document.items():
        if value not in (None, ""):
            merged[key] = value
    return merged


def enrich(fields: dict, document: Document | None) -> tuple[dict, tuple[str, ...], str | None]:
    """Re-parse the invoice's own document and merge what it adds.

    An emailed receipt states a total; the PDF behind it states the invoice
    number, the net/VAT split and the line items. Parsing only the body throws
    that away, so the document gets its own pass whenever one was retrieved.
    """
    if not document or not document.name.endswith(".pdf"):
        return fields, (), None

    parsed, error = parse_bytes(document.blob, ".pdf")
    if error or not parsed:
        return fields, (), error

    # A linked PDF is only trusted when it agrees on who issued it — following
    # a link is not proof the document belongs to this invoice.
    body_issuer = (fields.get("issuer") or "").strip().lower()
    doc_issuer = (parsed.get("issuer") or "").strip().lower()
    if body_issuer and doc_issuer and body_issuer != doc_issuer:
        log.warning(
            "%s parsed as %r, not %r — keeping the body's fields.",
            document.name,
            parsed.get("issuer"),
            fields.get("issuer"),
        )
        return fields, (), None

    return merge_fields(fields, parsed), (parsed.get("template_name") or "?",), None


def extract(
    candidate: Candidate,
    message: dict,
    fetch: Fetch,
    *,
    follow_links: bool = True,
) -> tuple[Extracted | None, str | None]:
    """(invoice, error) for one candidate. Both None means it is not an invoice.

    Resolving the vendor's document — downloading an image, or following a link
    out to the vendor — happens only after the invoice is confirmed, so an
    ordinary email never costs a request.
    """
    fields, error = parse_bytes(candidate.blob, candidate.suffix)
    if error or not fields:
        return None, error

    document = candidate.document
    if document is None:
        document = attached_image(message, fetch)
    if document is None and follow_links:
        document = linked_document(candidate.html)

    used = [fields.get("template_name") or "?"]
    parsed_from = [candidate.kind]
    fields, extra, document_error = enrich(fields, document)
    if extra:
        used.extend(extra)
        parsed_from.append(f"document:{document.name}")

    return (
        Extracted(
            fields=fields,
            kind=candidate.kind,
            templates=tuple(used),
            parsed_from=tuple(parsed_from),
            document=document,
            errors=(document_error,) if document_error else (),
        ),
        None,
    )
