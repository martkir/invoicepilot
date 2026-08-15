"""Pydantic request/response models for the API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.process import DEFAULT_LIMIT

# Enough to catch a typed address that cannot be delivered, without taking a
# dependency on a full RFC 5322 validator for one field.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
# A name goes into the mail's heading and its footer; it is a person's name,
# not a field to write prose in.
NAME_LENGTH = 120


class HealthResponse(BaseModel):
    status: str
    version: str


class Account(BaseModel):
    id: str
    email: str
    # Unipile's sync status: OK, CREDENTIALS, ERROR, ...
    status: str


class ConnectLink(BaseModel):
    url: str


class ScanRequest(BaseModel):
    # Messages per mailbox. The default is the scanner's own, imported rather
    # than restated so the two cannot drift.
    limit: int = Field(default=DEFAULT_LIMIT, ge=1)
    # Following a link contacts the vendor's own servers rather than Unipile,
    # which also trips their tracking redirects. On by default for parity with
    # the CLI, because it is how several vendors' PDFs are reachable at all.
    follow_links: bool = True


class ScanErrorOut(BaseModel):
    mailbox: str
    subject: str
    detail: str


class ScanJob(BaseModel):
    id: str
    status: Literal["running", "done", "error"]
    mailboxes: list[str] = []
    messages_scanned: int = 0
    invoices_found: int = 0
    invoices_new: int = 0
    errors: list[ScanErrorOut] = []
    # Set only when status is "error": the scan itself failed, as opposed to
    # individual documents failing, which are reported in `errors`.
    detail: str | None = None
    # What the scan is on right now, as "<mailbox>: <subject>". Empty before
    # the first message and once the scan is over; a poller shows it while
    # `status` is "running" and has the counts to show after that.
    progress: str = ""


class InvoicePage(BaseModel):
    """One page of stored invoices.

    Each item is the payload as filed — `invoice`, `email`, `source`,
    `document`, `extraction` — plus `id` and `issued_on`. Passed through
    untyped on purpose: the parser learns new fields as templates are added,
    and the dashboard reads only the few it renders.
    """

    items: list[dict[str, Any]]
    total: int


class ShareCreate(BaseModel):
    """What the Share button sends. Every field is optional on purpose.

    The click is the share: there is no dialog in between, so nothing here is
    ever asked of the user at the moment they click.
    """

    # Omitted snapshots every invoice — the table's own behaviour, which shares
    # the checked rows if any are checked and the whole view otherwise.
    invoice_ids: list[str] | None = Field(default=None, min_length=1)
    # A correction the browser is holding from a previous share, sent again so
    # the fix is made once rather than once per link.
    owner_name: str | None = Field(default=None, min_length=1, max_length=NAME_LENGTH)
    # Which mailbox this goes out as, when more than one is connected. Without
    # it, the first.
    account_id: str | None = None


class ShareCreated(BaseModel):
    """The new link, and the one time its owner key is ever returned."""

    token: str
    url: str
    owner_key: str
    owner_name: str
    expires_at: datetime


class ShareItem(BaseModel):
    """One line of the manifest — what a recipient may see of an invoice.

    A projection rather than the stored payload: the share page is public, and
    the payload carries the owner's mailbox and the message the invoice
    arrived in. Amounts are strings because that is how the parser filed them,
    and every field is optional because half of them are empty on a real
    batch — a ride receipt has no invoice number and no VAT split.
    """

    id: str
    vendor: str | None
    invoice_number: str | None
    # The name this document has inside the zip, so the manifest is a list of
    # what lands in the recipient's folder rather than a second table.
    file: str | None
    issued_on: str | None
    currency: str | None
    amount_net: str | None
    amount_vat: str | None
    amount_total: str | None


class ShareManifest(BaseModel):
    """Everything the share page renders, derived from the snapshot at read time."""

    token: str
    owner_name: str
    owner_email: str
    created_at: datetime
    expires_at: datetime
    filename: str
    # "Apr 1 - Jun 30, 2026", or empty when nothing in the batch carries a date.
    period: str
    invoices: int
    documents: int
    bytes: int
    items: list[ShareItem]


class ShareRename(BaseModel):
    """The one column of a live share that can change."""

    owner_name: str = Field(min_length=1, max_length=NAME_LENGTH)
    owner_key: str


class ShareEmail(BaseModel):
    to: str = Field(pattern=EMAIL_PATTERN)
    from_account_id: str
    owner_key: str
