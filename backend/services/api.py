"""FastAPI service — what the dashboard talks to.

Run with: uvicorn backend.services.api:api --reload

Every route is a plain `def`, not `async def`, on purpose: everything below is
blocking (urllib to Unipile, invoice2data, psycopg), so FastAPI runs these in a
threadpool. Declaring them async would put that work on the event loop and
stall the whole service for the length of a scan.
"""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from backend import __version__, accounts, invoices, scan_jobs, share_mail, share_zip, shares
from backend.core.db import session_scope
from backend.core.logging import setup_logging
from backend.invoice_store import document_path, thumbnail
from backend.models import Share
from backend.schemas import (
    Account,
    ConnectLink,
    HealthResponse,
    InvoicePage,
    ScanJob,
    ScanRequest,
    ShareCreate,
    ShareCreated,
    ShareEmail,
    ShareManifest,
    ShareRename,
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


@api.post(
    "/scan",
    response_model=ScanJob,
    status_code=202,
    # Raised, not returned, so FastAPI cannot infer it — and a client that
    # cannot see it has no reason to handle it.
    responses={409: {"description": "A scan is already running."}},
)
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


@api.post("/shares", response_model=ShareCreated, status_code=201)
def create_share(payload: ShareCreate, creds: CredentialsDep) -> ShareCreated:
    """Mint a link for a batch of invoices. The only place a share is written.

    The owner key comes back here and never again — the browser keeps it, and
    it is what separates the person who made the link from anyone holding it.
    """
    mailbox = accounts.owner(*creds, payload.account_id)
    if mailbox is None:
        raise HTTPException(status_code=403, detail="Not one of your connected mailboxes.")
    name, address = mailbox

    with session_scope() as session:
        ids = payload.invoice_ids
        if ids is None:
            ids = invoices.all_ids(session)
        share, owner_key = shares.mint(
            session,
            invoice_ids=ids,
            owner=((payload.owner_name or name).strip(), address),
        )
        summary = shares.snapshot(session, share).summary
        return ShareCreated(
            token=share.token,
            url=shares.url(share.token),
            owner_key=owner_key,
            owner_name=share.owner_name,
            expires_at=share.expires_at,
            invoices=summary.invoices,
            period=summary.period,
        )


@api.get(
    "/s/{token}",
    response_model=ShareManifest,
    responses={410: {"description": "The link has expired."}},
)
def share_manifest(token: str) -> ShareManifest:
    """Everything the share page shows: who shared it, and what is in the zip."""
    with session_scope() as session:
        snapshot = shares.snapshot(session, _live_share(session, token))
        share, summary = snapshot.share, snapshot.summary
        return ShareManifest(
            token=share.token,
            owner_name=share.owner_name,
            owner_email=share.owner_email,
            created_at=share.created_at,
            expires_at=share.expires_at,
            filename=summary.filename,
            period=summary.period,
            invoices=summary.invoices,
            documents=summary.documents,
            bytes=summary.bytes,
            subject=share_mail.subject(summary),
            items=shares.manifest(snapshot.items, snapshot.entries),
        )


@api.patch("/s/{token}", status_code=204)
def rename_share(token: str, payload: ShareRename) -> None:
    """Correct the name the recipient is greeted by. The one UPDATE in the feature.

    Gated by the owner key, so a recipient holding the same link cannot rewrite
    who it says shared with them. The address is not editable: it is the
    mailbox that will actually send.
    """
    with session_scope() as session:
        share = _live_share(session, token)
        _owned(share, payload.owner_key)
        share.owner_name = payload.owner_name.strip()


@api.get("/s/{token}/thumb/{invoice_id}")
def share_thumbnail(token: str, invoice_id: str) -> FileResponse:
    """One invoice's first page, as a small WebP.

    The id has to be in this share's own snapshot: a token grants exactly the
    invoices it was made for, so an id guessed out of somebody else's share is
    a 404 rather than a picture.
    """
    with session_scope() as session:
        share = _live_share(session, token)
        if invoice_id not in share.invoice_ids:
            raise HTTPException(status_code=404, detail="No such invoice in this share.")
        payload = invoices.get(session, invoice_id)

    image = thumbnail(payload) if payload else None
    if image is None:
        raise HTTPException(status_code=404, detail="This invoice has no document.")
    return FileResponse(image, media_type="image/webp")


@api.get("/s/{token}/zip")
def download_share(token: str) -> StreamingResponse:
    """The whole batch: every document, plus invoices.csv.

    No parameters — the link is the batch, and there is nothing to choose.
    """
    with session_scope() as session:
        snapshot = shares.snapshot(session, _live_share(session, token))

    return StreamingResponse(
        share_zip.stream(snapshot),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{snapshot.summary.filename}"'},
    )


@api.get("/s/{token}/email/preview", response_class=HTMLResponse)
def preview_share_email(token: str) -> HTMLResponse:
    """The mail this share would send, as the document the composer's iframe loads.

    Ungated: it shows the recipient's own manifest and the name already on the
    share page. What it buys is that the preview is the bytes the send uses,
    rather than a look-alike that can drift from them.
    """
    with session_scope() as session:
        snapshot = shares.snapshot(session, _live_share(session, token))
    return HTMLResponse(share_mail.draft(snapshot, shares.url(token)).html)


@api.post("/s/{token}/email", status_code=204)
def send_share_email(token: str, payload: ShareEmail, creds: CredentialsDep) -> None:
    """Send the link as the chosen mailbox. Nothing records that this happened.

    Two things are checked before Unipile is called: the owner key, and that
    the mailbox is really one of this user's. Both arrive from the browser, and
    the only thing that may send as a mailbox is that mailbox's owner.
    """
    with session_scope() as session:
        share = _live_share(session, token)
        _owned(share, payload.owner_key)
        snapshot = shares.snapshot(session, share)

    if accounts.owner(*creds, payload.from_account_id) is None:
        raise HTTPException(status_code=403, detail="Not one of your connected mailboxes.")

    share_mail.send(
        *creds,
        payload.from_account_id,
        to=payload.to,
        mail=share_mail.draft(snapshot, shares.url(token)),
    )


def _live_share(session: Session, token: str) -> Share:
    """The share a token names, or the difference between the two dead ends.

    404 means no such link ever existed — check what you pasted. 410 means this
    link worked and has stopped, which is why the body still names who shared
    it and when it lapsed: the expired page can then say both.
    """
    share = shares.get(session, token)
    if share is None:
        raise HTTPException(status_code=404, detail="No such share.")
    if shares.expired(share):
        raise HTTPException(
            status_code=410,
            detail={
                "message": "This link has expired.",
                "owner_name": share.owner_name,
                "owner_email": share.owner_email,
                "created_at": share.created_at.isoformat(),
                "expires_at": share.expires_at.isoformat(),
            },
        )
    return share


def _owned(share: Share, owner_key: str) -> None:
    """Refuse anything but the browser that made this link."""
    if not shares.authorized(share, owner_key):
        raise HTTPException(status_code=403, detail="This link is not yours to change.")


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
