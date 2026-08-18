"""The Unipile client's paging and date handling, against a stubbed transport."""

from datetime import UTC, datetime

import pytest

from invoicepilot import unipile
from invoicepilot.unipile import iter_emails, stamp


def test_stamp_is_the_iso_utc_form_the_filters_require() -> None:
    assert stamp(datetime(2026, 8, 8, 7, 22, tzinfo=UTC)) == "2026-08-08T07:22:00.000Z"


def test_stamp_converts_rather_than_relabels() -> None:
    """A non-UTC moment must move, not have its offset painted over."""
    from datetime import timedelta, timezone

    at = datetime(2026, 8, 8, 10, 22, tzinfo=timezone(timedelta(hours=3)))
    assert stamp(at) == "2026-08-08T07:22:00.000Z"


@pytest.fixture
def pages(monkeypatch: pytest.MonkeyPatch):
    """Serve canned pages, and record the params each request carried."""
    asked: list[dict] = []

    def serve(responses):
        queue = list(responses)

        def fake_request(method, base, path, api_key, params=None, **kwargs):
            asked.append(params or {})
            return queue.pop(0)

        monkeypatch.setattr(unipile, "request", fake_request)
        return asked

    return serve


def _page(dates, cursor=None):
    return {"items": [{"id": d, "date": d} for d in dates], "cursor": cursor}


def test_paging_follows_the_cursor_and_returns_oldest_first(pages) -> None:
    """Unipile serves newest-first and will not sort; a watermark can only
    advance over a contiguous run, so the order is flipped on the way out."""
    asked = pages(
        [
            _page(["2026-08-05", "2026-08-04"], cursor="c1"),
            _page(["2026-08-03", "2026-08-02"], cursor="c2"),
            _page([], cursor=None),
        ]
    )

    messages, capped = iter_emails("https://api.test", "key", "a1", cap=100)

    assert [m["date"] for m in messages] == ["2026-08-02", "2026-08-03", "2026-08-04", "2026-08-05"]
    assert capped is False
    assert asked[1]["cursor"] == "c1"
    assert "cursor" not in asked[0]


def test_paging_stops_when_the_cursor_runs_out(pages) -> None:
    pages([_page(["2026-08-05"], cursor=None)])
    messages, capped = iter_emails("https://api.test", "key", "a1", cap=100)
    assert len(messages) == 1
    assert capped is False


def test_the_cap_stops_the_walk_and_says_so(pages) -> None:
    asked = pages([_page(["2026-08-05", "2026-08-04"], cursor="c1")])

    messages, capped = iter_emails("https://api.test", "key", "a1", cap=2)

    assert capped is True
    assert len(messages) == 2
    # Never asks for more than the cap leaves room for, nor more than the
    # API's own ceiling.
    assert asked[0]["limit"] == 2


def test_a_page_is_never_asked_for_more_than_the_api_ceiling(pages) -> None:
    asked = pages([_page([], cursor=None)])
    iter_emails("https://api.test", "key", "a1", cap=10_000)
    assert asked[0]["limit"] == unipile.MAX_PAGE


def test_filters_are_only_sent_when_set(pages) -> None:
    asked = pages([_page([], cursor=None)])
    iter_emails(
        "https://api.test",
        "key",
        "a1",
        after=datetime(2026, 8, 1, tzinfo=UTC),
        search="invoice OR receipt",
        cap=10,
    )
    sent = asked[0]
    assert sent["after"] == "2026-08-01T00:00:00.000Z"
    assert sent["search"] == "invoice OR receipt"
    assert sent["role"] == "inbox"
    assert "before" not in sent
