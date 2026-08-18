"""Workspace isolation — the reason the rest of this change exists.

These are the only tests in the suite that need a real Postgres, and they need
it on purpose. What is under test is that a query filters on a column and that
a key is composite; standing the database in with a dict would leave both
claims unproven, which is the one thing that must not happen here. They skip
when DATABASE_URL is unset, and CI provides one.

Each `TestClient` is a separate browser: httpx keeps a cookie jar per client,
so two of them get two workspaces exactly as two browsers would. Nothing here
overrides the workspace dependency — that is the code being tested.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from invoicepilot import invoices, shares, workspaces
from invoicepilot.app import api
from invoicepilot.core.db import session_scope
from invoicepilot.models import Invoice, MailboxScan
from invoicepilot.workspaces import COOKIE

pytestmark = pytest.mark.usefixtures("database")


def a_payload(issuer: str) -> dict:
    """The shape invoice_store writes and invoices.save stores."""
    return {
        "invoice": {"issuer": issuer, "amount": 12.5, "currency": "EUR", "date": "2026-08-03"},
        "email": {"mailbox": "someone@example.com", "message_id": "<m1@example.com>"},
    }


@pytest.fixture
def browser() -> Iterator[TestClient]:
    """A fresh browser: no cookie, and whatever workspace the API gives it."""
    with TestClient(api) as client:
        yield client


@pytest.fixture
def second_browser() -> Iterator[TestClient]:
    with TestClient(api) as client:
        yield client


def workspace_of(client: TestClient) -> str:
    """Make the client hit a scoped route, then read the id it was issued."""
    client.get("/invoices")
    return client.cookies[COOKIE]


# --- identity ---------------------------------------------------------------


def test_a_browser_is_given_one_workspace_and_keeps_it(browser: TestClient) -> None:
    """Same browser, same workspace — the whole promise of the cookie."""
    first = workspace_of(browser)
    assert first
    for _ in range(3):
        browser.get("/invoices")
    assert browser.cookies[COOKIE] == first


def test_two_browsers_are_two_workspaces(browser: TestClient, second_browser: TestClient) -> None:
    assert workspace_of(browser) != workspace_of(second_browser)


def test_the_cookie_is_not_readable_by_script(browser: TestClient) -> None:
    """httpOnly, so a cross-site script on the page cannot lift the credential."""
    browser.get("/invoices")
    header = next(
        value
        for key, value in browser.get("/invoices").request.headers.items()
        if key.lower() == "cookie"
    )
    assert COOKIE in header  # it is sent...
    set_cookie = TestClient(api).get("/invoices").headers["set-cookie"]
    assert "HttpOnly" in set_cookie  # ...but not exposed to JS
    assert "SameSite=lax" in set_cookie.replace("samesite", "SameSite")


def test_an_invented_cookie_is_replaced_rather_than_adopted(browser: TestClient) -> None:
    """A client must not get to choose its own workspace id.

    Adopting whatever arrived would let a caller pick a short, guessable id —
    and the id is the entire credential.
    """
    # Sent as a raw header rather than through the cookie jar: what matters is
    # what the server does with an id it does not recognise, and the jar's
    # domain matching only gets in the way of reading that.
    response = browser.get("/invoices", headers={"cookie": f"{COOKIE}=a"})

    issued = response.headers["set-cookie"]
    assert f"{COOKIE}=a;" not in issued
    assert issued.startswith(f"{COOKIE}=")
    assert len(issued.split(";")[0].split("=", 1)[1]) > 20


# --- what one workspace can see of another ----------------------------------


def test_invoices_do_not_cross_between_workspaces(
    browser: TestClient, second_browser: TestClient
) -> None:
    mine = workspace_of(browser)
    theirs = workspace_of(second_browser)

    with session_scope() as session:
        invoices.save(session, mine, "2026-08-03__acme__12-5eur__aaaaaa", a_payload("Acme"))

    assert browser.get("/invoices").json()["total"] == 1
    assert second_browser.get("/invoices").json()["total"] == 0
    assert theirs != mine


def test_another_workspaces_invoice_document_is_a_404(
    browser: TestClient, second_browser: TestClient
) -> None:
    """Not a 403: whether an id exists elsewhere is not a stranger's to learn."""
    mine = workspace_of(browser)
    workspace_of(second_browser)
    invoice_id = "2026-08-03__acme__12-5eur__bbbbbb"

    with session_scope() as session:
        invoices.save(session, mine, invoice_id, a_payload("Acme"))

    assert second_browser.get(f"/invoices/{invoice_id}/document").status_code == 404


