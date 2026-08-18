"""Scanning connected mailboxes for invoices — the job the CLI and API share.

Returns results and reports progress through a callback; it never prints and
never decides how anything is displayed. That is what lets one pipeline serve
both a terminal report and a polled HTTP job without either concern leaking in.

Each recognised invoice is written twice: to .data/ for the vendor's own
document, and to Postgres for the metadata the dashboard queries. Both receive
the identical payload, because invoice_store builds it once and hands it back.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from importlib.metadata import version

from invoicepilot import extract
from invoicepilot.accounts import list_connected
from invoicepilot.core.db import session_scope
from invoicepilot.core.logging import get_logger
from invoicepilot.invoice_store import mail_token, save_invoice
from invoicepilot.invoices import row_id, save
from invoicepilot.unipile import UnipileError, credentials, download_attachment, list_emails

log = get_logger(__name__)

DEFAULT_LIMIT = 20


@dataclass(frozen=True)
class ScanError:
    """One document that could not be read.

    Reported rather than logged away: an unreadable PDF is not the same as an
    ordinary email, and a scan that conflated them would under-report silently.
    """

    mailbox: str
    subject: str
    detail: str


@dataclass(frozen=True)
class Progress:
    """Where a scan has got to, for whoever is watching it.

    `mailbox` and `subject` are the message in hand. The three counts are for
    the scan as a whole, not the mailbox in hand: scan_account can only count
    its own, so scan_all adds the finished mailboxes' tally back on before the
    report goes out. `messages_total` is therefore what is known so far — it
    grows as each further mailbox is listed.
    """

    mailbox: str
    subject: str
    messages_scanned: int
    messages_total: int
    invoices_found: int


@dataclass(frozen=True)
class ScanResult:
    mailboxes: tuple[str, ...] = ()
    messages_scanned: int = 0
    invoices_found: int = 0
    invoices_new: int = 0
    errors: tuple[ScanError, ...] = field(default=())

    def merge(self, other: "ScanResult") -> "ScanResult":
        return ScanResult(
            mailboxes=self.mailboxes + other.mailboxes,
            messages_scanned=self.messages_scanned + other.messages_scanned,
            invoices_found=self.invoices_found + other.invoices_found,
            invoices_new=self.invoices_new + other.invoices_new,
            errors=self.errors + other.errors,
        )


OnProgress = Callable[[Progress], None]


def scan_account(
    base: str,
    api_key: str,
    account: dict,
    *,
    limit: int = DEFAULT_LIMIT,
    follow_links: bool = True,
    on_progress: OnProgress | None = None,
) -> ScanResult:
    """Parse the most recent `limit` messages in one mailbox and file what parses."""
    account_id = account["id"]
    mailbox = account.get("name") or account_id

    messages = list_emails(base, api_key, account_id, limit=limit)
    if not messages:
        return ScanResult(mailboxes=(mailbox,))

    tool = f"invoice2data {version('invoice2data')}"
    errors: list[ScanError] = []
    found = new = 0

    for index, message in enumerate(messages, start=1):
        subject = message.get("subject") or "(no subject)"

        def fetch(attachment_id: str, message: dict = message) -> bytes:
            return download_attachment(
                base, api_key, account_id, message["provider_id"], attachment_id
            )

        for candidate in extract.candidates(message, fetch):
            invoice, error = extract.extract(candidate, message, fetch, follow_links=follow_links)
            if error:
                errors.append(ScanError(mailbox, subject, error))
                continue
            if invoice is None:
                continue

            errors.extend(ScanError(mailbox, subject, e) for e in invoice.errors)
            _, payload = save_invoice(
                mailbox,
                message,
                invoice.fields,
                source_name=candidate.source_name,
                source_blob=candidate.source_blob,
                source_kind=invoice.kind,
                document=invoice.document,
                tool=tool,
                parsed_from=list(invoice.parsed_from),
                templates=list(invoice.templates),
            )
            invoice_id = row_id(
                invoice.fields,
                mail_token(message.get("message_id"), message.get("id") or ""),
            )
            # One transaction per invoice, rather than one around the whole
            # scan. A scan spends minutes downloading attachments and fetching
            # vendor PDFs; holding a write transaction open across that would
            # mean an interruption discarded every row while leaving every
            # folder on disk — the two sinks would drift apart.
            with session_scope() as session:
                if save(session, invoice_id, payload):
                    new += 1
            found += 1

        if on_progress:
            on_progress(Progress(mailbox, subject, index, len(messages), found))

    return ScanResult(
        mailboxes=(mailbox,),
        messages_scanned=len(messages),
        invoices_found=found,
        invoices_new=new,
        errors=tuple(errors),
    )


def scan_all(
    *,
    limit: int = DEFAULT_LIMIT,
    follow_links: bool = True,
    on_progress: OnProgress | None = None,
) -> ScanResult:
    """Scan every connected mailbox. Raises UnipileError if none can be reached."""
    base, api_key = credentials()
    accounts = list_connected(base, api_key)
    if not accounts:
        raise UnipileError("No mailboxes are connected — connect one before scanning.")

    result = ScanResult()
    for account in accounts:
        # scan_account counts from zero, so its reports are shifted by what the
        # finished mailboxes already came to. Without this a watcher sees the
        # count fall back to 1 every time the scan crosses into another
        # mailbox. `done` is bound as a default so each account's relay holds
        # the tally as it stood when the account started rather than the loop
        # variable's latest value.
        def relay(progress: Progress, done: ScanResult = result) -> None:
            on_progress(
                replace(
                    progress,
                    messages_scanned=done.messages_scanned + progress.messages_scanned,
                    messages_total=done.messages_scanned + progress.messages_total,
                    invoices_found=done.invoices_found + progress.invoices_found,
                )
            )

        try:
            result = result.merge(
                scan_account(
                    base,
                    api_key,
                    account,
                    limit=limit,
                    follow_links=follow_links,
                    on_progress=relay if on_progress else None,
                )
            )
        except UnipileError as exc:
            # One unreachable mailbox must not abandon the others.
            mailbox = account.get("name") or account["id"]
            log.warning("could not scan %s: %s", mailbox, exc)
            result = result.merge(
                ScanResult(mailboxes=(mailbox,), errors=(ScanError(mailbox, "", str(exc)),))
            )
    return result
