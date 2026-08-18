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
from datetime import UTC, datetime, timedelta
from importlib.metadata import version

from invoicepilot import extract, gate, learn, mailboxes
from invoicepilot.accounts import list_connected
from invoicepilot.core.db import session_scope
from invoicepilot.core.logging import get_logger
from invoicepilot.invoice_store import mail_token, save_invoice, workspace_root
from invoicepilot.invoices import row_id, save
from invoicepilot.unipile import UnipileError, credentials, download_attachment, iter_emails

log = get_logger(__name__)

# How far back a mailbox nobody has scanned before reaches. A rolling window
# rather than calendar months: "this month and last" is 31 days on the 1st and
# 61 on the 31st, which would make a first scan's depth depend on the day the
# button happened to be pressed.
SEED_LOOKBACK = timedelta(days=60)

# How far back of already-scanned mail each scan re-reads. A message can carry
# a date behind its delivery — sender clock skew, a delayed relay — so one
# dated 23:58 can arrive after the mailbox was scanned through 23:59. Re-read
# mail costs time; mail stepped over is never seen again.
RESCAN_OVERLAP = timedelta(days=1)

# A backstop against a mailbox that somehow matches thousands of messages, not
# a page size. Hitting it means a scan could not finish the range it asked for,
# which is reported rather than quietly rounded off — see scan_account.
MAX_MESSAGES_PER_SCAN = 500

# How many issuers one scan may teach itself. learn.teach already records every
# domain it tries, so the real bound is the number of distinct senders and this
# never binds twice; it exists so that the *first* scan of an unusually varied
# mailbox cannot spend without limit before anyone sees the result.
MAX_TEMPLATES_PER_SCAN = 8

# Mail worth opening. Unipile hands this to the provider as a full-text query
# over subject, body, attachment filenames and attachment contents, so it is
# the difference between parsing every message in a mailbox and parsing the few
# that could be invoices.
#
# Multilingual because the vendors are: templates/invoice2data/bolt_invoice_bg.yml
# parses Bulgarian, so an English-only list would miss the very document it was
# written for. Widening this costs a little scan time and nothing else;
# narrowing it loses invoices silently, so it errs wide.
INVOICE_KEYWORDS = (
    "invoice",
    "invoices",
    "receipt",
    "receipts",
    "billing",
    "statement",
    "subscription",
    "payment",
    "paid",
    # bg — the Bolt PDF template's own language.
    "Фактура",
    "фактури",
    "разписка",
    "плащане",
    # de, fr, es/ro, it
    "Rechnung",
    "facture",
    "factura",
    "fattura",
)


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


def keyword_query(keywords: tuple[str, ...] = INVOICE_KEYWORDS) -> str:
    """`a OR b OR c`, the only joining the provider understands.

    Verified against a live mailbox: a space between terms means AND and a
    comma means nothing at all — both match no mail whatsoever.
    """
    return " OR ".join(keywords)


def teachable_text(candidates: list) -> str:
    """The one document from a message worth writing a template for.

    A vendor's own attachment wins over the mail that carried it: the PDF is
    the invoice, while the body is a summary of it, and only the document
    states the invoice number and the VAT split. Failing that, the longest
    text, which is the body rather than a footer or a signature block.
    """
    longest = ""
    for candidate in candidates:
        text = extract.candidate_text(candidate)
        if candidate.document is not None and text.strip():
            return text
        if len(text) > len(longest):
            longest = text
    return longest


def scan_from(workspace_id: str, mailbox: str, since: datetime | None = None) -> datetime:
    """The oldest message date this mailbox's next scan should reach.

    An explicit `since` wins. Otherwise this workspace's own watermark for the
    mailbox, rolled back by RESCAN_OVERLAP, and for one never scanned, the seed
    window. Another workspace's progress on the same address does not count:
    they have their own invoices to show for it and this one has none.

    A watermark older than the seed window is honoured rather than clamped to
    it. Clamping would advance the mark past mail nobody had looked at, and an
    invoice skipped that way is skipped permanently; the keyword filter is what
    makes honouring it affordable.
    """
    if since:
        return since
    with session_scope() as session:
        mark = mailboxes.watermark(session, workspace_id, mailbox)
    if mark:
        return mark - RESCAN_OVERLAP
    return datetime.now(UTC) - SEED_LOOKBACK