def test_the_same_invoice_id_can_exist_in_two_workspaces(
    browser: TestClient, second_browser: TestClient
) -> None:
    """The id is derived from the mail, so this collision is certain, not rare.

    One person in two browsers scans one mailbox and both arrive at the same
    id. Under a single-column key the second scan would overwrite the first
    workspace's row; under the composite key they are two rows.
    """
    mine = workspace_of(browser)
    theirs = workspace_of(second_browser)
    invoice_id = "2026-08-03__acme__12-5eur__cccccc"

    with session_scope() as session:
        assert invoices.save(session, mine, invoice_id, a_payload("Acme")) is True
        assert invoices.save(session, theirs, invoice_id, a_payload("Acme")) is True

    assert browser.get("/invoices").json()["total"] == 1
    assert second_browser.get("/invoices").json()["total"] == 1

    with session_scope() as session:
        rows = session.query(Invoice).filter(Invoice.id == invoice_id).count()
    assert rows == 2


def test_a_watermark_is_per_workspace(browser: TestClient, second_browser: TestClient) -> None:
    """Two people holding one address have scanned it to their own depths.

    A shared mark would have the first scan tell the second there was nothing
    left to fetch.
    """
    from datetime import UTC, datetime

    from invoicepilot import mailboxes

    mine = workspace_of(browser)
    theirs = workspace_of(second_browser)
    at = datetime(2026, 8, 10, tzinfo=UTC)

    with session_scope() as session:
        mailboxes.set_watermark(session, mine, "shared@example.com", at)

    with session_scope() as session:
        assert mailboxes.watermark(session, mine, "shared@example.com") == at
        assert mailboxes.watermark(session, theirs, "shared@example.com") is None
        assert session.query(MailboxScan).count() == 1


# --- shares, which deliberately cross the boundary --------------------------


def test_a_share_resolves_for_a_recipient_who_is_not_the_owner(
    browser: TestClient, second_browser: TestClient
) -> None:
    """The case that breaks if the scope is read off the request.

    A recipient holds the link and nothing else — their own workspace is empty.
    Resolving the manifest against *their* cookie would hand back an empty
    batch, which is every share link ever sent quietly going blank.
    """
    mine = workspace_of(browser)
    workspace_of(second_browser)
    invoice_id = "2026-08-03__acme__12-5eur__dddddd"

    with session_scope() as session:
        invoices.save(session, mine, invoice_id, a_payload("Acme"))
        share, _ = shares.mint(
            session,
            workspace_id=mine,
            invoice_ids=[invoice_id],
            owner=("Martin", "martin@example.com"),
        )
        token = share.token

    body = second_browser.get(f"/s/{token}").json()
    assert body["invoices"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == invoice_id


def test_a_share_cannot_reach_outside_the_workspace_that_made_it(
    browser: TestClient, second_browser: TestClient
) -> None:
    """A snapshot naming somebody else's id resolves to nothing, not to their invoice."""
    mine = workspace_of(browser)
    theirs = workspace_of(second_browser)
    invoice_id = "2026-08-03__acme__12-5eur__eeeeee"

    with session_scope() as session:
        invoices.save(session, theirs, invoice_id, a_payload("Acme"))
        share, _ = shares.mint(
            session,
            workspace_id=mine,
            invoice_ids=[invoice_id],
            owner=("Martin", "martin@example.com"),
        )
        token = share.token

    assert browser.get(f"/s/{token}").json()["invoices"] == 0


# --- mailbox attribution ----------------------------------------------------


def test_the_connect_callback_files_the_account_against_the_right_workspace(
    browser: TestClient,
) -> None:
    mine = workspace_of(browser)
    with session_scope() as session:
        nonce = workspaces.start_connect(session, mine)

    assert (
        browser.post(f"/unipile/connected/{nonce}", json={"account_id": "acc-1"}).status_code == 204
    )

    with session_scope() as session:
        assert workspaces.account_ids(session, mine) == ["acc-1"]


def test_a_replayed_callback_claims_nothing(browser: TestClient) -> None:
    """Single use, so a repeated webhook cannot attach a second mailbox."""
    mine = workspace_of(browser)
    with session_scope() as session:
        nonce = workspaces.start_connect(session, mine)

    browser.post(f"/unipile/connected/{nonce}", json={"account_id": "acc-2"})
    browser.post(f"/unipile/connected/{nonce}", json={"account_id": "acc-3"})

    with session_scope() as session:
        assert workspaces.account_ids(session, mine) == ["acc-2"]


def test_an_unknown_nonce_is_accepted_and_ignored(browser: TestClient) -> None:
    """204 either way: Unipile retries a failure, and there is nothing to retry."""
    assert (
        browser.post("/unipile/connected/never-issued", json={"account_id": "x"}).status_code == 204
    )
