"""Connected mailboxes.

Unipile holds the credentials and the sync status, so it is the source of truth
for which mailboxes exist. Nothing here is mirrored into Postgres — a copy
would only give the two a way to disagree.

Connecting a mailbox is a hosted flow: Unipile returns a wizard URL, the user
approves in a browser, and the account appears on the tenant. Unipile announces
that with a webhook, which is also what attributes the new account to the
workspace that asked for it — see invoicepilot/workspaces.py.

There is one Unipile tenant and one API key for the whole deployment, so every
visitor's mailbox lands in the same list and Unipile cannot say which is whose.
That is why each function here takes `allowed`: the account ids the calling
workspace owns, from workspaces.account_ids(). Anything outside that list is
somebody else's mailbox and is treated as though it did not exist. The list is
passed in rather than looked up here, so this module still needs no database.
"""

from invoicepilot.core.logging import get_logger
from invoicepilot.unipile import (
    UnipileError,
    account_status,
    create_hosted_auth_link,
    delete_account,
    expires_on,
    list_accounts,
)

log = get_logger(__name__)

# Long enough to sign in unhurried, short enough that a stale link is useless.
LINK_TTL_MINUTES = 15


def list_connected(base: str, api_key: str, allowed: list[str]) -> list[dict]:
    """Usable mailboxes this workspace owns, one entry per address, newest first.

    Three kinds of account are dropped here.

    An account the caller's workspace does not own goes first, before anything
    else is considered. The tenant is shared by every visitor, so this filter is
    the whole boundary between one person's mailboxes and another's.

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
    owned = set(allowed)
    if not owned:
        return []

    newest: dict[str, dict] = {}
    for account in sorted(
        (a for a in list_accounts(base, api_key) if a["id"] in owned),
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


def owner(
    base: str, api_key: str, allowed: list[str], account_id: str | None = None
) -> tuple[str, str] | None:
    """(name, address) of a mailbox: who a share is made as, and sent as.

    `account_id` arrives from a browser on both routes that use this, so it is
    checked against the workspace's own mailboxes rather than trusted — None
    back means it is not one of this user's. Without an id the first connected
    mailbox answers, which is what the dashboard's Share button sends.

    Checking against `allowed` and not merely against the tenant is the point:
    on a shared tenant an unfiltered check would accept any account id in the
    deployment, and this gates both minting a share as a mailbox and sending
    mail as one.

    Raises UnipileError when no mailbox is connected at all: a share names the
    person who made it, and there is nobody to name.
    """
    connected = list_connected(base, api_key, allowed)
    if not connected:
        raise UnipileError("No mailboxes are connected — connect one before sharing.")

    if account_id is None:
        account = connected[0]
    else:
        account = next((a for a in connected if a["id"] == account_id), None)
        if account is None:
            return None

    address = describe(account)["email"]
    # Unipile records a mail account's own address in `name`, so in practice
    # the fallback is what runs: the local part, verbatim. A tenant that does
    # carry a display name is used as it stands.
    label = (account.get("name") or "").strip()
    return (label if label and "@" not in label else address.split("@")[0], address)


def disconnect(base: str, api_key: str, allowed: list[str], account_id: str) -> list[str]:
    """Disconnect the mailbox an account belongs to. Returns the ids deleted.

    Every account for that address goes, not just the one named. Reconnecting
    leaves the previous account behind rather than replacing it, so one address
    routinely has several; the dashboard collapses them into a single row, and
    deleting only the newest would leave a hidden duplicate to take its place —
    the row would reappear and nothing would look disconnected.

    That sweep is intersected with `allowed`, and it is the reason this function
    returns a list. Matching on the address alone was correct while one person
    owned the tenant; on a shared one it reaches across workspaces, so a visitor
    disconnecting their own Gmail would delete the live connection of everyone
    else who had connected the same address. The ids come back so the caller can
    drop the matching ownership rows.

    Invoices already extracted are deliberately left alone: they record what was
    spent, and that does not stop being true because the mailbox was unlinked.
    """
    owned = set(allowed)
    if account_id not in owned:
        # Not ours to delete, and not ours to confirm the existence of either.
        # The route turns this into the same 404 an unknown id gets.
        raise UnipileError(f"HTTP 404: no such account {account_id}")

    accounts = [a for a in list_accounts(base, api_key) if a["id"] in owned]
    named = next((a for a in accounts if a["id"] == account_id), None)
    if named is None:
        # Owned by this workspace but gone from the tenant. Let Unipile produce
        # the 404, so an unknown id reports consistently.
        delete_account(base, api_key, account_id)
        return [account_id]

    address = (named.get("name") or "").strip().lower()
    targets = [
        a["id"] for a in accounts if address and (a.get("name") or "").strip().lower() == address
    ] or [account_id]

    for target in targets:
        delete_account(base, api_key, target)
    log.info("disconnected %s (%d account(s))", address or account_id, len(targets))
    return targets


def connect_link(
    base: str,
    api_key: str,
    *,
    notify_url: str | None = None,
    providers: tuple[str, ...] = ("GOOGLE",),
) -> str:
    """A hosted auth wizard URL for connecting a new mailbox.

    `notify_url` is what makes the finished account attributable: the wizard
    runs in the user's browser and the account surfaces on a tenant shared by
    everyone, so the callback carrying our nonce is the only thing that says
    who asked for it. It is optional because a local run has no publicly
    reachable URL for Unipile to reach — and without it the account arrives
    unclaimed and stays invisible, which is the intended failure.

    The nonce travels as a path segment rather than a query parameter: both are
    accepted when the link is created, but a path segment is the harder of the
    two for an intermediary to drop.
    """
    payload = {
        "type": "create",
        "providers": list(providers),
        "api_url": base,
        "expiresOn": expires_on(LINK_TTL_MINUTES),
    }
    if notify_url:
        payload["notify_url"] = notify_url
    return create_hosted_auth_link(base, api_key, payload)
