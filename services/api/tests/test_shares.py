"""The share flow: what a batch calls itself, what lands in the zip, and the
two dead ends a link can reach.

Nothing here touches Postgres. The rows are built in memory and `session_scope`
is replaced, so what is under test is the flow's own behaviour rather than
SQLAlchemy's — the same rule the rest of tests/test_api.py keeps.
"""

import csv
import io
import shutil
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from invoicepilot import app as api_module
from invoicepilot import invoice_store, invoices, share_mail, share_zip, shares
from invoicepilot.app import api
from invoicepilot.models import Share

OWNER_KEY = "the-key-the-browser-kept"


def a_share(**overrides) -> Share:
    now = datetime.now(UTC)
    fields = {
        "token": "7Kq2mXbN4vRt9wLpZaHc3f",
        "owner_key_hash": shares.key_hash(OWNER_KEY),
        "workspace_id": "test-workspace",
        "invoice_ids": [],
        "owner_name": "Martin Kirov",
        "owner_email": "martin@kirov.dev",
        "created_at": now,
        "expires_at": now + shares.TTL,
    }
    return Share(**{**fields, **overrides})


def an_item(invoice_id: str, issued_on: str | None, **invoice) -> dict:
    """One row as invoicepilot.invoices hands it out: the payload, plus its two columns."""
    return {"id": invoice_id, "issued_on": issued_on, "invoice": invoice}


@pytest.fixture
def items(corpus: list[dict]) -> list[dict]:
    """Real filed invoices, in the shape a share reads them in."""
    return [
        {
            "id": entry["id"],
            "issued_on": (entry["payload"].get("invoice") or {}).get("date"),
            **entry["payload"],
        }
        for entry in corpus
    ]


@pytest.fixture
def linked(monkeypatch: pytest.MonkeyPatch):
    """A client whose share routes resolve without a database.

    Returns a function taking the share the token resolves to and the invoices
    its snapshot covers.
    """

    @contextmanager
    def no_session():
        yield None

    monkeypatch.setattr(api_module, "session_scope", no_session)

    def use(share: Share | None, rows: list[dict] | None = None) -> TestClient:
        monkeypatch.setattr(shares, "get", lambda session, token: share)
        monkeypatch.setattr(invoices, "by_ids", lambda session, ws, ids: rows or [])
        return TestClient(api)

    return use


# ------------------------------------------------------------- the batch ----
def test_a_batch_names_itself_from_the_dates_in_it() -> None:
    """There is no title column, so the name has to come out of the invoices."""
    one_quarter = shares.summarise([an_item("a", "2026-04-01"), an_item("b", "2026-06-30")], {})
    assert one_quarter.filename == "invoices-2026-Q2.zip"
    assert one_quarter.label == "Q2"
    assert one_quarter.period == "Apr 1 - Jun 30, 2026"
    assert one_quarter.months == "Apr to Jun 2026"

    one_year = shares.summarise([an_item("a", "2026-02-01"), an_item("b", "2026-06-30")], {})
    assert one_year.filename == "invoices-2026.zip"
    assert one_year.label == "2026"

    two_years = shares.summarise([an_item("a", "2025-12-03"), an_item("b", "2026-06-30")], {})
    assert two_years.filename == "invoices-2025-2026.zip"
    assert two_years.period == "Dec 3, 2025 - Jun 30, 2026"


def test_an_undated_batch_still_has_a_name() -> None:
    """The parser does not always find a date, and a share of those still downloads."""
    summary = shares.summarise([an_item("a", None)], {})
    assert summary.filename == "invoices.zip"
    assert (summary.label, summary.period, summary.months) == ("", "", "")
    assert summary.invoices == 1


def test_the_counts_separate_invoices_from_documents(items: list[dict], corpus_root) -> None:
    """An invoice read out of an email body has no file; it is still in the batch."""
    entries = shares.documents(items, corpus_root)
    summary = shares.summarise(items, entries)
    assert summary.invoices == len(items)
    assert summary.documents == len(entries) <= summary.invoices
    assert summary.bytes == sum(entry.bytes for entry in entries.values())


def test_two_invoices_that_agree_on_a_name_both_survive_the_zip(
    with_pdf: dict, corpus_root
) -> None:
    """A zip with the same entry name twice quietly loses one of them."""
    payload = with_pdf["payload"]
    twins = [
        {"id": "2026-08-03__bolt__1-63eur__aaaaaa", "issued_on": None, **payload},
        {"id": "2026-08-03__bolt__1-63eur__bbbbbb", "issued_on": None, **payload},
    ]
    names = [entry.name for entry in shares.documents(twins, corpus_root).values()]
    assert names[0] == "2026-08-03__bolt__1-63eur.pdf"
    assert len(set(names)) == 2, names


# --------------------------------------------------------------- the zip ----
def test_the_zip_carries_every_document_and_one_csv(items: list[dict], corpus_root) -> None:
    entries = shares.documents(items, corpus_root)
    snapshot = shares.Snapshot(a_share(), items, entries, shares.summarise(items, entries))

    blob = b"".join(share_zip.stream(snapshot))
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert names[0] == share_zip.CSV_NAME
        assert sorted(names[1:]) == sorted(entry.name for entry in entries.values())

        rows = list(
            csv.DictReader(io.StringIO(archive.read(share_zip.CSV_NAME).decode("utf-8-sig")))
        )

    assert len(rows) == len(items)
    assert list(rows[0]) == list(share_zip.CSV_COLUMNS)
    # Every column the sheet on the page cannot show is why the CSV exists.
    assert any(row["email_message_id"] for row in rows)


