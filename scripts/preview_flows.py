#!/usr/bin/env python3
"""Serve the flow mockups and open the paginated viewer.

The screens link to ``frontend/src/styles/tokens.css`` with a ``../../../``
prefix, so the server root has to be the repository root -- serving
``docs/flows`` directly would 404 every stylesheet and render the pages
unstyled.

Each flow is a directory under ``docs/flows`` holding numbered screens, an
``index.html`` contact sheet and a ``viewer.html``. Name the one you want; with
no name, the only flow is opened, or the available ones are listed.

Usage:
    python scripts/preview_flows.py [flow] [--port N] [--no-browser]
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import socket
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLOWS = ROOT / "docs/flows"
DEFAULT_PORT = 8020


class Handler(http.server.SimpleHTTPRequestHandler):
    """Quiet handler that never lets the browser cache a mockup."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        if not self.path.startswith("/docs/flows"):
            return
        sys.stderr.write(f"  {self.path}\n")


def find_port(preferred: int) -> int:
    """Return `preferred` if it is free, else the next free port after it."""
    for port in range(preferred, preferred + 50):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit(f"No free port in {preferred}..{preferred + 50}")


def available() -> list[str]:
    """Every flow directory that has a viewer to open."""
    return sorted(d.name for d in FLOWS.iterdir() if (d / "viewer.html").is_file())


def resolve(name: str | None) -> str:
    """The flow to serve, as a path relative to the repository root."""
    flows = available()
    if not flows:
        raise SystemExit(f"No flows with a viewer.html under {FLOWS}")

    if name is None:
        # One flow is unambiguous; more than one is a question only the caller
        # can answer, so list them rather than guessing.
        if len(flows) > 1:
            listed = "\n".join(f"    {f}" for f in flows)
            raise SystemExit(f"Name a flow:\n{listed}")
        name = flows[0]

    name = name.strip("/").removeprefix("docs/flows/")
    if name not in flows:
        listed = ", ".join(flows)
        raise SystemExit(f"No such flow: {name}\nAvailable: {listed}")
    return f"docs/flows/{name}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("flow", nargs="?", help="directory under docs/flows, e.g. share-flow")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true", help="just print the URL")
    args = ap.parse_args()

    flow = resolve(args.flow)
    port = find_port(args.port)
    url = f"http://localhost:{port}/{flow}/viewer.html"

    handler = functools.partial(Handler, directory=str(ROOT))
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        screens = sorted((ROOT / flow).glob("[0-9]*.html"))
        print(f"\n  {Path(flow).name}  →  {url}")
        print(f"  {len(screens)} screens · ← / → to paginate · ? for shortcuts")
        print("  Ctrl+C to stop\n")

        if not args.no_browser:
            threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

        with contextlib.suppress(KeyboardInterrupt):
            httpd.serve_forever()
        print("\n  Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
