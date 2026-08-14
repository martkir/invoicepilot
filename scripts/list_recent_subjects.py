"""Print the subjects on the first page of one mailbox, via Aurinko.

Ops script — run and exit. Never imported by the application.
Usage: python scripts/list_recent_subjects.py [--service Google] [--return-url URI]

Prompts for the address, builds an Aurinko authorization link, opens it, catches
the callback locally, exchanges the code for an account token, then prints the
subjects Aurinko returns on the first page of /v1/email/messages.

Reads from the repo-root .env:
  AURINKO_CLIENT_ID      (required)
  AURINKO_CLIENT_SECRET  (required)
  AURINKO_RETURN_URL     (optional, default http://localhost:57553)

The return URL must be registered under the app's authorized return URLs in the
Aurinko portal, and its port is the port this script listens on.
"""

import argparse
import base64
import http.server
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.config import get_settings  # noqa: E402
from backend.core.logging import get_logger  # noqa: E402

log = get_logger("list-subjects")

API = "https://api.aurinko.io/v1"
AUTH_URL = f"{API}/auth/authorize"
# Space separated per the API reference. The scopes page shows commas instead;
# the reference is the authority, and space is what the portal's own sample uses.
SCOPES = "Mail.Read"

# Aurinko names one service per provider — there is no auto-detect, so the
# common consumer domains are mapped here and anything else has to be told.
SERVICES = ("Google", "Office365", "EWS", "IMAP", "iCloud")
DOMAIN_SERVICE = {
    "gmail.com": "Google",
    "googlemail.com": "Google",
    "outlook.com": "Office365",
    "hotmail.com": "Office365",
    "live.com": "Office365",
    "msn.com": "Office365",
    "icloud.com": "iCloud",
    "me.com": "iCloud",
}

# Loopback hosts a return URL may name. Bound as 127.0.0.1 either way, so the
# listener is never reachable off this machine.
LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}
BIND_HOST = "127.0.0.1"

