"""Scan orchestration — the counting across mailboxes, without a network."""

import pytest

from invoicepilot import process
from invoicepilot.process import Progress, ScanResult, scan_all


@pytest.fixture
def two_mailboxes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process, "credentials", lambda: ("https://api.test", "key"))
    monkeypatch.setattr(
        process,
        "list_connected",
        lambda base, api_key: [
            {"id": "a1", "name": "one@example.com"},
            {"id": "a2", "name": "two@example.com"},
        ],
    )


def test_progress_counts_the_scan_not_the_mailbox(
    two_mailboxes: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Counts must climb across the whole scan.

    scan_account counts from zero every time, so without the shift in scan_all
    a dashboard watching a second mailbox would see "scanned 34" drop back to
    "scanned 1" partway through.
    """

    def two_messages(
        base, api_key, account, *, limit, follow_links, on_progress=None
    ) -> ScanResult:
        mailbox = account["name"]
        for index in (1, 2):
            on_progress(Progress(mailbox, f"message {index}", index, 2, index))
        return ScanResult(mailboxes=(mailbox,), messages_scanned=2, invoices_found=2)

    monkeypatch.setattr(process, "scan_account", two_messages)

    seen: list[tuple[int, int, int]] = []
    result = scan_all(
        on_progress=lambda p: seen.append((p.messages_scanned, p.messages_total, p.invoices_found))
    )

    assert seen == [(1, 2, 1), (2, 2, 2), (3, 4, 3), (4, 4, 4)]
    assert (result.messages_scanned, result.invoices_found) == (4, 4)


def test_an_unreachable_mailbox_does_not_shift_the_ones_after_it(
    two_mailboxes: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mailbox that fails scanned nothing, so it must add nothing to the tally."""

    def first_one_fails(
        base, api_key, account, *, limit, follow_links, on_progress=None
    ) -> ScanResult:
        mailbox = account["name"]
        if account["id"] == "a1":
            raise process.UnipileError("credentials expired")
        on_progress(Progress(mailbox, "message 1", 1, 1, 0))
        return ScanResult(mailboxes=(mailbox,), messages_scanned=1)

    monkeypatch.setattr(process, "scan_account", first_one_fails)

    seen: list[int] = []
    result = scan_all(on_progress=lambda p: seen.append(p.messages_scanned))

    assert seen == [1]
    assert result.messages_scanned == 1
    assert [e.detail for e in result.errors] == ["credentials expired"]
