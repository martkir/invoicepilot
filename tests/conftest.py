import json

import pytest
from fastapi.testclient import TestClient

from backend.invoice_store import DATA_ROOT
from backend.services.api import api


@pytest.fixture
def client() -> TestClient:
    return TestClient(api)


@pytest.fixture(scope="session")
def corpus() -> list[dict]:
    """Invoices filed by earlier real scans, as (payload, directory) pairs.

    These are the only end-to-end fixtures that exist: real vendor mail, with
    the exact bytes that were parsed kept beside the fields they produced. They
    replay with no network, so the extraction rules stay covered without
    reaching Unipile or any vendor.
    """
    found = []
    for path in sorted(DATA_ROOT.glob("*/*/invoice.json")):
        found.append(
            {
                "payload": json.loads(path.read_text(encoding="utf-8")),
                "dir": path.parent,
                "id": path.parent.name,
            }
        )
    if not found:
        pytest.skip(f"no invoice fixtures under {DATA_ROOT}")
    return found


@pytest.fixture(scope="session")
def with_pdf(corpus: list[dict]) -> dict:
    """A fixture whose vendor PDF was recovered, so document parsing is covered."""
    for item in corpus:
        if (item["dir"] / "invoice.pdf").is_file():
            return item
    pytest.skip("no fixture carries a vendor PDF")
