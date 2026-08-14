"""Pydantic request/response models for the API."""

from typing import Any, Literal

from pydantic import BaseModel


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
    limit: int = 20
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


class InvoicePage(BaseModel):
    """One page of stored invoices.

    Each item is the payload as filed — `invoice`, `email`, `source`,
    `document`, `extraction` — plus `id` and `issued_on`. Passed through
    untyped on purpose: the parser learns new fields as templates are added,
    and the dashboard reads only the few it renders.
    """

    items: list[dict[str, Any]]
    total: int
