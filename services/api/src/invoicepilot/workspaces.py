"""Whose invoices, whose mailboxes.

The dashboard is served on a public URL and has no login, so "who is asking"
has to come from somewhere. It comes from a cookie: an unguessable id minted on
the first request that needs one, held httpOnly by the browser, and used to
scope every read and write in the product. Same browser, same workspace. A
different browser is a different person as far as this module is concerned,
even when it is the same human — there is no account to tie the two together
and deliberately no way to recover one from the other.

That makes the cookie the whole credential, which is why it is sized like one
and why nothing here ever accepts an id the client made up: an unknown cookie
is replaced rather than adopted, so the id space stays server-generated.

No FastAPI here. Like invoicepilot/unipile.py, this stays framework-free and
invoicepilot/app.py does the `Depends` wrapping — the routes are the only layer
that knows what a request is.
"""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from invoicepilot.accounts import LINK_TTL_MINUTES
from invoicepilot.core.logging import get_logger
from invoicepilot.models import Invoice, PendingConnect, Workspace, WorkspaceAccount

log = get_logger(__name__)

# The cookie the whole scheme rests on. httpOnly so script on the page cannot
# read it, and Lax rather than Strict so a share link followed from a mail
# client still arrives with the recipient's own workspace attached.
COOKIE = "ip_ws"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60

# 32 bytes, like the share owner key. Possession is the entire authorisation,
# so the only defence is that it cannot be arrived at by guessing.
ID_BYTES = 32

# A wizard the user never finished. Matched to the link's own expiry, since a
# nonce cannot be redeemed after the link it travelled with has lapsed.
CONNECT_TTL = timedelta(minutes=LINK_TTL_MINUTES)


def ensure(session: Session, workspace_id: str | None) -> tuple[str, bool]:
    """The caller's workspace, creating one if they do not have a usable id.

    Returns (id, minted). `minted` is True when the caller needs the cookie set
    — either they arrived without one, or with one no row answers to.

    An unrecognised id is replaced rather than trusted into existence. Adopting
    it would let a client pick its own workspace id, and an id a client can
    choose is an id a client can choose to make short.
    """
    if workspace_id and session.get(Workspace, workspace_id) is not None:
        return workspace_id, False

    workspace = Workspace(id=secrets.token_urlsafe(ID_BYTES))
    session.add(workspace)
    session.flush()
    log.info("new workspace %s", workspace.id[:8])
    return workspace.id, True


def exists(session: Session, workspace_id: str) -> bool:
    """Whether a workspace id names anything. For the CLI, which is given one."""
    return session.get(Workspace, workspace_id) is not None


def summarise(session: Session) -> list[dict]:
    """Every workspace with its size, newest first — what `invoicepilot workspaces` prints.

    The only way to find a workspace id from outside the browser that owns it,
    which is what makes an operator able to scan into one or to find where the
    migration put the invoices that predate all this.
    """
    accounts = (
        select(WorkspaceAccount.workspace_id, func.count().label("n"))
        .group_by(WorkspaceAccount.workspace_id)
        .subquery()
    )
    counted = (
        select(Invoice.workspace_id, func.count().label("n"))
        .group_by(Invoice.workspace_id)
        .subquery()
    )
    rows = session.execute(
        select(
            Workspace.id,
            Workspace.created_at,
            func.coalesce(accounts.c.n, 0),
            func.coalesce(counted.c.n, 0),
        )
        .outerjoin(accounts, accounts.c.workspace_id == Workspace.id)
        .outerjoin(counted, counted.c.workspace_id == Workspace.id)
        .order_by(Workspace.created_at.desc())
    ).all()
    return [
        {"id": row[0], "created_at": row[1], "accounts": row[2], "invoices": row[3]} for row in rows
    ]


def account_ids(session: Session, workspace_id: str) -> list[str]:
    """The Unipile accounts this workspace owns.

    The allowlist every mailbox operation is filtered through. Empty is the
    normal state for a browser that has just arrived, and means the tenant's
    other accounts are invisible rather than that there are none.
    """
    return list(
        session.scalars(
            select(WorkspaceAccount.account_id).where(WorkspaceAccount.workspace_id == workspace_id)
        )
    )


def start_connect(session: Session, workspace_id: str) -> str:
    """Open a hosted-auth flow and return the nonce that identifies it.

    The nonce goes out in the `notify_url` Unipile is told to call back on, and
    coming back is the only thing that ties the finished account to this
    workspace — the wizard runs in the user's browser and the account surfaces
    on a tenant shared by everyone.
    """
    pending = PendingConnect(nonce=secrets.token_urlsafe(ID_BYTES), workspace_id=workspace_id)
    session.add(pending)
    session.flush()
    return pending.nonce


def claim(session: Session, nonce: str, account_id: str) -> str | None:
    """File a freshly connected account against the workspace that asked for it.

    Returns the workspace id, or None when the nonce is unknown, already spent
    or too old — all of which are refusals rather than errors, because the only
    caller is a public webhook and it is told nothing either way.

    Single use: the row is deleted as it is redeemed, so a replayed webhook
    cannot attach a second account to a workspace that never asked for one.
    """
    pending = session.get(PendingConnect, nonce)
    if pending is None:
        return None

    session.delete(pending)
    if datetime.now(UTC) - pending.created_at > CONNECT_TTL:
        log.info("nonce for %s expired unredeemed", pending.workspace_id[:8])
        return None

    session.merge(WorkspaceAccount(workspace_id=pending.workspace_id, account_id=account_id))
    log.info("account %s claimed by %s", account_id, pending.workspace_id[:8])
    return pending.workspace_id


def forget_account(session: Session, workspace_id: str, account_ids: list[str]) -> None:
    """Drop the ownership rows for accounts this workspace just disconnected."""
    if not account_ids:
        return
    session.execute(
        delete(WorkspaceAccount).where(
            WorkspaceAccount.workspace_id == workspace_id,
            WorkspaceAccount.account_id.in_(account_ids),
        )
    )


def sweep_pending(session: Session) -> int:
    """Delete nonces for wizards nobody finished. Returns how many went."""
    result = session.execute(
        delete(PendingConnect).where(PendingConnect.created_at < datetime.now(UTC) - CONNECT_TTL)
    )
    return result.rowcount or 0
