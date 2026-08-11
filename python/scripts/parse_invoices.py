"""Scan a mailbox's inbox, parse whatever looks like an invoice, and file it.

Ops script — run and exit. Never imported by the application.
Usage: python scripts/parse_invoices.py [EMAIL] [--limit 10]

Prompts for the mailbox, reuses its Unipile account when one is already
connected, and only falls back to a hosted auth link when it is not.

Each message contributes candidate documents: PDF attachments, PDFs nested
inside forwarded .eml attachments, the text of those nested messages, and the
body of the message itself. invoice2data matches every candidate against its
template library, and that match is what separates an invoice from the rest of
the inbox — which is also the limit worth knowing about. Recognition is
per-issuer, so an invoice whose issuer has no template parses to nothing.
There are 215 built-in templates; add your own as YAML under
python/templates/invoice2data/ (auto-loaded) or point --templates elsewhere.

Every recognised invoice is written to python/.data/ — see app/invoice_store.py
for the layout. Documents are stored as the vendor sent them: an attached PDF
or image is kept as-is, and when the invoice is only linked from the body (some
vendors mail a receipt and put the PDF behind a "Download invoice" link) the
link is followed and the PDF stored. Following links means contacting the
sender's servers, which also trips their tracking redirects — pass
--no-follow-links to keep the scan strictly offline.

Reads UNIPILE_API_KEY and UNIPILE_DSN from python/.env or the repo-root .env.
"""

import argparse
import email
import email.policy
import html as html_module
import logging
import re
import sys
import tempfile
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.invoice_store import DATA_ROOT, Document, save_invoice  # noqa: E402
from app.unipile import (  # noqa: E402
    UnipileError,
    account_status,
    create_hosted_auth_link,
    credentials,
    download_attachment,
    expires_on,
    find_account,
    list_accounts,
    list_emails,
    wait_for_account,
)

log = get_logger("parse-invoices")

DEFAULT_EMAIL = "martinvkirov@gmail.com"
LINK_TTL_MINUTES = 15
CONNECT_TIMEOUT_SECONDS = 300

# Loaded on top of the built-ins when present, so project-specific issuers can
# be taught without touching the installed package.
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "invoice2data"

# invoice2data reads images too, but only through OCR (tesseract), which is not
# a dependency here — so images are never parsed. They are still filed when the
# invoice they belong to is recognised some other way.
PDF_EXTENSIONS = {"pdf"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "tif", "tiff"}
EML_MIMES = {"message/rfc822"}

