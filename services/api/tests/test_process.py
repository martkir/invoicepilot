"""Scan orchestration — where a scan starts, how far it counts, what it records.

None of this opens a session: the watermark table is stood in for by a dict, so
a regression that reaches the database fails by needing DATABASE_URL rather than
by asserting.
"""

from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime, timedelta

import pytest

from invoicepilot import process
from invoicepilot.process import (
    RESCAN_OVERLAP,
    SEED_LOOKBACK,
    Progress,
    ScanResult,
    keyword_query,
    message_date,
    scan_all,
    scan_from,
)

# The workspace these tests scan into. Which one it is never matters here —
# what a scan does *within* one workspace is the subject, and what separates
# two of them is test_workspaces.py.
WS = "ws-test"

# The account ids that workspace owns, as accounts.list_connected would be
# given. Stubbed out alongside it in `two_mailboxes`, so the value only has to
# be a list.
ALLOWED = ["a1", "a2"]


@pytest.fixture
def marks(monkeypatch: pytest.MonkeyPatch) -> dict[str, datetime]:
    """An in-memory stand-in for the mailbox_scans table."""
    store: dict[str, datetime] = {}

    @contextmanager
    def no_session():
        yield None

    monkeypatch.setattr(process, "session_scope", no_session)
    # Keyed on the mailbox alone: these tests run in one workspace, and the
    # column that separates two of them is covered in test_workspaces.py.
    monkeypatch.setattr(process.mailboxes, "watermark", lambda _s, _ws, mailbox: store.get(mailbox))
    monkeypatch.setattr(
        process.mailboxes,
        "set_watermark",
        lambda _s, _ws, mailbox, at: store.update({mailbox: at}),
    )
    return store


@pytest.fixture
def two_mailboxes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process, "credentials", lambda: ("https://api.test", "key"))
    monkeypatch.setattr(
        process,
        "list_connected",
        lambda base, api_key, allowed: [
            {"id": "a1", "name": "one@example.com"},
            {"id": "a2", "name": "two@example.com"},
        ],
    )


# --- where a scan starts ---------------------------------------------------


def test_a_mailbox_never_scanned_reaches_sixty_days_back(marks: dict) -> None:
    at = scan_from(WS, "new@example.com")
    assert abs((datetime.now(UTC) - SEED_LOOKBACK) - at) < timedelta(seconds=5)


def test_a_scanned_mailbox_resumes_from_its_watermark(marks: dict) -> None:
    mark = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    marks["seen@example.com"] = mark
    assert scan_from(WS, "seen@example.com") == mark - RESCAN_OVERLAP


def test_an_ancient_watermark_is_honoured_rather_than_clamped(marks: dict) -> None:
    """The explicit decision: never step over mail nobody has looked at.

    Clamping a stale mark to the seed window would advance it past months of
    unexamined mail, and an invoice skipped that way is skipped for good.
    """
    ancient = datetime(2024, 1, 1, tzinfo=UTC)
    marks["old@example.com"] = ancient
    assert scan_from(WS, "old@example.com") == ancient - RESCAN_OVERLAP


def test_since_overrides_the_watermark(marks: dict) -> None:
    marks["seen@example.com"] = datetime(2026, 8, 10, tzinfo=UTC)
    asked = datetime(2026, 1, 1, tzinfo=UTC)
    assert scan_from(WS, "seen@example.com", asked) == asked


# --- the keyword filter ----------------------------------------------------


def test_keywords_join_with_the_only_operator_the_provider_understands() -> None:
    """A space means AND to the provider and a comma means nothing — verified."""
    assert keyword_query(("invoice", "receipt", "Фактура")) == "invoice OR receipt OR Фактура"
    assert keyword_query(("invoice",)) == "invoice"


def test_the_shipped_list_covers_the_languages_the_templates_parse() -> None:
    """bolt_invoice_bg.yml parses Bulgarian; an English-only list would miss it."""
    assert "invoice" in process.INVOICE_KEYWORDS
    assert "Фактура" in process.INVOICE_KEYWORDS


# --- message dates ---------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-08-08T07:22:00.000Z", datetime(2026, 8, 8, 7, 22, tzinfo=UTC)),
        ("2026-08-08T07:22:00+00:00", datetime(2026, 8, 8, 7, 22, tzinfo=UTC)),
        # Naive input is read as UTC rather than crashing a comparison later.
        ("2026-08-08T07:22:00", datetime(2026, 8, 8, 7, 22, tzinfo=UTC)),
        (None, None),
        ("", None),
        ("not a date", None),
    ],
)
def test_message_date_reads_what_unipile_sends(raw, expected) -> None:
    assert message_date({"date": raw}) == expected


# --- counting across mailboxes ---------------------------------------------


