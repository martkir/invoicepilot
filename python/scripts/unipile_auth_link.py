"""Generate a Unipile Hosted Auth link for a user to connect a mailbox.

Ops script — run and exit. Never imported by the application.
Usage: python scripts/unipile_auth_link.py [EMAIL] [--provider GOOGLE ...]

Prompts for the address unless one is given on the command line.

One POST to /api/v1/hosted/accounts/link returns a temporary URL. The user
opens it, Unipile hosts the whole wizard (provider consent, 2FA, QR codes),
and on success POSTs {status, account_id, name} to the notify URL. Unlike the
Aurinko flow in list_recent_subjects.py, nothing is exchanged locally — there
is no code, no local callback listener, and no token to hold.

This script stops at the link. To connect and then read the mailbox in one go,
use unipile_connect_and_list.py instead.

Reads from python/.env or the repo-root .env:
  UNIPILE_API_KEY     (required)
  UNIPILE_DSN         (required, e.g. api8.unipile.com:13845)
  UNIPILE_NOTIFY_URL  (optional, must be publicly reachable)

Links are single-purpose and short-lived: Unipile invalidates every outstanding
link on its daily restart regardless of expiresOn, so generate one per connect
attempt rather than storing them.
"""

import argparse
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.unipile import (  # noqa: E402
    PROVIDERS,
    UnipileError,
    create_hosted_auth_link,
    credentials,
    expires_on,
)

log = get_logger("unipile-auth-link")

# Offered at the prompt, and used unattended when there is no tty to ask.
# Only a correlation key — see the note in main() about which mailbox
# actually gets connected.
DEFAULT_EMAIL = "martinvkirov@gmail.com"

DEFAULT_TTL_MINUTES = 15


def resolve_email(given: str | None) -> str:
    """The address to issue for: the argument, else the prompt, else the default."""
    if given:
        return given
    # Piped or cron'd, there is nobody to ask — take the default rather than
    # dying on EOF halfway through.
    if not sys.stdin.isatty():
        return DEFAULT_EMAIL
    return input(f"Email address [{DEFAULT_EMAIL}]: ").strip() or DEFAULT_EMAIL


def build_payload(args: argparse.Namespace, base: str, notify_url: str | None) -> dict:
    payload: dict[str, object] = {
        "type": args.type,
        "providers": args.provider,
        "api_url": base,
        "expiresOn": expires_on(args.expires_in),
        # Echoed back verbatim on the webhook — the only thing tying the
        # resulting account_id to a user of ours.
        "name": args.email,
    }
    if notify_url:
        payload["notify_url"] = notify_url
    if args.success_redirect_url:
        payload["success_redirect_url"] = args.success_redirect_url
    if args.failure_redirect_url:
        payload["failure_redirect_url"] = args.failure_redirect_url
    if args.type == "reconnect":
        payload["reconnect_account"] = args.reconnect_account
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "email",
        nargs="?",
        default=None,
        help="address the link is issued for, used as the `name` key (default: prompt)",
    )
    parser.add_argument(
        "--provider",
        action="append",
        choices=PROVIDERS,
        default=None,
        help="provider to offer in the wizard, repeatable (default: GOOGLE)",
    )
    parser.add_argument(
        "--type",
        choices=("create", "reconnect"),
        default="create",
        help="new connection, or re-auth of an account that went to CREDENTIALS",
    )
    parser.add_argument(
        "--reconnect-account",
        default=None,
        help="Unipile account_id to re-auth (required with --type reconnect)",
    )
    parser.add_argument(
        "--expires-in",
        type=int,
        default=DEFAULT_TTL_MINUTES,
        help=f"link lifetime in minutes (default: {DEFAULT_TTL_MINUTES})",
    )
    parser.add_argument(
        "--notify-url",
        default=None,
        help="override UNIPILE_NOTIFY_URL for this run",
    )
    parser.add_argument("--success-redirect-url", default=None)
    parser.add_argument("--failure-redirect-url", default=None)
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="print the link without opening a browser",
    )
    args = parser.parse_args()

    if args.expires_in < 1:
        parser.error("--expires-in must be at least 1 minute")
    if args.type == "reconnect" and not args.reconnect_account:
        parser.error("--reconnect-account is required with --type reconnect")
    args.provider = args.provider or ["GOOGLE"]

    try:
        base, api_key = credentials()
    except UnipileError as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc

    # Asked after the credential check, so a misconfigured .env fails before
    # anything is typed.
    args.email = resolve_email(args.email)

    notify_url = args.notify_url or get_settings().unipile_notify_url
    payload = build_payload(args, base, notify_url)
    try:
        url = create_hosted_auth_link(base, api_key, payload)
    except UnipileError as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc

    print(f"\nHosted auth link for {args.email} ({', '.join(args.provider)}):\n")
    print(f"  {url}\n")
    print(f"Expires {payload['expiresOn']} — and sooner if Unipile restarts.")

    # The wizard has no equivalent of Aurinko's authEmail, so the address above
    # constrains nothing: whichever account is picked at the provider is the one
    # that gets connected, under the name we sent.
    print(f"Sign in as {args.email} when the provider asks — the link does not enforce it.")

    if notify_url:
        print(f"Result will be POSTed to {notify_url}.")
    else:
        print(
            "No notify_url set, so the account_id will not be reported — "
            "read it from GET /api/v1/accounts afterwards."
        )

    if not args.no_open and not webbrowser.open(url):
        print("\nCould not open a browser automatically — copy the URL above.")


if __name__ == "__main__":
    main()
