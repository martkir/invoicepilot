import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from invoicepilot.app import api, owned_accounts, workspace
from invoicepilot.invoice_store import DATA_ROOT

# The workspace every route-contract test runs as, and the mailboxes it owns.
# Fixed values, because those tests are about status codes and error mapping
# and would otherwise all need a database purely to be issued an identity.
TEST_WORKSPACE = "test-workspace"
TEST_ACCOUNTS = ["a1"]


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A client with an identity but no database behind it.

    Both workspace dependencies are overridden for the same reason
    `credentials` is: they reach a backend these tests deliberately do not
    have. Scoping itself is covered in test_workspaces.py, against a real
    database — overriding it there would make the test prove nothing.
    """
    api.dependency_overrides[workspace] = lambda: TEST_WORKSPACE
    api.dependency_overrides[owned_accounts] = lambda: TEST_ACCOUNTS
    yield TestClient(api)
    api.dependency_overrides.clear()


@pytest.fixture
def database() -> Iterator[None]:
    """A real Postgres, with the schema created. Skips when there is none.

    Only the isolation tests need this. Everything else in the suite runs with
    no backend at all, which is what keeps it fast and what lets CI run it
    without a service container.
    """
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("no DATABASE_URL — isolation tests need a real Postgres")

    from sqlalchemy import text

    from invoicepilot.core.db import get_engine
    from invoicepilot.models import Base

    engine = get_engine()
    Base.metadata.create_all(engine)

    # Emptied before each test, not after: a failing test then leaves its rows
    # behind to be looked at. CASCADE because the scoped tables carry a foreign
    # key to workspaces, and RESTART IDENTITY so counts start where they read.
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture(scope="session")
def corpus() -> list[dict]:
    """Invoices filed by earlier real scans, as (payload, directory) pairs.

    These are the only end-to-end fixtures that exist: real vendor mail, with
    the exact bytes that were parsed kept beside the fields they produced. They
    replay with no network, so the extraction rules stay covered without
    reaching Unipile or any vendor.

    Found by walking rather than at a fixed depth: documents gained a workspace
    level above the mailbox, and a checkout may hold either layout depending on
    whether the migration has run against it. What these fixtures are for —
    payload in, fields out — does not depend on where they sit.
    """
    found = []
    for path in sorted(DATA_ROOT.rglob("invoice.json")):
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
def corpus_root(corpus: list[dict]) -> Path:
    """The directory the fixtures' mailbox folders sit directly under.

    Derived from a fixture's own path rather than named, so it is right whether
    the checkout still holds the flat `<data>/<mailbox>/` layout or the
    `<data>/<workspace>/<mailbox>/` one the migration produces.
    """
    return corpus[0]["dir"].parent.parent


@pytest.fixture(scope="session")
def with_pdf(corpus: list[dict]) -> dict:
    """A fixture whose vendor PDF was recovered, so document parsing is covered."""
    for item in corpus:
        if (item["dir"] / "invoice.pdf").is_file():
            return item
    pytest.skip("no fixture carries a vendor PDF")