def test_progress_counts_the_scan_not_the_mailbox(
    two_mailboxes: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Counts must climb across the whole scan.

    scan_account counts from zero every time, so without the shift in scan_all
    a dashboard watching a second mailbox would see "scanned 34" drop back to
    "scanned 1" partway through.
    """

    def two_messages(
        base, api_key, workspace_id, account, *, on_progress=None, **kwargs
    ) -> ScanResult:
        mailbox = account["name"]
        for index in (1, 2):
            on_progress(Progress(mailbox, f"message {index}", index, 2, index))
        return ScanResult(mailboxes=(mailbox,), messages_scanned=2, invoices_found=2)

    monkeypatch.setattr(process, "scan_account", two_messages)

    seen: list[tuple[int, int, int]] = []
    result = scan_all(
        WS,
        ALLOWED,
        on_progress=lambda p: seen.append((p.messages_scanned, p.messages_total, p.invoices_found)),
    )

    assert seen == [(1, 2, 1), (2, 2, 2), (3, 4, 3), (4, 4, 4)]
    assert (result.messages_scanned, result.invoices_found) == (4, 4)


def test_an_unreachable_mailbox_does_not_shift_the_ones_after_it(
    two_mailboxes: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mailbox that failed scanned nothing, so it must add nothing to the tally."""

    def first_one_fails(
        base, api_key, workspace_id, account, *, on_progress=None, **kwargs
    ) -> ScanResult:
        mailbox = account["name"]
        if account["id"] == "a1":
            raise process.UnipileError("credentials expired")
        on_progress(Progress(mailbox, "message 1", 1, 1, 0))
        return ScanResult(mailboxes=(mailbox,), messages_scanned=1)

    monkeypatch.setattr(process, "scan_account", first_one_fails)

    seen: list[int] = []
    result = scan_all(WS, ALLOWED, on_progress=lambda p: seen.append(p.messages_scanned))

    assert seen == [1]
    assert result.messages_scanned == 1
    assert [e.detail for e in result.errors] == ["credentials expired"]


# --- what a pass leaves behind ---------------------------------------------


@pytest.fixture
def mailbox(monkeypatch: pytest.MonkeyPatch):
    """scan_account over a canned message list, with nothing to extract."""
    monkeypatch.setattr(process.extract, "candidates", lambda *a, **k: [])

    def run(messages: list[dict], capped: bool = False, **kwargs) -> ScanResult:
        monkeypatch.setattr(process, "iter_emails", lambda *a, **k: (messages, capped))
        return process.scan_account(
            "https://api.test", "key", WS, {"id": "a1", "name": "one@example.com"}, **kwargs
        )

    return run


def _mail(date: str, subject: str = "hello") -> dict:
    return {"id": date, "provider_id": date, "date": date, "subject": subject}


def test_a_clean_pass_marks_the_mailbox_to_its_newest_message(mailbox, marks: dict) -> None:
    """The newest message processed, not now(): a clock reading would claim
    mail the provider had not finished syncing."""
    mailbox([_mail("2026-08-01T09:00:00.000Z"), _mail("2026-08-03T09:00:00.000Z")])
    assert marks["one@example.com"] == datetime(2026, 8, 3, 9, 0, tzinfo=UTC)


def test_an_undated_message_does_not_become_the_watermark(mailbox, marks: dict) -> None:
    mailbox([_mail("2026-08-01T09:00:00.000Z"), {"id": "x", "provider_id": "x", "date": None}])
    assert marks["one@example.com"] == datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def test_an_empty_mailbox_leaves_the_watermark_alone(mailbox, marks: dict) -> None:
    marks["one@example.com"] = datetime(2026, 8, 1, tzinfo=UTC)
    result = mailbox([])
    assert marks["one@example.com"] == datetime(2026, 8, 1, tzinfo=UTC)
    assert result.messages_scanned == 0


def test_a_capped_pass_reports_it_and_does_not_advance_the_watermark(mailbox, marks: dict) -> None:
    """A capped pass holds the newest N, so what it missed is older than
    everything it handled — which no single watermark can describe."""
    result = mailbox([_mail("2026-08-03T09:00:00.000Z")], capped=True)
    assert "one@example.com" not in marks
    assert len(result.errors) == 1
    assert "still unscanned" in result.errors[0].detail


def test_keywords_reach_the_query_and_no_keywords_drops_it(monkeypatch, marks: dict) -> None:
    monkeypatch.setattr(process.extract, "candidates", lambda *a, **k: [])
    asked: list[str | None] = []

    def spy(*a, search=None, **k):
        asked.append(search)
        return [], False

    monkeypatch.setattr(process, "iter_emails", spy)
    account = {"id": "a1", "name": "one@example.com"}
    process.scan_account("https://api.test", "key", WS, account)
    process.scan_account("https://api.test", "key", WS, account, keywords=False)

    assert asked[0] == keyword_query()
    assert asked[1] is None


def test_a_stalled_issuer_is_not_asked_about_again_this_scan(monkeypatch):
    """A rate limit is worth retrying later, not fifteen times now.

    learn.teach deliberately records nothing when the request itself fails —
    a timeout says nothing about the document. But without an in-scan memory
    that means one outage costs one request per message: a rate-limited run of
    a real mailbox asked about receipts@bolt.eu fifteen times.
    """
    from invoicepilot import gate, learn, process

    asked = []

    def always_fails(text, sender, **kwargs):
        asked.append(sender)
        raise RuntimeError("rate limited")

    monkeypatch.setattr(learn, "teach", always_fails)
    monkeypatch.setattr(gate, "looks_like_invoice", lambda *a, **k: True)
    monkeypatch.setattr(process.extract, "candidates", lambda *a, **k: [])
    monkeypatch.setattr(process.extract, "body_text", lambda m: "Total 1.00")
    monkeypatch.setattr(process, "teachable_text", lambda c: "Total 1.00")
    monkeypatch.setattr(process, "scan_from", lambda *a, **k: None)
    monkeypatch.setattr(process.mailboxes, "set_watermark", lambda *a, **k: None)
    monkeypatch.setattr(process, "session_scope", lambda: nullcontext(None))

    sender = {"identifier": "receipts@bolt.eu"}
    messages = [
        {"from_attendee": sender, "subject": f"ride {n}", "provider_id": "p", "id": str(n)}
        for n in range(5)
    ]
    monkeypatch.setattr(process, "iter_emails", lambda *a, **k: (messages, False))

    result = process.scan_account("base", "key", "ws", {"id": "a1", "name": "m"})

    assert asked == ["receipts@bolt.eu"]
    assert len(result.errors) == 1
