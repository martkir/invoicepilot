"""Unipile REST client: hosted auth links, accounts, and mail.

Unipile brokers the provider OAuth, so nothing here handles tokens — every
call authenticates with the tenant-wide X-API-KEY, and a connected mailbox is
addressed by its `account_id`.

Endpoints are hung off a per-tenant DSN (`api48.unipile.com:17840`), which is
also what the hosted wizard is told to call back into.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from invoicepilot.core.config import get_settings

API_PREFIX = "/api/v1"
DEFAULT_TIMEOUT = 30
POLL_SECONDS = 3
# Unipile's own ceiling for `limit` on /emails.
MAX_PAGE = 250

# Providers the hosted wizard can offer. X/TWITTER and FACEBOOK_MESSENGER are
# documented as no longer maintained, so they are left out.
PROVIDERS = (
    "GOOGLE",
    "MICROSOFT",
    "IMAP",
    "LINKEDIN",
    "WHATSAPP",
    "INSTAGRAM",
    "TELEGRAM",
)


class UnipileError(RuntimeError):
    """Any failure talking to Unipile — bad config, transport, or HTTP status."""


def api_base(dsn: str) -> str:
    """https origin for the tenant, from a DSN written with or without a scheme."""
    candidate = dsn.strip().rstrip("/")
    if not candidate:
        raise UnipileError("UNIPILE_DSN is empty.")
    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme != "https" or not parsed.hostname:
        raise UnipileError(
            f"UNIPILE_DSN must be a host like 'api8.unipile.com:13845', got {dsn!r}."
        )
    if parsed.path not in ("", "/"):
        raise UnipileError(f"UNIPILE_DSN must be host:port only, without a path — got {dsn!r}.")
    return f"{parsed.scheme}://{parsed.netloc}"


def credentials() -> tuple[str, str]:
    """(base, api_key) from the environment, or a UnipileError naming what is missing."""
    settings = get_settings()
    if not settings.unipile_api_key or not settings.unipile_dsn:
        raise UnipileError(
            "UNIPILE_API_KEY / UNIPILE_DSN are not set. "
            "Add them to the repo-root .env (see .env.example)."
        )
    return api_base(settings.unipile_dsn), settings.unipile_api_key


def request(
    method: str,
    base: str,
    path: str,
    api_key: str,
    *,
    params: dict[str, object] | None = None,
    payload: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """One JSON call, with the API error body surfaced rather than swallowed."""
    url = f"{base}{API_PREFIX}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    http_request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={
            "X-API-KEY": api_key,
            "accept": "application/json",
            **({"content-type": "application/json"} if payload is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(http_request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace").strip()
        raise UnipileError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise UnipileError(f"{method} {url} -> {exc.reason}") from exc


def expires_on(minutes: int) -> str:
    """ISO 8601 expiry, milliseconds and a Z suffix as the API's examples use."""
    stamp = datetime.now(UTC) + timedelta(minutes=minutes)
    return stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def create_hosted_auth_link(base: str, api_key: str, payload: dict) -> str:
    """POST a link request and return the wizard URL."""
    link = request("POST", base, "/hosted/accounts/link", api_key, payload=payload)
    url = link.get("url")
    if not url:
        raise UnipileError(f"No url in the response: {json.dumps(link)}")
    return url


def list_accounts(base: str, api_key: str) -> list[dict]:
    """Every account connected to the tenant."""
    return request("GET", base, "/accounts", api_key).get("items", [])


def delete_account(base: str, api_key: str, account_id: str) -> None:
    """Disconnect a mailbox, discarding the credentials Unipile holds for it.

    Not reversible: reconnecting means going through the hosted wizard again.
    Mail already fetched is unaffected — it lives in our own store, not here.
    """
    request("DELETE", base, f"/accounts/{urllib.parse.quote(account_id)}", api_key)


def account_status(account: dict) -> str:
    """Sync status of an account: OK, CREDENTIALS, ERROR, ..."""
    sources = account.get("sources") or [{}]
    return sources[0].get("status") or "UNKNOWN"


def find_account(accounts: list[dict], email: str) -> dict | None:
    """The account for a mailbox, matched on the name the wizard recorded.

    Connecting the same mailbox twice leaves two accounts behind, so the most
    recently created one wins — it is the one whose credentials are freshest.
    """
    wanted = email.strip().lower()
    matches = [a for a in accounts if (a.get("name") or "").strip().lower() == wanted]
    if not matches:
        return None
    return max(matches, key=lambda a: a.get("created_at") or "")


def wait_for_account(
    base: str,
    api_key: str,
    known_ids: set[str],
    email: str,
    *,
    timeout: int,
    interval: int = POLL_SECONDS,
    on_tick: Callable[[int], None] | None = None,
) -> dict | None:
    """Poll until the wizard produces an account, or the deadline passes.

    Local runs have no notify_url — a webhook needs a publicly reachable
    endpoint — so polling is the only way to observe the connection.
    """
    started = time.monotonic()
    deadline = started + timeout
    accounts: list[dict] = []
    while True:
        try:
            accounts = list_accounts(base, api_key)
        except UnipileError:
            # A blip mid-wait should not discard a connection the user has
            # already approved; keep polling until the deadline.
            accounts = accounts or []
        else:
            fresh = [a for a in accounts if a.get("id") not in known_ids]
            if fresh:
                return fresh[0]

        if time.monotonic() >= deadline:
            # Reconnecting a mailbox that is already linked updates the account
            # in place, so no new id ever appears. Fall back to the name.
            return find_account(accounts, email)
        if on_tick:
            on_tick(int(time.monotonic() - started))
        time.sleep(interval)


