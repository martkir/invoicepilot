"""FastAPI service — what the dashboard talks to.

Run with: uvicorn backend.services.api:api --reload

Every route is a plain `def`, not `async def`, on purpose: everything below is
blocking (urllib to Unipile, invoice2data, psycopg), so FastAPI runs these in a
threadpool. Declaring them async would put that work on the event loop and
stall the whole service for the length of a scan.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from backend import __version__, accounts, invoices, scan_jobs
from backend.core.db import session_scope
from backend.core.logging import setup_logging
from backend.invoice_store import document_path
from backend.schemas import (
    Account,
    ConnectLink,
    HealthResponse,
    InvoicePage,
    ScanJob,
    ScanRequest,
)
from backend.unipile import UnipileError, credentials

setup_logging()

api = FastAPI(title="Invoice Pilot API", version=__version__)


@api.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@api.get("/accounts", response_model=list[Account])
def list_accounts() -> list[Account]:
    """Mailboxes Unipile currently holds credentials for."""
    try:
        base, api_key = credentials()
        return [Account(**accounts.describe(a)) for a in accounts.list_connected(base, api_key)]
    except UnipileError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@api.post("/accounts/connect", response_model=ConnectLink)
def connect_account() -> ConnectLink:
    """A hosted auth URL for connecting a mailbox.

    The caller opens it, the user approves, and the account appears on the
    tenant — which the caller observes by polling /accounts, because Unipile's
    webhook needs a publicly reachable URL that a local run does not have.
    """
    try:
        base, api_key = credentials()
        return ConnectLink(url=accounts.connect_link(base, api_key))
    except UnipileError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@api.delete("/accounts/{account_id}", status_code=204)
def disconnect_account(account_id: str) -> None:
    """Disconnect a mailbox. Invoices already extracted from it are kept."""
    try:
        base, api_key = credentials()
        accounts.disconnect(base, api_key, account_id)
    except UnipileError as exc:
        # Unipile 404s an unknown id; surface that as a 404 rather than a 502,
        # which is what the client needs to tell "gone already" from "broken".
        status = 404 if "HTTP 404" in str(exc) else 502
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@api.post("/scan", response_model=ScanJob, status_code=202)
def start_scan(request: ScanRequest | None = None) -> ScanJob:
    """Start scanning every connected mailbox. Returns immediately with a job id."""
    options = request or ScanRequest()
    if options.limit < 1:
        raise HTTPException(status_code=422, detail="limit must be at least 1")
    return _as_job(scan_jobs.start(limit=options.limit, follow_links=options.follow_links))


@api.get("/scan/{job_id}", response_model=ScanJob)
def scan_status(job_id: str) -> ScanJob:
    job = scan_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No such scan.")
    return _as_job(job)


@api.get("/invoices", response_model=InvoicePage)
def list_invoices(limit: int = invoices.DEFAULT_PAGE, offset: int = 0) -> InvoicePage:
    """One page of stored invoices, newest first."""
    with session_scope() as session:
        return InvoicePage(
            items=invoices.recent(session, limit=limit, offset=offset),
            total=invoices.count(session),
        )


@api.get("/invoices/{invoice_id}/document")
def invoice_document(invoice_id: str) -> FileResponse:
    """The vendor's own file for one invoice.

    Served inline so a browser can render the PDF in place. Not every invoice
    has one — a receipt that only ever existed as an email body has nothing to
    return, which is a 404 the client is expected to handle rather than an
    error worth logging.
    """
    with session_scope() as session:
        payload = invoices.get(session, invoice_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="No such invoice.")

    path = document_path(payload)
    if path is None:
        raise HTTPException(status_code=404, detail="This invoice has no document.")

    return FileResponse(
        path,
        media_type="application/pdf" if path.suffix == ".pdf" else None,
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


def _as_job(job: scan_jobs.Job) -> ScanJob:
    result = job.result
    return ScanJob(
        id=job.id,
        status=job.status,
        detail=job.detail,
        mailboxes=list(result.mailboxes) if result else [],
        messages_scanned=result.messages_scanned if result else 0,
        invoices_found=result.invoices_found if result else 0,
        invoices_new=result.invoices_new if result else 0,
        errors=[
            {"mailbox": e.mailbox, "subject": e.subject, "detail": e.detail}
            for e in (result.errors if result else ())
        ],
    )