def test_the_zip_is_written_as_it_is_read(items: list[dict], corpus_root) -> None:
    """Nothing assembles the batch in memory, so the first bytes arrive early."""
    entries = shares.documents(items, corpus_root)
    snapshot = shares.Snapshot(a_share(), items, entries, shares.summarise(items, entries))

    chunks = [chunk for chunk in share_zip.stream(snapshot) if chunk]
    assert len(chunks) > 1


# -------------------------------------------------------------- the mail ----
def test_the_mail_names_the_owner_the_batch_and_the_day_it_stops() -> None:
    share = a_share(expires_at=datetime(2026, 7, 12, tzinfo=UTC))
    items = [an_item("a", "2026-04-01"), an_item("b", "2026-06-30")]
    entries: dict[str, shares.Entry] = {}
    snapshot = shares.Snapshot(share, items, entries, shares.summarise(items, entries))

    mail = share_mail.draft(snapshot, "https://invoicepilot.app/s/abc")

    assert mail.subject == "Invoices, Apr to Jun 2026 (2 invoices)"
    assert "Martin shared Q2 invoices with you" in mail.html
    assert "invoices-2026-Q2.zip" in mail.html
    assert "expires on 12 July 2026" in mail.html
    assert 'href="https://invoicepilot.app/s/abc"' in mail.html


def test_a_corrected_name_cannot_carry_markup_into_the_mail() -> None:
    """owner_name is the one column a person can rewrite, and it lands in HTML."""
    snapshot = shares.Snapshot(
        a_share(owner_name="<script>alert(1)</script>"), [], {}, shares.summarise([], {})
    )
    html = share_mail.draft(snapshot, "https://invoicepilot.app/s/abc").html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# ------------------------------------------------------------ the routes ----
def test_a_link_that_never_existed_is_a_404(linked) -> None:
    assert linked(None).get("/s/nothing").status_code == 404


def test_an_expired_link_is_a_410_that_still_names_who_sent_it(linked) -> None:
    """The two dead ends are different: this one worked, so it may be asked for again."""
    lapsed = a_share(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    response = linked(lapsed).get(f"/s/{lapsed.token}")

    assert response.status_code == 410
    assert response.json()["detail"] == {
        "message": "This link has expired.",
        "owner_name": "Martin Kirov",
        "owner_email": "martin@kirov.dev",
        "created_at": lapsed.created_at.isoformat(),
        "expires_at": lapsed.expires_at.isoformat(),
    }


def test_the_manifest_tells_the_recipient_nothing_about_the_mailbox(
    linked, items: list[dict]
) -> None:
    """The share page is public; the stored payload is not."""
    share = a_share(invoice_ids=[item["id"] for item in items])
    body = linked(share, items).get(f"/s/{share.token}").json()

    assert body["items"] and len(body["items"]) == len(items)
    assert set(body["items"][0]) == {
        "id",
        "vendor",
        "invoice_number",
        "file",
        "issued_on",
        "currency",
        "amount_net",
        "amount_vat",
        "amount_total",
    }
    assert "kiraesq124@gmail.com" not in str(body["items"])


def test_only_the_browser_that_made_a_link_may_rename_it(linked) -> None:
    """Without this, anyone holding the link could rewrite who it says shared it."""
    share = a_share()
    client = linked(share)

    refused = client.patch(
        f"/s/{share.token}", json={"owner_name": "Someone Else", "owner_key": "guess"}
    )
    assert refused.status_code == 403
    assert share.owner_name == "Martin Kirov"

    allowed = client.patch(
        f"/s/{share.token}", json={"owner_name": "  Martin  ", "owner_key": OWNER_KEY}
    )
    assert allowed.status_code == 204
    assert share.owner_name == "Martin"


def test_a_thumbnail_is_bounded_by_the_share_that_asks_for_it(linked) -> None:
    """A token grants its own snapshot, so an id out of another share is a 404."""
    share = a_share(invoice_ids=["mine"])
    assert linked(share).get(f"/s/{share.token}/thumb/somebody-elses").status_code == 404


def test_a_thumbnail_is_rendered_once_beside_the_document(with_pdf: dict, tmp_path: Path) -> None:
    """Rendered on first request rather than at extraction, so nothing is backfilled."""
    payload = with_pdf["payload"]
    folder = tmp_path / payload["email"]["mailbox"] / with_pdf["dir"].name
    folder.parent.mkdir(parents=True)
    shutil.copytree(with_pdf["dir"], folder)

    thumb = invoice_store.thumbnail(payload, root=tmp_path)
    assert thumb == folder / invoice_store.THUMB_NAME
    assert Image.open(thumb).width == invoice_store.THUMB_WIDTH

    written = thumb.stat().st_mtime_ns
    assert invoice_store.thumbnail(payload, root=tmp_path) == thumb
    assert thumb.stat().st_mtime_ns == written, "a second read re-rendered the image"


def test_an_invoice_with_no_document_has_no_thumbnail(tmp_path: Path) -> None:
    """Some invoices were read out of an email body. That is a real case, not an error."""
    assert invoice_store.thumbnail({"invoice": {}, "email": {}}, root=tmp_path) is None
