"""FastAPI service — what the dashboard talks to.

Run with: uvicorn invoicepilot.app:api --reload

Every route is a plain `def`, not `async def`, on purpose: everything below is
blocking (urllib to Unipile, invoice2data, psycopg), so FastAPI runs these in a
threadpool. Declaring them async would put that work on the event loop and
stall the whole service for the length of a scan.
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from invoicepilot import (
    __version__,
    accounts,
    invoices,
    scan_jobs,
    share_mail,
    share_zip,
    shares,
    workspaces,
)
from invoicepilot.core.config import get_settings
from invoicepilot.core.db import session_scope
from invoicepilot.core.logging import get_logger, setup_logging
from invoicepilot.invoice_store import document_path, thumbnail, workspace_root
from invoicepilot.models import Share
from invoicepilot.schemas import (
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
from invoicepilot.unipile import UnipileError, credentials

setup_logging()

log = get_logger(__name__)

api = FastAPI(title="Invoice Pilot API", version=__version__)

# Unipile's base URL and key, resolved per request. A dependency rather than a
# call in each handler so that missing configuration and an unreachable tenant
# report the same way everywhere — see the UnipileError handler below.
CredentialsDep = Annotated[tuple[str, str], Depends(credentials)]


def workspace(request: Request, response: Response) -> str:
    """Who is asking, as an id — the scope every route below reads and writes in.

    There is no login. The dashboard is served on a public URL, so identity is
    a cookie this sets the first time a browser arrives without a usable one.
    Same browser, same workspace; a different browser is a different person and
    starts empty, which is the whole point of the thing.

    Note what this does *not* gate: it refuses nobody. Anyone may have a
    workspace, and what they get is their own. The scoping is the security
    boundary, not an admission check.
    """
    with session_scope() as session:
        workspace_id, minted = workspaces.ensure(session, request.cookies.get(workspaces.COOKIE))

    if minted:
        response.set_cookie(
            workspaces.COOKIE,
            workspace_id,
            max_age=workspaces.COOKIE_MAX_AGE,
            httponly=True,
            # Off for a plain-HTTP origin, or the dev server could never keep
            # the cookie at all: browsers drop a Secure cookie sent over http.
            # Derived from the public origin rather than a setting of its own,
            # so there is no second switch to forget in production.
            secure=get_settings().public_base_url.startswith("https://"),
            # Lax, not Strict: a share link followed out of a mail client is a
            # cross-site navigation, and under Strict the recipient would
            # arrive without their own cookie and be minted a new workspace on
            # every visit.
            samesite="lax",
            path="/",
        )
    return workspace_id


WorkspaceDep = Annotated[str, Depends(workspace)]


def owned_accounts(ws: WorkspaceDep) -> list[str]:
    """The Unipile account ids this workspace may act on.

    One tenant serves every visitor, so this list is what separates "my
    mailboxes" from "the deployment's mailboxes". Passed into accounts.* rather
    than looked up there, which is what keeps that module free of the database.

    A dependency rather than a call inside each handler, for the same reason
    `credentials` is one: it reaches a backend, so it is the seam a test needs
    to override.
    """
    with session_scope() as session:
        return workspaces.account_ids(session, ws)


AllowedDep = Annotated[list[str], Depends(owned_accounts)]


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
def list_accounts(creds: CredentialsDep, allowed: AllowedDep) -> list[Account]:
    """Mailboxes this workspace has connected.

    Not every mailbox on the tenant — that list is everyone's, and answering it
    here is what the workspace scoping exists to prevent.
    """
    connected = accounts.list_connected(*creds, allowed)
    return [Account(**accounts.describe(a)) for a in connected]


@api.post("/accounts/connect", response_model=ConnectLink)
def connect_account(creds: CredentialsDep, ws: WorkspaceDep) -> ConnectLink:
    """A hosted auth URL for connecting a mailbox to this workspace.

    The caller opens it, the user approves, and the account appears on the
    tenant — which the caller observes by polling /accounts.

    The nonce in the callback URL is what makes the finished account
    attributable. The wizard runs in the user's own browser and the account
    surfaces on a tenant shared by every visitor, so without the callback there
    is nothing to say whose it is. If it never arrives the account stays
    unclaimed and invisible rather than being guessed at.
    """
    with session_scope() as session:
        nonce = workspaces.start_connect(session, ws)

    origin = get_settings().public_base_url.rstrip("/")
    return ConnectLink(
        url=accounts.connect_link(*creds, notify_url=f"{origin}/api/unipile/connected/{nonce}")
    )


@api.post("/unipile/connected/{nonce}", status_code=204)
def account_connected(nonce: str, payload: dict[str, Any] | None = None) -> None:
    """Unipile's callback: file a freshly connected account against a workspace.

    Public and unauthenticated, because Unipile is the caller and carries no
    credential of ours. The nonce is the check — it was minted for one connect
    flow, is single-use, and expires with the link it travelled in.

    Answers 204 whether or not the nonce meant anything. A webhook that reports
    failure gets retried, and there is nothing to retry: an unknown nonce is a
    flow that expired or a replay, and neither improves on a second attempt.

    The body is logged because its exact shape is Unipile's to change and this
    is the only place it is ever seen — the first real connect after a deploy
    is the only chance to find out it moved.
    """
    body = payload or {}
    account_id = body.get("account_id") or body.get("accountId") or body.get("id")
    if not account_id:
        log.warning("connect callback carried no account id: %s", body)
        return

    with session_scope() as session:
        claimed = workspaces.claim(session, nonce, str(account_id))
    if claimed is None:
        log.info("connect callback for an unknown or spent nonce")


@api.delete("/accounts/{account_id}", status_code=204)
def disconnect_account(
    account_id: str, creds: CredentialsDep, ws: WorkspaceDep, allowed: AllowedDep
) -> None:
    """Disconnect a mailbox. Invoices already extracted from it are kept.

    An account this workspace does not own reports 404 rather than 403: whether
    some other visitor has connected a given mailbox is not this caller's to
    find out.
    """
    try:
        removed = accounts.disconnect(*creds, allowed, account_id)
    except UnipileError as exc:
        # Unipile 404s an unknown id. Only this route can read that as "gone
        # already" rather than "broken" — everywhere else a 404 from Unipile
        # means our own request was wrong, which is the handler's 502.
        if "HTTP 404" not in str(exc):
            raise
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    with session_scope() as session:
        workspaces.forget_account(session, ws, removed)


@api.post(
    "/scan",
    response_model=ScanJob,
    status_code=202,
    # Raised, not returned, so FastAPI cannot infer it — and a client that
    # cannot see it has no reason to handle it.
    responses={409: {"description": "A scan is already running."}},
)
def start_scan(
    ws: WorkspaceDep, allowed: AllowedDep, request: ScanRequest | None = None
) -> ScanJob:
    """Start scanning this workspace's mailboxes. Returns immediately with a job id."""
    options = request or ScanRequest()
    try:
        return _as_job(scan_jobs.start(ws, allowed, follow_links=options.follow_links))
    except scan_jobs.ScanInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@api.get("/scan/{job_id}", response_model=ScanJob)
