"""Connected mailboxes.

Unipile holds the credentials and the sync status, so it is the source of truth
for which mailboxes exist. Nothing here is mirrored into Postgres — a copy
would only give the two a way to disagree.

Connecting a mailbox is a hosted flow: Unipile returns a wizard URL, the user
approves in a browser, and the account appears on the tenant. Unipile can
announce that with a webhook, but only to a publicly reachable URL, so locally
the caller polls list_connected() until it shows up.
"""

from backend.core.logging import get_logger
from backend.unipile import (
    account_status,
    create_hosted_auth_link,
    delete_account,
    expires_on,
    list_accounts,
)

log = get_logger(__name__)

# Long enough to sign in unhurried, short enough that a stale link is useless.
LINK_TTL_MINUTES = 15


def list_connected(base: str, api_key: str) -> list[dict]:
    """Usable mailboxes, one entry per address, newest first.

    Two kinds of account are dropped here.

    An account whose status is not OK has lapsed credentials and cannot be
    read, so it is treated as though it were never connected — there is no
    separate "reconnect" state in the product, you simply add the source again.
    It is left in place on Unipile rather than deleted, because a status can
    recover and deleting would discard a working connection over a blip.

    And reconnecting leaves the previous account behind rather than replacing
    it, so the tenant really does list one address twice. The newest wins: it
    holds the freshest credentials, and scanning both would parse the same
    inbox twice and double every count.
    """
    newest: dict[str, dict] = {}
    for account in sorted(
        list_accounts(base, api_key),
        key=lambda a: a.get("created_at") or "",
        reverse=True,
    ):
        status = account_status(account)
        if status != "OK":
            log.info("hiding %s — status %s", account.get("name") or account["id"], status)
            continue
        newest.setdefault((account.get("name") or account["id"]).strip().lower(), account)
    return list(newest.values())


def describe(account: dict) -> dict:
    """The parts of an account worth showing: who it is and whether it works."""
    return {
        "id": account["id"],
        "email": account.get("name") or account["id"],
        "status": account_status(account),
    }


def disconnect(base: str, api_key: str, account_id: str) -> None:
    """Disconnect the mailbox an account belongs to.

    Every account for that address goes, not just the one named. Reconnecting
    leaves the previous account behind rather than replacing it, so one address
    routinely has several; the dashboard collapses them into a single row, and
    deleting only the newest would leave a hidden duplicate to take its place —
    the row would reappear and nothing would look disconnected.

    Invoices already extracted are deliberately left alone: they record what was
    spent, and that does not stop being true because the mailbox was unlinked.
    """
    accounts = list_accounts(base, api_key)
    named = next((a for a in accounts if a["id"] == account_id), None)
    if named is None:
        # Let Unipile produce the 404, so an unknown id reports consistently.
        delete_account(base, api_key, account_id)
        return

    address = (named.get("name") or "").strip().lower()
    targets = [
        a["id"] for a in accounts if address and (a.get("name") or "").strip().lower() == address
    ] or [account_id]

    for target in targets:
        delete_account(base, api_key, target)
    log.info("disconnected %s (%d account(s))", address or account_id, len(targets))


def connect_link(base: str, api_key: str, *, providers: tuple[str, ...] = ("GOOGLE",)) -> str:
    """A hosted auth wizard URL for connecting a new mailbox."""
    return create_hosted_auth_link(
        base,
        api_key,
        {
            "type": "create",
            "providers": list(providers),
            "api_url": base,
            "expiresOn": expires_on(LINK_TTL_MINUTES),
        },
    )