def stamp(moment: datetime) -> str:
    """The ISO-8601 UTC form Unipile's `after`/`before` filters require."""
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _emails_page(
    base: str,
    api_key: str,
    account_id: str,
    *,
    limit: int,
    role: str | None,
    after: datetime | None = None,
    before: datetime | None = None,
    search: str | None = None,
    cursor: str | None = None,
) -> dict:
    """One page of the envelope: {"items": [...], "cursor": str | None}.

    `after` and `before` filter on the *message's* date rather than on when
    Unipile ingested it — checked against a live mailbox, because a watermark
    built on ingestion time would be worthless. `after` is inclusive in
    practice despite the documentation calling it exclusive, so the boundary
    message comes back on every scan; the invoice upsert absorbs it.

    `search` is a provider-side full-text query covering subject, body,
    attachment filenames and attachment contents. Terms must be joined with an
    explicit " OR " — a space means AND and a comma means nothing.
    """
    params: dict[str, object] = {"account_id": account_id, "limit": limit}
    if role:
        params["role"] = role
    if after:
        params["after"] = stamp(after)
    if before:
        params["before"] = stamp(before)
    if search:
        params["search"] = search
    if cursor:
        params["cursor"] = cursor
    return request("GET", base, "/emails", api_key, params=params)


def list_emails(
    base: str,
    api_key: str,
    account_id: str,
    *,
    limit: int = 10,
    role: str | None = "inbox",
) -> list[dict]:
    """One page, most recent mail first. `role` filters by folder; None spans all."""
    return _emails_page(base, api_key, account_id, limit=limit, role=role).get("items", [])


def iter_emails(
    base: str,
    api_key: str,
    account_id: str,
    *,
    after: datetime | None = None,
    before: datetime | None = None,
    search: str | None = None,
    role: str | None = "inbox",
    cap: int,
) -> tuple[list[dict], bool]:
    """Every message matching the filters, **oldest first**, and whether `cap` bit.

    Reversed on the way out because Unipile serves newest-first and the order
    is not configurable, while a watermark can only advance over a contiguous
    run of messages. Processing newest-first would leave the older half of an
    interrupted pass behind a mark that had already moved past it.

    `cap` is a runaway backstop, not a page size — it is why the second element
    of the return exists. A capped pass holds the *newest* `cap` messages, so
    the ones it did not collect are older than everything it did, and no single
    watermark can describe that. The caller's job is to not advance one.
    """
    collected: list[dict] = []
    cursor: str | None = None
    while True:
        page = _emails_page(
            base,
            api_key,
            account_id,
            limit=min(MAX_PAGE, cap - len(collected)),
            role=role,
            after=after,
            before=before,
            search=search,
            cursor=cursor,
        )
        items = page.get("items") or []
        collected.extend(items)
        cursor = page.get("cursor")
        if not items or not cursor or len(collected) >= cap:
            break

    collected.reverse()
    return collected, len(collected) >= cap


def wait_for_emails(
    base: str,
    api_key: str,
    account_id: str,
    *,
    limit: int = 10,
    timeout: int,
    interval: int = POLL_SECONDS,
    on_tick: Callable[[int], None] | None = None,
) -> list[dict]:
    """First page of the inbox once the initial sync produces one.

    An empty page straight after connecting means the sync is still running,
    not that the mailbox is empty.
    """
    started = time.monotonic()
    deadline = started + timeout
    items: list[dict] = []
    while True:
        try:
            items = list_emails(base, api_key, account_id, limit=limit)
        except UnipileError:
            items = []
        if items or time.monotonic() >= deadline:
            return items
        if on_tick:
            on_tick(int(time.monotonic() - started))
        time.sleep(interval)


def send_email(
    base: str,
    api_key: str,
    account_id: str,
    *,
    to: str,
    subject: str,
    body: str,
) -> None:
    """Send one mail as a connected mailbox.

    Unipile already holds the credentials and already does the transport, so
    there is no second OAuth and no provider client here. It goes out as the
    mailbox itself rather than as a no-reply address, which is what lets a
    recipient reply and reach a person.
    """
    request(
        "POST",
        base,
        "/emails",
        api_key,
        payload={
            "account_id": account_id,
            "to": [{"identifier": to}],
            "subject": subject,
            "body": body,
        },
    )


def download_attachment(
    base: str,
    api_key: str,
    account_id: str,
    email_provider_id: str,
    attachment_id: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> bytes:
    """Raw bytes of one attachment.

    Addressed by the email's `provider_id`, NOT its Unipile `id` — the latter
    404s on this route even though it is what /emails returns as the id.
    """
    url = (
        f"{base}{API_PREFIX}/emails/{urllib.parse.quote(email_provider_id)}"
        f"/attachments/{attachment_id}"
        f"?{urllib.parse.urlencode({'account_id': account_id})}"
    )
    http_request = urllib.request.Request(url, headers={"X-API-KEY": api_key})
    try:
        with urllib.request.urlopen(http_request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace").strip()
        raise UnipileError(f"GET {url} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise UnipileError(f"GET {url} -> {exc.reason}") from exc