# <style>/<script> bodies survive naive tag stripping and bury the receipt in
# CSS, so they go before the tags do.
SCRIPT_RE = re.compile(r"<(style|script)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
BLANK_RE = re.compile(r"\n{3,}")
ANCHOR_RE = re.compile(
    r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL
)
INVOICE_LINK_RE = re.compile(r"invoice|receipt|facture|rechnung|factura|billing|\.pdf", re.I)

# Enough links to cover a receipt that offers the document twice, few enough
# that a scan never turns into a crawl.
MAX_LINKS_PER_INVOICE = 5
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
LINK_TIMEOUT_SECONDS = 20


@dataclass
class Candidate:
    """One document handed to invoice2data, and what to keep if it parses."""

    path: Path
    kind: str
    source_name: str
    source_blob: bytes
    # Original markup, kept so invoice links can be followed if this parses.
    html: str | None = None
    # The vendor's own file, when this candidate is one.
    document: Document | None = None


def resolve_email(given: str | None) -> str:
    """The mailbox to scan: the argument, else the prompt, else the default."""
    if given:
        return given
    if not sys.stdin.isatty():
        return DEFAULT_EMAIL
    return input(f"Email address [{DEFAULT_EMAIL}]: ").strip() or DEFAULT_EMAIL


def tick(elapsed: int) -> None:
    print(f"\r  waiting for the account ({elapsed}s)...", end="", flush=True)


def clear_progress() -> None:
    print("\r" + " " * 60 + "\r", end="", flush=True)


def ensure_account(base: str, api_key: str, address: str, timeout: int, open_browser: bool) -> dict:
    """The connected account for a mailbox, running the auth wizard if needed."""
    accounts = list_accounts(base, api_key)
    existing = find_account(accounts, address)
    if existing:
        status = account_status(existing)
        print(f"{address} is already connected ({existing['id']}, status {status}).")
        if status != "OK":
            print(f"Status is {status}, not OK — the mail below may be stale.")
        return existing

    url = create_hosted_auth_link(
        base,
        api_key,
        {
            "type": "create",
            "providers": ["GOOGLE"],
            "api_url": base,
            "expiresOn": expires_on(LINK_TTL_MINUTES),
            "name": address,
        },
    )
    print(f"\n{address} is not connected yet. Connect it here:\n")
    print(f"  {url}\n")
    print(f"Sign in as {address} when Google asks — the link does not enforce it.")
    if open_browser and not webbrowser.open(url):
        print("Could not open a browser automatically — copy the URL above.")

    known = {a.get("id") for a in accounts}
    account = wait_for_account(base, api_key, known, address, timeout=timeout, on_tick=tick)
    clear_progress()
    if account is None:
        raise UnipileError(
            f"No account connected within {timeout}s. "
            "The link may have expired — re-run for a new one."
        )
    print(f"Connected {account.get('name')} as {account['id']}.")
    return account


def as_text(part_bytes: bytes, is_html: bool) -> str:
    """Readable text from a body part, so a template has something to match."""
    text = part_bytes.decode("utf-8", errors="replace")
    if is_html:
        text = SCRIPT_RE.sub(" ", text)
        text = TAG_RE.sub(" ", text)
        text = html_module.unescape(text)
        text = "\n".join(line.strip() for line in text.splitlines())
    return BLANK_RE.sub("\n\n", text).strip()


def invoice_links(markup: str) -> list[str]:
    """https links that advertise themselves as the invoice document."""
    found: list[str] = []
    for match in ANCHOR_RE.finditer(markup):
        href = html_module.unescape(match.group(1)).strip()
        label = TAG_RE.sub(" ", match.group(2))
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
    """Follow the invoice links in a body and keep the first real PDF."""
    if not markup:
        return None
    for url in invoice_links(markup):
        blob = fetch_pdf(url)
        if blob:
            return Document(name="invoice.pdf", blob=blob, origin="linked")
    return None


def attached_image(base: str, api_key: str, account_id: str, item: dict) -> Document | None:
    """A non-inline image attachment, downloaded only once an invoice is confirmed."""
    for attachment in item.get("attachments") or []:
        extension = (attachment.get("extension") or "").lower()
        if extension not in IMAGE_EXTENSIONS or attachment.get("inline"):
            continue
        try:
            blob = download_attachment(
                base, api_key, account_id, item["provider_id"], attachment["id"]
            )
        except UnipileError as exc:
            log.warning("could not download %s: %s", attachment.get("name"), exc)
            continue
        return Document(name=f"invoice.{extension}", blob=blob, origin="attachment")
    return None


def unpack_eml(blob: bytes, stem: str, workdir: Path) -> list[Candidate]:
    """Candidates hiding inside a forwarded message: its PDFs and its own text."""
    found: list[Candidate] = []
    try:
        message = email.message_from_bytes(blob, policy=email.policy.default)
    except Exception as exc:  # noqa: BLE001 — a malformed .eml must not stop the scan
        log.debug("could not parse %s as a message: %s", stem, exc)
        return found

    bodies: list[tuple[str, bool]] = []
    for index, part in enumerate(message.walk()):
        content_type = part.get_content_type()
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        filename = (part.get_filename() or "").lower()
        if content_type == "application/pdf" or filename.endswith(".pdf"):
            path = workdir / f"{stem}.nested{index}.pdf"
            path.write_bytes(payload)
            found.append(
                Candidate(
                    path=path,
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
        markup, is_html = max(bodies, key=lambda b: len(b[0]))
        path = workdir / f"{stem}.nested.txt"
        path.write_text(as_text(markup.encode(), is_html), encoding="utf-8")
        found.append(
            Candidate(
                path=path,
                kind="eml-nested-body",
                source_name="source.html" if is_html else "source.txt",
                source_blob=markup.encode(),
                html=markup if is_html else None,
            )
        )
    return found


def gather_candidates(
    base: str, api_key: str, account_id: str, item: dict, workdir: Path, include_body: bool
) -> list[Candidate]:
    """Every document worth handing to invoice2data for one message."""
    candidates: list[Candidate] = []
    stem = item["id"]

    for index, attachment in enumerate(item.get("attachments") or []):
        extension = (attachment.get("extension") or "").lower()
        mime = (attachment.get("mime") or "").lower()
        if extension not in PDF_EXTENSIONS and mime not in EML_MIMES:
            continue
        try:
            blob = download_attachment(
                base, api_key, account_id, item["provider_id"], attachment["id"]
            )
        except UnipileError as exc:
            log.warning("could not download %s: %s", attachment.get("name"), exc)
            continue

        if extension in PDF_EXTENSIONS:
            path = workdir / f"{stem}.{index}.pdf"
            path.write_bytes(blob)
            candidates.append(
                Candidate(
                    path=path,
                    kind="pdf-attachment",
                    source_name="invoice.pdf",
                    source_blob=blob,
                    document=Document("invoice.pdf", blob, "attachment"),
                )
            )
        else:
            candidates.extend(unpack_eml(blob, f"{stem}.{index}", workdir))

    if include_body:
        markup = item.get("body") or ""
        text = item.get("body_plain") or ""
        if not text.strip() and markup:
            text = as_text(markup.encode(), is_html=True)
        if text.strip():
            path = workdir / f"{stem}.body.txt"
            path.write_text(text, encoding="utf-8")
            candidates.append(
                Candidate(
                    path=path,
                    kind="email-body",
                    source_name="source.html" if markup else "source.txt",
                    source_blob=(markup or text).encode(),
                    html=markup or None,
                )
            )

    return candidates


def load_templates(extra_dir: Path | None):
    """Built-in templates, plus any local ones."""
    from invoice2data.extract.loader import read_templates

    templates = read_templates()
    directory = extra_dir or (TEMPLATE_DIR if TEMPLATE_DIR.is_dir() else None)
    if directory:
        local = read_templates(str(directory))
        print(f"Loaded {len(templates)} built-in and {len(local)} local template(s).")
        return templates + local
    print(f"Loaded {len(templates)} built-in template(s).")
    return templates


def parse(path: Path, templates) -> tuple[dict | None, str | None]:
    """(fields, error). Both None means the document simply is not an invoice.

    The error is reported rather than logged away: a missing PDF backend or an
    unreadable file would otherwise be indistinguishable from an ordinary
    email, and the scan would quietly under-report.
    """
    from invoice2data import extract_data
    from invoice2data.input import text as text_input

    module = text_input if path.suffix == ".txt" else None
    try:
        result = extract_data(str(path), templates=templates, input_module=module)
    except Exception as exc:  # noqa: BLE001 — one bad document must not stop the scan
        return None, f"{type(exc).__name__}: {exc}"
    return (result or None), None


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


def enrich(
    fields: dict, document: Document | None, workdir: Path, stem: str, templates
) -> tuple[dict, list[str], str | None]:
    """Re-parse the invoice's own document and merge what it adds.

    An emailed receipt states a total; the PDF behind it states the invoice
    number, the net/VAT split and the line items. Parsing only the body throws
    that away, so the document gets its own pass whenever one was retrieved.
    """
    if not document or not document.name.endswith(".pdf"):
        return fields, [], None

    path = workdir / f"{stem}.document.pdf"
    path.write_bytes(document.blob)
    parsed, error = parse(path, templates)
    if error or not parsed:
        return fields, [], error

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
        return fields, [], None

    return merge_fields(fields, parsed), [parsed.get("template_name") or "?"], None


def amount_of(fields: dict) -> str:
    amount = fields.get("amount")
    if amount is None:
        return ""
    return f"{amount} {fields.get('currency') or ''}".strip()


def date_of(fields: dict) -> str:
    value = fields.get("date")
    return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value or "")


def report(
    found: list[tuple[dict, dict, Candidate, Path]],
    scanned: int,
    candidates: int,
    errors: list[tuple[Path, str]],
) -> None:
    print(f"\nScanned {scanned} message(s), {candidates} candidate document(s).")
    if errors:
        print(f"{len(errors)} document(s) could not be read — these were NOT checked:")
        for path, message in errors:
            print(f"  {path.name}: {message}")
    if not found:
        print("No invoices recognised.")
        print(
            "invoice2data only reports a document when a template matches its issuer, "
            "so an unrecognised invoice looks the same as an ordinary email here.\n"
            f"Add a template under {TEMPLATE_DIR} to teach it a new issuer."
        )
        return

    print(f"{len(found)} invoice(s) recognised:\n")
    for item, fields, candidate, directory in found:
        document = candidate.document
        print(f"  {fields.get('issuer') or '(unknown issuer)'}")
        print(f"    email     : {item.get('subject') or '(no subject)'}")
        print(f"    invoice # : {fields.get('invoice_number') or '-'}")
        print(f"    date      : {date_of(fields) or '-'}")
        print(f"    amount    : {amount_of(fields) or '-'}")
        if fields.get("amount_tax") is not None:
            print(f"    net / VAT : {fields.get('amount_untaxed')} / {fields['amount_tax']}")
        print(
            f"    document  : {document.name} ({document.origin})"
            if document
            else "    document  : none — the invoice was the email body"
        )
        print(f"    saved     : {directory}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("email", nargs="?", default=None, help="mailbox to scan (default: prompt)")
    parser.add_argument("--limit", type=int, default=10, help="messages to scan (default: 10)")
    parser.add_argument(
        "--templates", type=Path, default=None, help=f"extra template dir (default: {TEMPLATE_DIR})"
    )
    parser.add_argument(
        "--data-dir", type=Path, default=DATA_ROOT, help=f"where invoices are filed ({DATA_ROOT})"
    )
    parser.add_argument(
        "--no-body", action="store_true", help="only parse attachments, not message bodies"
    )
    parser.add_argument(
        "--no-follow-links",
        action="store_true",
        help="do not fetch invoices linked from a message body",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=CONNECT_TIMEOUT_SECONDS,
        help=f"seconds to wait for a new connection (default: {CONNECT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--no-open", action="store_true", help="print the auth link without opening a browser"
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    # invoice2data logs "No template for ..." at ERROR for every document that
    # is not an invoice. In a mailbox that is the common case, not a problem,
    # and the summary reports it — so silence it below CRITICAL.
    if not get_settings().debug_logs_enabled:
        logging.getLogger("invoice2data").setLevel(logging.CRITICAL)

    try:
        base, api_key = credentials()
        address = resolve_email(args.email)
        account = ensure_account(base, api_key, address, args.timeout, not args.no_open)
        items = list_emails(base, api_key, account["id"], limit=args.limit)
    except UnipileError as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc

    if not items:
        print(f"\nNo inbox mail for {address} — nothing to parse.")
        return

    templates = load_templates(args.templates)
    tool = f"invoice2data {version('invoice2data')}"

    with tempfile.TemporaryDirectory(prefix="invoicepilot-") as temp:
        workdir = Path(temp)
        found: list[tuple[dict, dict, Candidate, Path]] = []
        errors: list[tuple[Path, str]] = []
        total_candidates = 0

        print(f"\nScanning {len(items)} message(s) in {address}:\n")
        for item in items:
            candidates = gather_candidates(
                base, api_key, account["id"], item, workdir, not args.no_body
            )
            total_candidates += len(candidates)

            hits = 0
            for candidate in candidates:
                fields, error = parse(candidate.path, templates)
                if error:
                    errors.append((candidate.path, error))
                    continue
                if not fields:
                    continue

                # Only now, with an invoice confirmed, is it worth spending a
                # download on the document it refers to.
                if candidate.document is None:
                    candidate.document = attached_image(base, api_key, account["id"], item)
                if candidate.document is None and not args.no_follow_links:
                    candidate.document = linked_document(candidate.html)

                used = [fields.get("template_name") or "?"]
                parsed_from = [candidate.kind]
                fields, extra_templates, document_error = enrich(
                    fields, candidate.document, workdir, item["id"], templates
                )
                if document_error:
                    errors.append((Path(candidate.document.name), document_error))
                if extra_templates:
                    used.extend(extra_templates)
                    parsed_from.append(f"document:{candidate.document.name}")

                directory = save_invoice(
                    address,
                    item,
                    fields,
                    source_name=candidate.source_name,
                    source_blob=candidate.source_blob,
                    source_kind=candidate.kind,
                    document=candidate.document,
                    tool=tool,
                    parsed_from=parsed_from,
                    templates=used,
                    root=args.data_dir,
                )
                found.append((item, fields, candidate, directory))
                hits += 1

            mark = f"{hits} invoice(s)" if hits else "no invoice"
            print(f"  {(item.get('subject') or '(no subject)')[:52]:54} {mark}")

        report(found, len(items), total_candidates, errors)
        if found:
            print(f"Filed under {args.data_dir}")


if __name__ == "__main__":
    main()