def scan_status(job_id: str, ws: WorkspaceDep) -> ScanJob:
    job = scan_jobs.get(job_id, ws)
    if job is None:
        raise HTTPException(status_code=404, detail="No such scan.")
    return _as_job(job)


@api.get("/invoices", response_model=InvoicePage)
def list_invoices(
    ws: WorkspaceDep,
    limit: Annotated[int, Query(ge=1, le=invoices.MAX_PAGE)] = invoices.DEFAULT_PAGE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InvoicePage:
    """One page of this workspace's invoices, newest first."""
    with session_scope() as session:
        return InvoicePage(
            items=invoices.recent(session, ws, limit=limit, offset=offset),
            total=invoices.count(session, ws),
        )


@api.get("/invoices/{invoice_id}/document")
def invoice_document(invoice_id: str, ws: WorkspaceDep) -> FileResponse:
    """The vendor's own file for one invoice.

    Served inline so a browser can render the PDF in place. Not every invoice
    has one — a receipt that only ever existed as an email body has nothing to
    return, which is a 404 the client is expected to handle rather than an
    error worth logging.

    Another workspace's invoice id is the same 404 as one that does not exist.
    The lookup is scoped, so there is no branch here that could tell them apart.
    """
    with session_scope() as session:
        payload = invoices.get(session, ws, invoice_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="No such invoice.")

    path = document_path(payload, workspace_root(ws))
    if path is None:
        raise HTTPException(status_code=404, detail="This invoice has no document.")

    return FileResponse(
        path,
        media_type="application/pdf" if path.suffix == ".pdf" else None,
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@api.post("/shares", response_model=ShareCreated, status_code=201)
def create_share(
    payload: ShareCreate, creds: CredentialsDep, ws: WorkspaceDep, allowed: AllowedDep
) -> ShareCreated:
    """Mint a link for a batch of invoices. The only place a share is written.

    The owner key comes back here and never again — the browser keeps it, and
    it is what separates the person who made the link from anyone holding it.

    Two scopes meet here and they are both this caller's: the mailbox it is
    sent as must be one this workspace owns, and the ids it covers are read
    within this workspace. An id belonging to somebody else simply is not found
    and drops out of the snapshot.
    """
    mailbox = accounts.owner(*creds, allowed, payload.account_id)
    if mailbox is None:
        raise HTTPException(status_code=403, detail="Not one of your connected mailboxes.")
    name, address = mailbox

    with session_scope() as session:
        ids = payload.invoice_ids
        if ids is None:
            ids = invoices.all_ids(session, ws)
        share, owner_key = shares.mint(
            session,
            workspace_id=ws,
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
    """Everything the share page shows: who shared it, and what is in the zip.

    No workspace dependency, here or on any other /s/{token} route. The caller
    is a recipient: they hold the link, they have no account, and the cookie
    their browser carries is their own empty workspace or nothing at all. The
    scope comes off the share row instead — see shares.snapshot().
    """
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
        payload = invoices.get(session, share.workspace_id, invoice_id)
        root = workspace_root(share.workspace_id)

    image = thumbnail(payload, root) if payload else None
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

    The mailbox is checked against the *share's* workspace, not the caller's
    cookie. The owner key is what authorises acting as this share, so it is the
    share's own mailboxes that it authorises sending from — which also means an
    owner who has lost their cookie but kept the key can still send.
    """
    with session_scope() as session:
        share = _live_share(session, token)
        _owned(share, payload.owner_key)
        snapshot = shares.snapshot(session, share)
        allowed = workspaces.account_ids(session, share.workspace_id)

    if accounts.owner(*creds, allowed, payload.from_account_id) is None:
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
    # `counts` answers from the running scan's last report or from its finished
    # result, whichever the job has, so there is no running/done branch here.
    counts = job.counts
    return ScanJob(
        id=job.id,
        status=job.status,
        detail=job.detail,
        mailboxes=list(counts.mailboxes),
        messages_scanned=counts.messages_scanned,
        invoices_found=counts.invoices_found,
        invoices_new=counts.invoices_new,
        errors=[
            {"mailbox": e.mailbox, "subject": e.subject, "detail": e.detail} for e in counts.errors
        ],
    )