CALLBACK_PAGE = "<html><body><h1>{title}</h1><p>{body}</p></body></html>"


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Single-shot handler that captures the ?code=/?status= callback."""

    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's naming
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" not in query and "status" not in query:
            # Browsers also ask for /favicon.ico; ignore anything that isn't the callback.
            self.send_error(404)
            return

        self.server.callback_query = query  # type: ignore[attr-defined]
        ok = "code" in query and query.get("status", ["success"])[0] == "success"
        page = CALLBACK_PAGE.format(
            title="&#10003; Authorization successful!" if ok else "Authorization failed",
            body=(
                "You can close this window and return to the terminal."
                if ok
                else f"Aurinko returned: {urllib.parse.urlparse(self.path).query}"
            ),
        ).encode()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, *args: object) -> None:
        """Silence the default stderr access log."""


def callback_port(return_url: str) -> int:
    """Port to listen on, validated out of the configured return URL."""
    parsed = urllib.parse.urlparse(return_url)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS:
        raise RuntimeError(
            f"AURINKO_RETURN_URL must be an http:// loopback URI "
            f"(localhost or 127.0.0.1), got {return_url!r}."
        )
    if parsed.port is None:
        raise RuntimeError(f"AURINKO_RETURN_URL needs an explicit port, got {return_url!r}.")
    return parsed.port


def infer_service(email: str) -> str | None:
    """Aurinko service type for the address, or None if the domain is unknown."""
    _, _, domain = email.partition("@")
    return DOMAIN_SERVICE.get(domain.lower())


def _send(request: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace").strip()
        raise RuntimeError(f"{request.full_url} -> HTTP {exc.code}: {detail}") from exc


def _api_get(path: str, token: str, params: dict[str, object] | None = None) -> dict:
    url = f"{API}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    return _send(request)


def authorize(
    email: str, service: str, client_id: str, client_secret: str, return_url: str
) -> tuple[int, str]:
    """Run the Aurinko auth flow and return (account_id, access_token)."""
    port = callback_port(return_url)
    state = secrets.token_urlsafe(32)

    auth_url = f"{AUTH_URL}?" + urllib.parse.urlencode(
        {
            "clientId": client_id,
            "serviceType": service,
            "scopes": SCOPES,
            "responseType": "code",
            "returnUrl": return_url,
            "state": state,
            "loginHint": email,
            # Hard constraint: Aurinko fails the flow rather than connecting a
            # different mailbox than the one that was typed.
            "authEmail": email,
        }
    )

    # Bind before opening the browser, so the callback can never arrive early.
    try:
        server = http.server.HTTPServer((BIND_HOST, port), _CallbackHandler)
    except OSError as exc:
        raise RuntimeError(
            f"Could not listen on {BIND_HOST}:{port} ({exc}). "
            "Free the port, or set AURINKO_RETURN_URL to a spare one — "
            "and register that exact URL on the app in the Aurinko portal too."
        ) from exc
    server.callback_query = None  # type: ignore[attr-defined]

    print("\nApprove access in the browser:\n")
    print(f"  {auth_url}\n")
    if not webbrowser.open(auth_url):
        print("Could not open a browser automatically — copy the URL above.\n")
    print("Waiting for the callback on", return_url, "...")

    try:
        while server.callback_query is None:  # type: ignore[attr-defined]
            server.handle_request()
    finally:
        server.server_close()

    query: dict[str, list[str]] = server.callback_query  # type: ignore[attr-defined]
    status = query.get("status", ["success"])[0]
    if status != "success" or "code" not in query:
        raise RuntimeError(f"Authorization failed: {urllib.parse.urlencode(query, doseq=True)}")
    if query.get("state", [None])[0] != state:
        raise RuntimeError("State mismatch on the Aurinko callback — aborting.")

    # The code is exchanged app-to-app, so this call carries the client secret
    # as HTTP Basic rather than the account token.
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    code = urllib.parse.quote(query["code"][0], safe="")
    token = _send(
        urllib.request.Request(
            f"{API}/auth/token/{code}",
            data=b"",
            method="POST",
            headers={"Authorization": f"Basic {basic}"},
        )
    )
    return token["accountId"], token["accessToken"]


def first_page(token: str) -> tuple[list[dict], str | None]:
    """First page of messages, plus the token for the next one if there is one."""
    # /v1/email/messages has no page-size parameter — Aurinko picks the size.
    page = _api_get("/email/messages", token, {"bodyType": "text"})
    return page.get("records", []), page.get("nextPageToken")


def _received(record: dict) -> str:
    stamp = record.get("receivedAt") or record.get("sentAt")
    if not stamp:
        return " " * 16
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return stamp[:16]
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M")


def _sender(record: dict) -> str:
    sender = record.get("from") or {}
    return sender.get("address") or sender.get("name") or "(unknown sender)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--service",
        choices=SERVICES,
        default=None,
        help="Aurinko service type (default: inferred from the address' domain)",
    )
    parser.add_argument(
        "--return-url",
        default=None,
        help="override AURINKO_RETURN_URL for this run",
    )
    args = parser.parse_args()

    settings = get_settings()
    client_id = settings.aurinko_client_id
    client_secret = settings.aurinko_client_secret
    if not client_id or not client_secret:
        log.error(
            "AURINKO_CLIENT_ID / AURINKO_CLIENT_SECRET are not set. "
            "Add them to the repo-root .env (see .env.example)."
        )
        raise SystemExit(1)

    email = input("Email address: ").strip()
    if not email:
        log.error("No address given.")
        raise SystemExit(1)

    service = args.service or infer_service(email)
    if not service:
        service = input(f"Provider {'/'.join(SERVICES)}: ").strip()
    if service not in SERVICES:
        log.error("Unknown service type %r — expected one of %s.", service, ", ".join(SERVICES))
        raise SystemExit(1)

    return_url = args.return_url or settings.aurinko_return_url
    account_id, token = authorize(email, service, client_id, client_secret, return_url)
    print(f"\nConnected {email} as Aurinko account {account_id}.")

    records, next_page_token = first_page(token)
    if not records:
        print(f"\nNo messages returned for {email}.")
        return

    print(f"\n{len(records)} messages on the first page for {email}:\n")
    for record in records:
        subject = record.get("subject") or "(no subject)"
        print(f"  {_received(record)}  {subject}   — {_sender(record)}")
    if next_page_token:
        print("\nMore pages available (nextPageToken returned) — only the first is shown.")


if __name__ == "__main__":
    main()
