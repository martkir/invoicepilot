"""Connect a mailbox through Unipile, then print its most recent inbox mail.

Ops script — run and exit. Never imported by the application.
Usage: python scripts/unipile_connect_and_list.py [EMAIL] [--limit 10]

The whole loop in one command: generate a hosted auth link, open it, wait for
the account to appear, then list the inbox. Waiting is done by polling
GET /api/v1/accounts, because the alternative — a notify_url webhook — needs a
publicly reachable endpoint that a laptop does not have.

For the link on its own (to hand to someone else), use unipile_auth_link.py.

Reads UNIPILE_API_KEY and UNIPILE_DSN from the repo-root .env.
"""

import argparse
import sys
import webbrowser
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.logging import get_logger  # noqa: E402
from backend.unipile import (  # noqa: E402
    UnipileError,
    account_status,
    create_hosted_auth_link,
    credentials,
    expires_on,
    list_accounts,
    wait_for_account,
    wait_for_emails,
)

log = get_logger("unipile-connect")

# Offered at the prompt, and used unattended when there is no tty to ask.
DEFAULT_EMAIL = "martinvkirov@gmail.com"

LINK_TTL_MINUTES = 15
CONNECT_TIMEOUT_SECONDS = 300
# Mail lands a little after the account does, so an empty first page right
# after connecting means "still syncing", not "empty mailbox".
SYNC_TIMEOUT_SECONDS = 60

SENDER_WIDTH = 38


def resolve_email(given: str | None) -> str:
    """The address to connect: the argument, else the prompt, else the default."""
    if given:
        return given
    if not sys.stdin.isatty():
        return DEFAULT_EMAIL
    return input(f"Email address [{DEFAULT_EMAIL}]: ").strip() or DEFAULT_EMAIL


def ticker(label: str) -> Callable[[int], None]:
    """Progress line printer for the polling helpers."""

    def tick(elapsed: int) -> None:
        print(f"\r  {label} ({elapsed}s)...", end="", flush=True)

    return tick


def clear_progress() -> None:
    print("\r" + " " * 60 + "\r", end="", flush=True)


def received(item: dict) -> str:
    stamp = item.get("date")
    if not stamp:
        return " " * 16
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return stamp[:16]
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M")


def sender(item: dict) -> str:
    attendee = item.get("from_attendee") or {}
    name = attendee.get("display_name")
    address = attendee.get("identifier")
    if name and address and name != address:
        return f"{name} <{address}>"
    return name or address or "(unknown sender)"


def flags(item: dict) -> str:
    # read_status comes back null on Google accounts; the UNREAD folder is
    # what actually carries the state.
    marks = []
    if "UNREAD" in (item.get("folders") or []):
        marks.append("unread")
    if item.get("has_attachments"):
        marks.append("attachment")
    return f"  [{', '.join(marks)}]" if marks else ""


def print_inbox(items: list[dict], email: str, limit: int) -> None:
    if not items:
        print(f"\nNo inbox mail returned for {email} yet.")
        print("The initial sync may still be running — re-run to check again.")
        return

    print(f"\n{len(items)} most recent inbox messages for {email}:\n")
    for item in items:
        subject = item.get("subject") or "(no subject)"
        who = sender(item)
        if len(who) > SENDER_WIDTH:
            who = who[: SENDER_WIDTH - 1] + "…"
        print(f"  {received(item)}  {who:<{SENDER_WIDTH}}  {subject}{flags(item)}")
    if len(items) < limit:
        print(f"\nOnly {len(items)} message(s) in the inbox — fewer than the {limit} requested.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "email",
        nargs="?",
        default=None,
        help="address to connect, used as the `name` key (default: prompt)",
    )
    parser.add_argument("--limit", type=int, default=10, help="messages to print (default: 10)")
    parser.add_argument(
        "--timeout",
        type=int,
        default=CONNECT_TIMEOUT_SECONDS,
        help=f"seconds to wait for the account (default: {CONNECT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--no-open", action="store_true", help="print the link without opening a browser"
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    try:
        base, api_key = credentials()
        email = resolve_email(args.email)

        # Snapshot first: the new account is whatever was not here before.
        known_ids = {a.get("id") for a in list_accounts(base, api_key)}

        url = create_hosted_auth_link(
            base,
            api_key,
            {
                "type": "create",
                "providers": ["GOOGLE"],
                "api_url": base,
                "expiresOn": expires_on(LINK_TTL_MINUTES),
                "name": email,
            },
        )
    except UnipileError as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc

    print(f"\nConnect {email} here:\n")
    print(f"  {url}\n")
    # The wizard has no way to pin a link to one mailbox — whichever account is
    # picked at the provider is the one that gets connected.
    print(f"Sign in as {email} when Google asks — the link does not enforce it.")

    if not args.no_open and not webbrowser.open(url):
        print("Could not open a browser automatically — copy the URL above.")

    print()
    account = wait_for_account(
        base,
        api_key,
        known_ids,
        email,
        timeout=args.timeout,
        on_tick=ticker("waiting for the account"),
    )
    clear_progress()
    if account is None:
        log.error(
            "No account connected within %ss. The link may have expired — re-run to get a new one.",
            args.timeout,
        )
        raise SystemExit(1)

    account_id = account["id"]
    status = account_status(account)
    print(
        f"Connected {account.get('name')} as {account_id} ({account.get('type')}), status {status}."
    )
    if status != "OK":
        print(f"Status is {status}, not OK — anything listed below may be stale.")

    try:
        items = wait_for_emails(
            base,
            api_key,
            account_id,
            limit=args.limit,
            timeout=SYNC_TIMEOUT_SECONDS,
            on_tick=ticker("waiting for the first sync"),
        )
    except UnipileError as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc
    clear_progress()

    print_inbox(items, email, args.limit)


if __name__ == "__main__":
    main()
