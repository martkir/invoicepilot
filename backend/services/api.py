"""FastAPI service — what the dashboard talks to.

Run with: uvicorn backend.services.api:api --reload

Every route is a plain `def`, not `async def`, on purpose: everything below is
blocking (urllib to Unipile, invoice2data, psycopg), so FastAPI runs these in a
threadpool. Declaring them async would put that work on the event loop and
stall the whole service for the length of a scan.
"""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

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

# Unipile's base URL and key, resolved per request. A dependency rather than a
# call in each handler so that missing configuration and an unreachable tenant
# report the same way everywhere — see the UnipileError handler below.
CredentialsDep = Annotated[tuple[str, str], Depends(credentials)]


@api.exception_handler(UnipileError)
def unipile_unavailable(request: Request, exc: UnipileError) -> JSONResponse:
    """Anything Unipile refuses is a bad gateway: we are the caller, not the fault.

    Registered once instead of wrapped around each handler, which also covers
    the credentials dependency — unset config fails the same way a dead tenant
    does, because from the client's side it is the same outage.
    """
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@api.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@api.get("/accounts", response_model=list[Account])
def list_accounts(creds: CredentialsDep) -> list[Account]:
    """Mailboxes Unipile currently holds credentials for."""
    return [Account(**accounts.describe(a)) for a in accounts.list_connected(*creds)]


@api.post("/accounts/connect", response_model=ConnectLink)
def connect_account(creds: CredentialsDep) -> ConnectLink:
    """A hosted auth URL for connecting a mailbox.

    The caller opens it, the user approves, and the account appears on the
    tenant — which the caller observes by polling /accounts, because Unipile's
    webhook needs a publicly reachable URL that a local run does not have.
    """
    return ConnectLink(url=accounts.connect_link(*creds))


@api.delete("/accounts/{account_id}", status_code=204)
def disconnect_account(account_id: str, creds: CredentialsDep) -> None:
    """Disconnect a mailbox. Invoices already extracted from it are kept."""
    try:
        accounts.disconnect(*creds, account_id)
    except UnipileError as exc:
        # Unipile 404s an unknown id. Only this route can read that as "gone
        # already" rather than "broken" — everywhere else a 404 from Unipile
        # means our own request was wrong, which is the handler's 502.
        if "HTTP 404" not in str(exc):
            raise
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api.post("/scan", response_model=ScanJob, status_code=202)
def start_scan(request: ScanRequest | None = None) -> ScanJob:
    """Start scanning every connected mailbox. Returns immediately with a job id."""
    options = request or ScanRequest()
    try:
        return _as_job(scan_jobs.start(limit=options.limit, follow_links=options.follow_links))
    except scan_jobs.ScanInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@api.get("/scan/{job_id}", response_model=ScanJob)
def scan_status(job_id: str) -> ScanJob:
    job = scan_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No such scan.")
    return _as_job(job)


@api.get("/invoices", response_model=InvoicePage)
def list_invoices(
    limit: Annotated[int, Query(ge=1, le=invoices.MAX_PAGE)] = invoices.DEFAULT_PAGE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InvoicePage:
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
        progress=job.progress,
        mailboxes=list(result.mailboxes) if result else [],
        messages_scanned=result.messages_scanned if result else 0,
        invoices_found=result.invoices_found if result else 0,
        invoices_new=result.invoices_new if result else 0,
        errors=[
            {"mailbox": e.mailbox, "subject": e.subject, "detail": e.detail}
            for e in (result.errors if result else ())
        ],
    )