def message_date(message: dict) -> datetime | None:
    """A message's own date, or None when it has none or one that will not parse."""
    raw = message.get("date")
    if not raw:
        return None
    try:
        at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def scan_account(
    base: str,
    api_key: str,
    workspace_id: str,
    account: dict,
    *,
    follow_links: bool = True,
    keywords: bool = True,
    learn_issuers: bool = True,
    since: datetime | None = None,
    on_progress: OnProgress | None = None,
) -> ScanResult:
    """Parse one mailbox's unscanned mail and file what parses, for one workspace.

    Which mail that is comes from the mailbox's watermark, which this advances
    on the way out — so a second call straight afterwards has almost nothing
    left to do. `since` overrides the watermark for a backfill; `keywords=False`
    drops the invoice-word filter, which is how you measure what it skips.

    Everything written lands under the workspace: the rows, the watermark and
    the documents on disk. Two workspaces scanning the same address produce two
    independent sets of all three.
    """
    account_id = account["id"]
    mailbox = account.get("name") or account_id

    after = scan_from(workspace_id, mailbox, since)
    messages, capped = iter_emails(
        base,
        api_key,
        account_id,
        after=after,
        search=keyword_query() if keywords else None,
        cap=MAX_MESSAGES_PER_SCAN,
    )
    if not messages:
        return ScanResult(mailboxes=(mailbox,))

    tool = f"invoice2data {version('invoice2data')}"
    errors: list[ScanError] = []
    found = new = taught = 0

    def file_candidates(candidates: list, message: dict, subject: str, fetch: extract.Fetch) -> int:
        """Parse and store whatever of one message parses. Returns how many."""
        nonlocal found, new
        filed = 0
        for candidate in candidates:
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
                root=workspace_root(workspace_id),
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
                if save(session, workspace_id, invoice_id, payload):
                    new += 1
            found += 1
            filed += 1
        return filed

    for index, message in enumerate(messages, start=1):
        subject = message.get("subject") or "(no subject)"

        def fetch(attachment_id: str, message: dict = message) -> bytes:
            return download_attachment(
                base, api_key, account_id, message["provider_id"], attachment_id
            )

        candidates = extract.candidates(message, fetch)
        filed = file_candidates(candidates, message, subject, fetch)

        # Nothing parsed. Either it is not an invoice, or it is one from an
        # issuer nobody has taught — which the gate separates without a
        # request, so only the second case reaches learn.teach.
        if not filed and learn_issuers and taught < MAX_TEMPLATES_PER_SCAN:
            sender = (message.get("from_attendee") or {}).get("identifier") or ""
            if gate.looks_like_invoice(
                sender,
                extract.body_text(message),
                has_attachment=bool(message.get("attachments")),
            ):
                try:
                    path = learn.teach(teachable_text(candidates), sender)
                except Exception as exc:  # noqa: BLE001 — one issuer must not end a scan
                    log.warning("could not draft a template for %s: %s", sender, exc)
                    errors.append(ScanError(mailbox, subject, f"could not draft a template: {exc}"))
                    path = None
                if path:
                    taught += 1
                    # Re-run the same message against the template it just
                    # produced, so the invoice that paid for it is also the
                    # first one filed by it.
                    filed = file_candidates(candidates, message, subject, fetch)

        if on_progress:
            on_progress(Progress(mailbox, subject, index, len(messages), found))

    # Only now, and only over a range that was scanned end to end. `messages`
    # is oldest-first, so the last dated one is the newest processed — the
    # honest mark. now() would claim mail the provider had not yet synced.
    if capped:
        # The uncollected messages are older than every one just handled, which
        # no single watermark can express. Left where it was, so the next scan
        # covers the same range again rather than stepping over the remainder.
        detail = (
            f"Stopped after {MAX_MESSAGES_PER_SCAN} messages, so mail older than "
            f"{messages[0].get('date')} in this range is still unscanned. "
            f"Run `invoicepilot scan --since` to work through it."
        )
        log.warning("%s: %s", mailbox, detail)
        errors.append(ScanError(mailbox, "", detail))
    else:
        newest = max((d for d in map(message_date, messages) if d), default=None)
        if newest:
            with session_scope() as session:
                mailboxes.set_watermark(session, workspace_id, mailbox, newest)

    return ScanResult(
        mailboxes=(mailbox,),
        messages_scanned=len(messages),
        invoices_found=found,
        invoices_new=new,
        errors=tuple(errors),
    )


def scan_all(
    workspace_id: str,
    allowed: list[str],
    *,
    follow_links: bool = True,
    keywords: bool = True,
    learn_issuers: bool = True,
    since: datetime | None = None,
    on_progress: OnProgress | None = None,
) -> ScanResult:
    """Scan this workspace's connected mailboxes.

    `allowed` is the workspace's own account ids. Raises UnipileError when it
    owns no reachable mailbox — the tenant's other accounts are not this
    workspace's to scan, so a deployment full of them still counts as none.
    """
    base, api_key = credentials()
    accounts = list_connected(base, api_key, allowed)
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
                    workspace_id,
                    account,
                    follow_links=follow_links,
                    keywords=keywords,
                    learn_issuers=learn_issuers,
                    since=since,
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
