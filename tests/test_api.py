"""Route-level behaviour: status codes, validation, and how Unipile failures map.

None of these reach Postgres or Unipile. The credentials dependency is
overridden and the accounts module is patched, so what is under test is the
route contract rather than either backend.
"""

import pytest
from fastapi.testclient import TestClient

from backend import __version__, accounts, invoices
from backend.services.api import api
from backend.unipile import UnipileError, credentials


@pytest.fixture
def connected(client: TestClient) -> TestClient:
    """A client whose Unipile credentials resolve, without reading the environment."""
    api.dependency_overrides[credentials] = lambda: ("https://api.example.com", "key")
    yield client
    api.dependency_overrides.clear()


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


def test_scan_rejects_a_limit_below_one(client: TestClient) -> None:
    assert client.post("/scan", json={"limit": 0}).status_code == 422
