"""Re-derive every template with the model, and check the result matches.

Ops script — run and exit. Never imported by the application.
Usage: python services/api/scripts/rebuild_templates_from_scratch.py <workspace-id>

Hides the repository's own templates, points generated ones at a scratch
directory, and runs a real mailbox through the scan pipeline with nothing
taught. Whatever the model writes is the only thing reading those documents,
so the invoices that come out are a direct answer to "would this have worked
if we had never written a template by hand?".

The comparison is against what is in the database now, keyed on the message the
invoice came from, so a difference points at a document rather than at a row.
Nothing is written: no database, no .data, no template outside the scratch
directory, which is printed at the end rather than deleted.

Costs one request per sending domain that passes the gate and parses to
nothing. Reads the mailbox through Unipile and needs the same credentials a
scan does.
"""

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invoicepilot import extract, gate, learn, process  # noqa: E402
from invoicepilot.accounts import list_connected  # noqa: E402
from invoicepilot.core.db import session_scope  # noqa: E402
from invoicepilot.core.logging import get_logger  # noqa: E402
from invoicepilot.invoices import recent  # noqa: E402
from invoicepilot.unipile import credentials, download_attachment, iter_emails  # noqa: E402
from invoicepilot.workspaces import account_ids  # noqa: E402

log = get_logger("rebuild-templates")

COMPARED = ("date", "amount", "currency", "invoice_number")


def baseline(workspace_id: str) -> dict[str, dict]:
    """What is filed today, keyed on the message each invoice came from."""
    with session_scope() as session:
        rows = recent(session, workspace_id, limit=200)
    return {row["email"]["message_id"]: row["invoice"] for row in rows}


def rebuild(workspace_id: str, scratch: Path) -> dict[str, dict]:
    """Every invoice the mailbox yields with only model-written templates."""
    base, api_key = credentials()
    accounts = list_connected(base, api_key, account_ids_for(workspace_id))
    found: dict[str, dict] = {}

    for account in accounts:
        account_id = account["id"]
        messages, _ = iter_emails(
            base,
            api_key,
            account_id,
            after=datetime.now(UTC) - process.SEED_LOOKBACK,
            search=process.keyword_query(),
            cap=process.MAX_MESSAGES_PER_SCAN,
        )
        print(f"{account.get('name') or account_id}: {len(messages)} message(s)\n")

        for message in messages:

            def fetch(attachment_id: str, message: dict = message) -> bytes:
                return download_attachment(
                    base, api_key, account_id, message["provider_id"], attachment_id
                )

            candidates = extract.candidates(message, fetch)
            fields = first_match(candidates, message, fetch)

            if fields is None:
                sender = (message.get("from_attendee") or {}).get("identifier") or ""
                if gate.looks_like_invoice(
                    sender,
                    extract.body_text(message),
                    has_attachment=bool(message.get("attachments")),
                ):
                    try:
                        path = learn.teach(process.teachable_text(candidates), sender)
                    except Exception as exc:  # noqa: BLE001 — one issuer must not end the run
                        print(f"  !! {sender}: {exc}")
                        continue
                    if path:
                        print(f"  ++ taught {sender} -> {path.name}")
                        fields = first_match(candidates, message, fetch)

            if fields is not None:
                found[message.get("message_id")] = fields
    return found


def account_ids_for(workspace_id: str) -> list[str]:
    with session_scope() as session:
        return account_ids(session, workspace_id)


def first_match(candidates: list, message: dict, fetch) -> dict | None:
    for candidate in candidates:
        invoice, _ = extract.extract(candidate, message, fetch, follow_links=True)
        if invoice is not None:
            return invoice.fields
    return None


def compare(before: dict[str, dict], after: dict[str, dict]) -> int:
    """Print the differences. Returns how many invoices disagree."""
    disagreed = 0
    for message_id in sorted(before.keys() | after.keys()):
        old, new = before.get(message_id), after.get(message_id)
        if old is None:
            print(f"EXTRA    {new.get('issuer')} {new.get('date')} {new.get('amount')}")
            continue
        if new is None:
            print(f"MISSING  {old.get('issuer')} {old.get('date')} {old.get('amount')}")
            disagreed += 1
            continue
        differences = [
            f"{name}: {old.get(name)!r} -> {new.get(name)!r}"
            for name in COMPARED
            if str(old.get(name) or "")[:10] != str(new.get(name) or "")[:10]
        ]
        if differences:
            disagreed += 1
            print(f"DIFFERS  {old.get('issuer')}  " + "; ".join(differences))
    return disagreed


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    workspace_id = sys.argv[1]

    before = baseline(workspace_id)
    print(f"{len(before)} invoice(s) filed today\n")

    scratch = Path(tempfile.mkdtemp(prefix="invoicepilot-scratch-"))
    # The point of the exercise: nothing is taught, so the only templates that
    # can read these documents are the ones the model writes during the run.
    extract.TEMPLATE_DIR = scratch / "none"
    extract.GENERATED_TEMPLATE_DIR = scratch
    extract.forget_templates()

    after = rebuild(workspace_id, scratch)

    print(f"\n{len(after)} invoice(s) rebuilt, from {len(list(scratch.glob('*.yml')))} template(s)")
    for path in sorted(scratch.glob("*.yml")):
        print(f"\n===== {path.name}\n{path.read_text(encoding='utf-8')}")
    for path in sorted(scratch.glob("*.failed")):
        print(f"\n----- {path.name}: {path.read_text(encoding='utf-8').strip()}")

    print("\n=== against what is filed today ===")
    disagreed = compare(before, after)
    print(
        f"\n{len(before) - disagreed}/{len(before)} match. Templates left in {scratch}"
        if before
        else f"\nNothing to compare against. Templates left in {scratch}"
    )


if __name__ == "__main__":
    main()
