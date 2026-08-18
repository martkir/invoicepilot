"""Route-level behaviour: status codes, validation, and how Unipile failures map.

None of these reach Postgres or Unipile. The credentials dependency is
overridden and the accounts module is patched, so what is under test is the
route contract rather than either backend.
"""

import threading
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from invoicepilot import __version__, accounts, invoices, scan_jobs
from invoicepilot.app import api
from invoicepilot.process import Progress, ScanResult
from invoicepilot.unipile import UnipileError, credentials


@pytest.fixture
def connected(client: TestClient) -> Iterator[TestClient]:
    """A client whose Unipile credentials resolve, without reading the environment."""
    api.dependency_overrides[credentials] = lambda: ("https://api.example.com", "key")
    yield client
    api.dependency_overrides.clear()


@pytest.fixture
def no_jobs() -> Iterator[None]:
    """Scan state is process-global; keep one test's jobs out of the next one's."""
    scan_jobs._JOBS.clear()
    yield
    scan_jobs._JOBS.clear()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_unreachable_unipile_is_a_bad_gateway(client: TestClient) -> None:
    """Including when it is our own configuration that is missing."""

    def missing() -> tuple[str, str]:
        raise UnipileError("UNIPILE_API_KEY / UNIPILE_DSN are not set.")

    api.dependency_overrides[credentials] = missing
    try:
        response = client.get("/accounts")
    finally:
        api.dependency_overrides.clear()

    assert response.status_code == 502
    assert "UNIPILE_API_KEY" in response.json()["detail"]


def test_disconnecting_an_unknown_account_is_a_404(
    connected: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 404 from Unipile means the mailbox is already gone, not that we are broken."""

    def gone(base: str, api_key: str, account_id: str) -> None:
        raise UnipileError("DELETE https://api.example.com/accounts/x -> HTTP 404: not found")

    monkeypatch.setattr(accounts, "disconnect", gone)
    assert connected.delete("/accounts/x").status_code == 404


def test_disconnect_reports_other_unipile_failures_as_502(
    connected: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(base: str, api_key: str, account_id: str) -> None:
        raise UnipileError("DELETE https://api.example.com/accounts/x -> HTTP 500: boom")

    monkeypatch.setattr(accounts, "disconnect", broken)
    assert connected.delete("/accounts/x").status_code == 502


@pytest.mark.parametrize(
    "query",
    [
        f"limit={invoices.MAX_PAGE + 1}",
        "limit=0",
        "limit=-1",
        "offset=-1",
    ],
)
def test_paging_out_of_range_is_rejected_before_the_database(
    client: TestClient, query: str
) -> None:
    """Postgres rejects a negative OFFSET with an error; the caller deserves a 422.

    These never open a session — if one of them regresses to reaching the
    database, this test fails by needing DATABASE_URL rather than by asserting.
    """
    assert client.get(f"/invoices?{query}").status_code == 422


def test_a_scan_reports_progress_and_refuses_a_second_one(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, no_jobs: None
) -> None:
    """Two scans would parse the same mail twice and race on the same folders."""
    reported = threading.Event()
    release = threading.Event()

    def blocking_scan(*, follow_links, on_progress=None, **options) -> ScanResult:
        on_progress(Progress("me@example.com", "March invoice", 3, 8, 1))
        reported.set()
        release.wait(timeout=5)
        return ScanResult(mailboxes=("me@example.com",), messages_scanned=8, invoices_found=1)

    monkeypatch.setattr(scan_jobs, "scan_all", blocking_scan)

    started = client.post("/scan")
    assert started.status_code == 202
    job_id = started.json()["id"]

    refused = client.post("/scan")
    assert refused.status_code == 409
    assert job_id in refused.json()["detail"]

    # Mid-scan the counts are the last report's, not zeros: that is what the
    # dashboard puts on screen instead of leaving the line frozen.
    assert reported.wait(timeout=5)
    running = client.get(f"/scan/{job_id}").json()
    assert running["status"] == "running"
    assert (running["messages_scanned"], running["invoices_found"]) == (3, 1)

    release.set()
    for _ in range(500):
        if scan_jobs.get(job_id).status != "running":
            break
        time.sleep(0.01)
    assert client.get(f"/scan/{job_id}").json() == {
        "id": job_id,
        "status": "done",
        "detail": None,
        "mailboxes": ["me@example.com"],
        "messages_scanned": 8,
        "invoices_found": 1,
        "invoices_new": 0,
        "errors": [],
    }


def test_a_finished_scan_does_not_block_the_next_one(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, no_jobs: None
) -> None:
    monkeypatch.setattr(
        scan_jobs, "scan_all", lambda **kwargs: ScanResult(mailboxes=("me@example.com",))
    )
    first = client.post("/scan")
    assert first.status_code == 202
    for _ in range(500):
        if scan_jobs.get(first.json()["id"]).status != "running":
            break
        time.sleep(0.01)
    assert client.post("/scan").status_code == 202
