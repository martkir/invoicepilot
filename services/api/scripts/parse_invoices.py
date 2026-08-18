"""Scan connected mailboxes for invoices and file what parses.

Ops script — run and exit. Never imported by the application.
Usage: python services/api/scripts/parse_invoices.py [--limit 20] [--no-follow-links]

All the work lives in invoicepilot/process.py, which the API calls too. This file is
only the terminal's half of it: arguments, a progress line, and a report.

Recognition is per-issuer — invoice2data reports a document only when one of
its templates matches — so an invoice from an untaught vendor parses to nothing
and looks exactly like an ordinary email here. Add YAML under
templates/invoice2data/ to teach a new issuer.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from invoicepilot.core.logging import get_logger  # noqa: E402
from invoicepilot.invoice_store import DATA_ROOT  # noqa: E402
from invoicepilot.process import DEFAULT_LIMIT, Progress, ScanResult, scan_all  # noqa: E402
from invoicepilot.unipile import UnipileError  # noqa: E402

log = get_logger("parse-invoices")


def show(progress: Progress) -> None:
    subject = progress.subject[:52]
    print(f"  [{progress.messages_scanned}/{progress.messages_total}] {subject:54} ", end="")
    print(f"{progress.invoices_found} invoice(s) so far")


def report(result: ScanResult) -> None:
    print(
        f"\nScanned {result.messages_scanned} message(s) "
        f"across {len(result.mailboxes)} mailbox(es): {', '.join(result.mailboxes)}."
    )

    if result.errors:
        print(f"\n{len(result.errors)} document(s) could not be read — these were NOT checked:")
        for error in result.errors:
            print(f"  {error.mailbox} | {error.subject[:40]}: {error.detail}")

    if not result.invoices_found:
        print("\nNo invoices recognised.")
        return

    print(
        f"\n{result.invoices_found} invoice(s) recognised, "
        f"{result.invoices_new} of them new.\nFiled under {DATA_ROOT} and in the database."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"messages to scan per mailbox (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--no-follow-links",
        action="store_true",
        help="do not fetch invoices linked from a message body (keeps the scan offline)",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    try:
        result = scan_all(
            limit=args.limit,
            follow_links=not args.no_follow_links,
            on_progress=show,
        )
    except UnipileError as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc

    report(result)


if __name__ == "__main__":
    main()
