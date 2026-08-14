"""Annotate the share-flow screens with the backend that powers them:
`python3 docs/flows/share-flow-v3-light-annotated/annotate.py`

This folder does not own a single line of the design. It reads the screens out
of ../share-flow-v3-light/, marks the elements that a request puts data into,
and writes the marked copies here beside a legend naming the endpoint, the
table and the query behind each one. Re-run it whenever that folder's build.py
runs; the two stay in step because this one never copies markup it could have
read.

Three things follow from that, and they are the whole design of this file:

  · **The screens are read, not regenerated.** ../share-flow-v3-light/build.py
    is the only generator of this markup. Forking it to add annotations would
    give the two copies somewhere to drift, which is the thing that generator
    exists to prevent.
  · **The stylesheets are linked, not copied.** The three sheets stay where
    they are and the annotated screens point back at them, so an annotated
    screen renders exactly what the design folder renders. `annotations.css`
    is the only sheet this folder owns and it adds only the pins and the
    panel.
  · **An anchor that stops matching is a hard failure.** Every pin names a
    substring of the real markup. If build.py changes an element out from
    under a pin, this script stops with the anchor that no longer matches
    rather than quietly writing a screen with a missing annotation — a wiring
    map that is silently 80% complete is worse than one that refuses to build.

What the wiring describes is the design in ../share-flow-v3-light/design.md
and the data model in ../draft/share-flow/design.md, amended by the decision in
../share-flow-v3-light/notes.md: revoke is replaced by a 7-day TTL, so the
table carries `expires_at` and there is no DELETE route. The screens still draw
revoke, because they were drawn before that decision; pin 8 on 03-preview.html
and the whole of 09-revoked.html say so rather than pretending otherwise.

Queries are written as the SQL the SQLAlchemy in backend/ emits, not as ORM
calls, because the question this folder answers is what the database is asked
to do. The four endpoints that ship today were read off backend/services/api.py
and backend/invoices.py; the six new ones are the plan.
"""

import html
import shutil
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).parent
SRC = HERE.parent / "share-flow-v3-light"

# The three sheets stay in the design folder. Same depth, so the two links into
# frontend/src/styles/ that every screen carries need no rewriting at all.
SHEETS = ("tokens-v3.css", "reskin.css", "flow.css")


# ------------------------------------------------------------- endpoints ----
class Endpoint(NamedTuple):
    """One route, defined once and pinned from as many screens as use it."""

    method: str
    path: str
    # (table, is_new). Empty when the route touches no table at all, which is
    # itself worth saying: three of these are pure Unipile or pure disk.
    tables: tuple[tuple[str, bool], ...]
    sql: str
    note: str
    # False for the four routes backend/services/api.py already serves.
    is_new: bool = True


NO_TABLE: tuple[tuple[str, bool], ...] = ()

ENDPOINTS: dict[str, Endpoint] = {
    # ---- what ships today, read off backend/services/api.py ----------------
    "accounts": Endpoint(
        "GET",
        "/api/accounts",
        NO_TABLE,
        "-- no query: Unipile holds the mailboxes, not us\n"
        "GET {unipile_dsn}/api/v1/accounts",
        "Ships today. The dashboard's sources card and the composer's From row "
        "are the same call; neither reads a row from Postgres.",
        is_new=False,
    ),
    "scan": Endpoint(
        "POST",
        "/api/scan  ->  GET /api/scan/{job_id}",
        (("invoices", False),),
        "INSERT INTO invoices (id, issued_on, data)\n"
        "VALUES ($1, $2, $3::jsonb)\n"
        "ON CONFLICT (id) DO UPDATE\n"
        "   SET issued_on = EXCLUDED.issued_on, data = EXCLUDED.data\n"
        "RETURNING xmax = 0 AS inserted;",
        "Ships today. 202 with a job id, then the client polls. The upsert is "
        "what makes a re-scan idempotent, and `xmax = 0` is how the job "
        "separates new invoices from ones it had already filed.",
        is_new=False,
    ),
    "invoices": Endpoint(
        "GET",
        "/api/invoices?limit=&offset=",
        (("invoices", False),),
        "SELECT id, issued_on, data FROM invoices\n"
        "ORDER BY issued_on DESC NULLS LAST, id\n"
        "LIMIT $1 OFFSET $2;\n"
        "\n"
        "SELECT count(*) FROM invoices;",
        "Ships today. One page plus the total, which is the only reason the "
        "second query exists. NULLS LAST is why an undated invoice does not "
        "lead the table.",
        is_new=False,
    ),
    "document": Endpoint(
        "GET",
        "/api/invoices/{invoice_id}/document",
        (("invoices", False),),
        "SELECT data FROM invoices WHERE id = $1;",
        "Ships today. The file path is built from the row's own payload, never "
        "from the id in the URL, and the resolved path is checked to be inside "
        ".data/ before it is served. 404 when the invoice has no document, "
        "which is a real case rather than an error.",
        is_new=False,
    ),
    # ---- the share flow ----------------------------------------------------
    "share_create": Endpoint(
        "POST",
        "/api/shares  {invoice_ids?}",
        (("shares", True), ("invoices", False)),
        "-- only when the caller sent no ids: snapshot the whole view\n"
        "SELECT id FROM invoices ORDER BY issued_on DESC NULLS LAST, id;\n"
        "\n"
        "INSERT INTO shares\n"
        "  (token, owner_key_hash, invoice_ids, created_at, expires_at)\n"
        "VALUES ($1, $2, $3::jsonb, now(), now() + interval '7 days');",
        "The only write the flow makes. `invoice_ids` is a JSONB snapshot and "
        "is never updated: a later scan must not widen a link that has already "
        "been sent. Returns {token, url, owner_key, expires_at}, and the owner "
        "key is returned exactly once - only its sha256 is stored.",
    ),
    "manifest": Endpoint(
        "GET",
        "/api/s/{token}",
        (("shares", True), ("invoices", False)),
        "SELECT token, invoice_ids, created_at, expires_at\n"
        "FROM shares WHERE token = $1;     -- primary key, no index needed\n"
        "\n"
        "SELECT id, issued_on, data FROM invoices\n"
        "WHERE id = ANY($1::text[])\n"
        "ORDER BY issued_on DESC NULLS LAST, id;",
        "Two queries, and the first one deliberately does not filter on "
        "expires_at. `WHERE expires_at > now()` would fold an expired share "
        "into a missing one and cost the page the difference between 410 and "
        "404 - which is the difference between the two dead-end screens. The "
        "row is fetched, then the expiry is compared.",
    ),
    "thumb": Endpoint(
        "GET",
        "/api/s/{token}/thumb/{invoice_id}",
        (("shares", True), ("invoices", False)),
        "SELECT invoice_ids, expires_at FROM shares WHERE token = $1;\n"
        "-- the id must appear in that snapshot, or 404\n"
        "SELECT data FROM invoices WHERE id = $1;",
        "The membership check is the access control: a token grants exactly "
        "its own snapshot, so guessing an id out of another share buys "
        "nothing. The image itself is not in Postgres - it is thumb.webp "
        "beside the PDF, rendered at extraction, rendered on first request "
        "when it is missing so no backfill is needed.",
    ),
    "zip": Endpoint(
        "GET",
        "/api/s/{token}/zip",
        (("shares", True), ("invoices", False)),
        "-- the same two queries as the manifest\n"
        "SELECT token, invoice_ids, expires_at FROM shares WHERE token = $1;\n"
        "\n"
        "SELECT id, issued_on, data FROM invoices\n"
        "WHERE id = ANY($1::text[])\n"
        "ORDER BY issued_on DESC NULLS LAST, id;",
        "No parameters: the link is the batch. The rows give the entry names "
        "and build invoices.csv; the PDFs are streamed off disk and never "
        "assembled in memory, so the profile does not depend on the batch.",
    ),
    "email_preview": Endpoint(
        "GET",
        "/api/s/{token}/email/preview",
        (("shares", True), ("invoices", False)),
        "-- the manifest queries again, for the summary the mail quotes\n"
        "SELECT token, invoice_ids, expires_at FROM shares WHERE token = $1;\n"
        "\n"
        "SELECT id, issued_on, data FROM invoices\n"
        "WHERE id = ANY($1::text[])\n"
        "ORDER BY issued_on DESC NULLS LAST, id;",
        "Serves the rendered mail as a document, for the composer's iframe to "
        "load. It exists so the preview is the bytes the send will use rather "
        "than a second template that can drift from it.",
    ),
    "email_send": Endpoint(
        "POST",
        "/api/s/{token}/email  {to, from_account_id, owner_key}",
        (("shares", True),),
        "SELECT owner_key_hash, invoice_ids, expires_at\n"
        "FROM shares WHERE token = $1;\n"
        "-- compare_digest(sha256(owner_key), owner_key_hash)\n"
        "-- then Unipile: POST {unipile_dsn}/api/v1/emails\n"
        "-- no write: nothing records that a share was mailed",
        "The one route the owner key gates. `from_account_id` arrives from the "
        "browser, so it is checked against /api/accounts on the way through - "
        "the only thing that may send as a mailbox is that mailbox's owner. "
        "backend/unipile.py has no send function yet; this is the one call it "
        "is missing.",
    ),
}


# ------------------------------------------------------------------ pins ----
class Pin(NamedTuple):
    """One UI element, and what fills it.

    `anchor` is a substring of the element's opening tag as build.py emits it.
    The attribute is inserted before that tag's `>`, so an anchor may stop
    short of the end of the tag and may span lines.
    """

    anchor: str
    element: str
    # A key into ENDPOINTS, or None for an element no request reaches.
    endpoint: str | None
    note: str = ""
    # An open question about the backend rather than a description of it.
    gap: str = ""
    # Which occurrence of `anchor` to mark, when the markup repeats it.
    nth: int = 1


# What the popover, the rail and the manifest all quote - said once here
# because three screens pin it.
DERIVED = (
    "Derived from the snapshot at read time, not stored: there is no title "
    "column and nothing that can drift from the rows it describes."
)

SCREENS: dict[str, tuple[str, str, tuple[Pin, ...]]] = {
    # ------------------------------------------------------------ dashboard -
    "01-idle.html": (
        "The Share button",
        "The dashboard as it ships, plus the one control the flow adds. "
        "Everything pinned here is already served.",
        (
            Pin(
                '<section class="card sources"',
                "Email sources card",
                "accounts",
                "Mailboxes come from Unipile, so this card survives a wiped "
                "database. The count under it is the length of that response.",
            ),
            Pin(
                '<h1 class="table-title">',
                "Invoices / 37 documents",
                "invoices",
                "The heading's figure is `total`, which is the second query - "
                "the page of rows below cannot answer how many there are.",
            ),
            Pin(
                '<button class="update-btn"',
                "Update",
                "scan",
                "The only control on this screen that writes anything.",
            ),
            Pin(
                "<table>",
                "The invoice table",
                "invoices",
                "One row per item in the page. Vendor, amount and issued date "
                "are read out of the `data` JSONB, not out of columns.",
            ),
            Pin(
                '<th class="col-check">',
                "The checkbox column",
                None,
                "No request. This is where the batch is chosen: the checked "
                "ids become `invoice_ids` in the POST the Share button makes, "
                "and an empty selection means the whole view.",
            ),
            Pin(
                '<button class="share-btn"',
                "Share",
                "share_create",
                "The click is the share - there is no dialog to open first, so "
                "this button is the request. See 02-link.html for what comes "
                "back.",
            ),
            Pin(
                '<div class="table-foot">',
                "10 of 37 shown",
                "invoices",
                "`limit` and `offset`. Worth knowing for the share: what gets "
                "snapshotted when nothing is checked is every invoice, not the "
                "10 on this page.",
            ),
        ),
    ),
    "01b-row.html": (
        "The row, opened",
        "A branch off the flow rather than a step through it. It is here "
        "because it costs one endpoint that already exists.",
        (
            Pin(
                '<tr class="expansion"',
                "The opened panel",
                None,
                "No request. Every field here was already in the row's `data` "
                "payload from GET /api/invoices - the table renders four of "
                "them and the panel renders the rest. Opening a row is free.",
            ),
            Pin(
                '<figure class="exp-doc"',
                "The document thumbnail",
                "document",
                "The one thing on this panel that costs a request. In the "
                "draft it renders the state where no page has arrived; in "
                "production the invoice's own PDF goes in that box.",
            ),
            Pin(
                '<div class="meta"',
                "The field list",
                None,
                "No request. Fields the extractor came back empty on are not "
                "rendered at all, so what this list proves is which keys the "
                "`data` JSONB actually carries for this issuer.",
            ),
        ),
    ),
    "02-link.html": (
        "Link created",
        "The one screen where the new table is written. Everything in the "
        "popover is the response body.",
        (
            Pin(
                '<button class="share-btn is-active"',
                "Share, mid-click",
                "share_create",
                "One POST. The link is minted and on the clipboard before the "
                "popover renders, which is why the popover reports rather than "
                "asks.",
            ),
            Pin(
                '<p class="pop-title">',
                "Link copied",
                None,
                "No request. The clipboard write is client-side; the tick "
                "reports that it succeeded, not that the server answered.",
            ),
            Pin(
                '<p class="pop-sub">',
                "All 37 invoices, Apr 1 - Jun 30, 2026",
                "share_create",
                "The count is the length of `invoice_ids`; the period is the "
                "min and max issued date across the snapshot. " + DERIVED,
            ),
            Pin(
                '<div class="link-row">',
                "The link",
                "share_create",
                "`url` from the response: the token joined to PUBLIC_BASE_URL, "
                "which is a setting the backend does not have yet. It cannot "
                "be built from the request host - the API is behind nginx and "
                "answers on /api.",
            ),
            Pin(
                '<a class="btn btn-primary btn-grow"',
                "Open the link",
                None,
                "No request. Navigation to /s/{token}, which is a page, not an "
                "API route - the manifest it then fetches is /api/s/{token}.",
            ),
            Pin(
                '<a class="btn-quiet" href="04-compose.html"',
                "Send by email",
                None,
                "No request yet. It opens the composer, which needs the "
                "`owner_key` from this response - held in localStorage so the "
                "owner never sees or types it.",
            ),
        ),
    ),
    # ----------------------------------------------------------- share page -
    "03-preview.html": (
        "The share page",
        "The owner's view of the recipient's page. One manifest call fills "
        "almost all of it.",
        (
            Pin(
                '<p class="shared-by">',
                "Your link / martin@kirov.dev",
                "manifest",
                "",
                gap="Nothing answers this. `shares` as specified carries no "
                "owner: not a name, not an address. The recipient's copy of "
                "this line (07-recipient.html) reads 'Shared with you by "
                "Martin Kirov', which needs an identity the table does not "
                "hold. Either the manifest derives it from the mailbox on the "
                "snapshot's invoices, or `shares` gains a column.",
            ),
            Pin(
                '<h1 class="batch-name"',
                "invoices-2026-Q2.zip",
                "manifest",
                "The filename is built from the date range of the snapshot. "
                + DERIVED,
            ),
            Pin(
                '<dl class="facts">',
                "Invoices / Documents / Size / Period",
                "manifest",
                "All four are computed off the snapshot: rows, rows with a "
                "document, the sum of `document.bytes`, and the min/max issued "
                "date. Size is the honest one to watch - it is the sum of the "
                "PDFs, and the zip that lands is a few KB larger for the CSV.",
            ),
            Pin(
                '<a class="btn btn-primary btn-lg"',
                "Download all",
                "zip",
                "An href, not a fetch: the browser streams it. Nothing on this "
                "page has to hold the batch in memory.",
            ),
            Pin(
                '<div class="doc-grid">',
                "The five tiles",
                "thumb",
                "Five requests, one per tile, and never more - the sixth cell "
                "is a count, not a document. No image on this page is lazy, "
                "because five is already the whole strip.",
            ),
            Pin(
                '<table class="sheet">',
                "The manifest",
                "manifest",
                "One row per id in the snapshot, from the second query. The "
                "Document column carries the zip's own entry name, which is "
                "what makes this a manifest rather than a second dashboard.",
            ),
            Pin(
                '<div class="owner-block"',
                "The owner block",
                None,
                "No request. This half of the page renders when the browser "
                "has an `owner_key` in localStorage for this token; the "
                "manifest is identical either way, so the server never decides "
                "who is looking.",
            ),
            Pin(
                '<a class="btn-quiet" href="09-revoked.html"',
                "Revoke",
                None,
                "",
                gap="This control is going. notes.md replaces revoke with a "
                "7-day TTL set at creation, so there is no DELETE /s/{token} "
                "in the plan and `shares` carries `expires_at` rather than "
                "`revoked_at`. The screens still draw it because they predate "
                "that decision.",
            ),
        ),
    ),
    "04-compose.html": (
        "Composer",
        "Two calls behind it, and one of them does not exist in any spec yet.",
        (
            Pin(
                '<span class="from-current">',
                "From",
                "accounts",
                "The address is stated rather than asked, so this is a read "
                "with no control attached. Defaults to the last mailbox this "
                "browser sent from, held in localStorage.",
            ),
            Pin(
                '<a class="icon-btn" href="05-from.html"',
                "The caret",
                "accounts",
                "Rendered only when the same response holds more than one "
                "account - the count decides whether this control exists.",
            ),
            Pin(
                '<input id="to"',
                "To",
                None,
                "No request. Validated in the browser on blur; the server's "
                "own rejection is a different screen (08-send-failed.html).",
            ),
            Pin(
                "<iframe src=",
                "The preview",
                "email_preview",
                "",
                gap="No route in any spec serves this. The design is explicit "
                "that the iframe must show the bytes the API is about to send "
                "rather than a mock-up - which means the mail has to be "
                "rendered server-side and fetched. Either a preview route "
                "exists, or the preview is a second template that can drift "
                "from the one that gets sent.",
            ),
            Pin(
                '<a class="btn btn-primary" href="06-sent.html"',
                "Send",
                "email_send",
                "Carries the address, the chosen account and the owner key. "
                "The share is already live - mail is the optional half of the "
                "flow.",
            ),
        ),
    ),
    "05-from.html": (
        "Choosing the mailbox",
        "A menu over data the composer already has.",
        (
            Pin(
                '<a class="from-opt is-current"',
                "The current mailbox",
                "accounts",
                "No second request: the menu is the same response the From row "
                "read. It keeps the current address in the list and ticks it, "
                "so it answers 'which am I on' as well as 'what else'.",
            ),
            Pin(
                '<a class="from-opt" href="04-compose.html"',
                "The other mailbox",
                None,
                "No request. Picking one writes it to localStorage and changes "
                "`from_account_id` on the send.",
            ),
        ),
    ),
    "06-sent.html": (
        "Sent",
        "What a 204 looks like.",
        (
            Pin(
                '<p class="banner"',
                "Sent to anna@ledger.co",
                "email_send",
                "Nothing was written. No table records that a share was "
                "mailed, so this banner is the only trace the send leaves - "
                "and the Undo beside it cannot be a server call for the same "
                "reason.",
            ),
            Pin(
                '<div class="owner-block"',
                "The owner block, unchanged",
                None,
                "No request. Sending does not touch the share row, so nothing "
                "on the rest of the page needs to be refetched.",
            ),
        ),
    ),
    "07-recipient.html": (
        "Recipient's view",
        "The same manifest call as the owner's page. The difference is "
        "entirely in the browser.",
        (
            Pin(
                '<p class="shared-by">',
                "Shared with you by Martin Kirov",
                "manifest",
                "",
                gap="The same gap as 03-preview.html, and this is the screen "
                "that makes it a real one: a name and an address, for a "
                "recipient who has no account and cannot be shown anything the "
                "manifest does not carry.",
            ),
            Pin(
                '<table class="sheet">',
                "The manifest",
                "manifest",
                "Byte for byte the response the owner gets. There is no "
                "recipient mode on the server: no owner block renders here "
                "because this browser holds no owner key, which is a client "
                "decision.",
            ),
            Pin(
                '<a class="btn btn-primary btn-lg"',
                "Download all",
                "zip",
                "The whole point of the page, and the only thing on it that "
                "the recipient is expected to click.",
            ),
        ),
    ),
    "08-send-failed.html": (
        "Send failed",
        "A 502 with the transport's own words kept intact.",
        (
            Pin(
                '<p class="mail-error"',
                "The error",
                "email_send",
                "The Unipile detail is shown verbatim because 'something went "
                "wrong' is not something anyone can act on. backend/unipile.py "
                "already surfaces the API's error body rather than swallowing "
                "it, so the string exists; the route has to pass it through "
                "rather than replace it.",
            ),
            Pin(
                '<input id="to"',
                "To, still filled in",
                None,
                "No request. The address survives the failure - the composer "
                "stays open rather than resetting.",
            ),
        ),
    ),
    "09-revoked.html": (
        "Revoked",
        "The screen the TTL decision rewrites.",
        (
            Pin(
                '<section class="dead"',
                "This link was turned off",
                "manifest",
                "",
                gap="As drawn this is the response to a revoked share. Under "
                "the TTL decision there is no revoke: the same screen becomes "
                "*expired*, served as 410 when `expires_at` has passed. That "
                "is why the manifest query does not filter on expiry - a "
                "filtered query could only answer 404 here, and 404 is the "
                "other screen.",
            ),
            Pin(
                '<div class="dead-actions"',
                "Ask for a new link",
                None,
                "No request. There is nothing to retry: the state is settled "
                "and the page says so rather than offering a button that "
                "cannot work.",
            ),
        ),
    ),
    "10-loading.html": (
        "Loading",
        "One request in flight, and the page shaped like its answer.",
        (
            Pin(
                '<span class="skel skel-name"',
                "The filename, pending",
                "manifest",
                "The manifest is one call for up to several hundred rows, so "
                "this is the only wait the page has. The band's real headings "
                "stay visible - the page's identity is known from the URL "
                "before its contents arrive.",
            ),
            Pin(
                '<div class="skel-sheet"',
                "The manifest, pending",
                "manifest",
                "Same request. The placeholder is shaped like the sheet so "
                "nothing moves when the rows land, and `aria-busy` is on the "
                "regions being filled.",
            ),
            Pin(
                '<div class="skel skel-thumb"',
                "The tiles, pending",
                "thumb",
                "The five thumbnail requests cannot start until the manifest "
                "names which invoices they are for, so this is the second "
                "round trip, not the first.",
            ),
        ),
    ),
    "11-zipping.html": (
        "Preparing the download",
        "The only screen that watches a stream.",
        (
            Pin(
                '<div class="bar"',
                "The progress bar",
                "zip",
                "Determinate, and that is a property of the manifest rather "
                "than of the stream: the total is known from the rows already "
                "on the page, so the bar does not need the server to report "
                "progress it never sends.",
            ),
            Pin(
                '<table class="sheet">',
                "The manifest, still readable",
                None,
                "No request. The zip is a download, not a mode - nothing is "
                "refetched while it builds.",
            ),
        ),
    ),
    "12-invalid.html": (
        "Address needs fixing",
        "The one screen in the flow that costs the backend nothing at all.",
        (
            Pin(
                '<input id="to"',
                "To, invalid",
                None,
                "No request. Checked in the browser on blur, before "
                "POST /api/s/{token}/email is called - `aria-invalid` and "
                "`aria-describedby` on the input, Send `aria-disabled` while "
                "it stands.",
            ),
            Pin(
                '<p class="field-error"',
                "The message",
                None,
                "No request. This is the cheap half that saves a round trip, "
                "not a substitute for the transport's own rejection, which is "
                "08-send-failed.html.",
            ),
        ),
    ),
    "13-not-found.html": (
        "Nothing at this link",
        "The 404, and why it has to be a different screen from the 410.",
        (
            Pin(
                '<section class="dead"',
                "Nothing at this link",
                "manifest",
                "The first query returned no row: this token was never minted. "
                "Telling it apart from an expired one is the difference "
                "between 'check what you pasted' and 'ask for a new link', "
                "which is why the expiry is compared in the route rather than "
                "filtered in the query.",
            ),
            Pin(
                '<div class="dead-actions"',
                "Try again",
                None,
                "No request. The likeliest cause is a token broken across two "
                "lines by a mail client, so the page names that rather than "
                "retrying anything.",
            ),
        ),
    ),
}


# ------------------------------------------------------------------ build ---
def mark(source: str, pins: tuple[Pin, ...], screen: str) -> str:
    """Add `data-pin` to each anchored tag, or raise naming the one that moved.

    The attribute goes in before the tag's own `>`, which is found by scanning
    forward from the anchor - so an anchor can stop anywhere inside the opening
    tag and the tag itself may span lines, as several in build.py's output do.
    """
    for number, pin in enumerate(pins, start=1):
        cursor = -1
        for _ in range(pin.nth):
            cursor = source.find(pin.anchor, cursor + 1)
            if cursor < 0:
                raise SystemExit(
                    f"{screen}: no match {pin.nth} for {pin.anchor!r}.\n"
                    f"  The element for pin {number} ({pin.element}) moved. "
                    f"Re-read it in ../share-flow-v3-light/{screen} and fix "
                    f"the anchor in SCREENS."
                )
        close = source.find(">", cursor)
        if close < 0:
            raise SystemExit(f"{screen}: unterminated tag at {pin.anchor!r}")
        # build.py closes void elements as `/>`, so the attribute goes before
        # the slash. Appending after it yields `value="x"/ data-pin="3">`,
        # which browsers forgive and nothing else does.
        if source[close - 1] == "/":
            close -= 1
        source = f'{source[:close]} data-pin="{number}"{source[close:]}'
    return source


def chips(tables: tuple[tuple[str, bool], ...]) -> str:
    """The table names for one route, as chips. `shares` is marked new."""
    if not tables:
        return '<span class="wiring-table">no table</span>'
    out = []
    for name, is_new in tables:
        cls = ' class="wiring-table is-new"' if is_new else ' class="wiring-table"'
        out.append(f"<span{cls}>{name}{' · new' if is_new else ''}</span>")
    return "".join(out)


def legend(title: str, lede: str, pins: tuple[Pin, ...]) -> str:
    """The docked panel: one entry per pin, in the order they are numbered."""
    items = []
    for number, pin in enumerate(pins, start=1):
        parts = [
            f'<p class="wiring-el"><span class="wiring-n">{number}</span>'
            f"<span>{html.escape(pin.element)}</span></p>"
        ]
        if pin.endpoint:
            route = ENDPOINTS[pin.endpoint]
            parts.append(
                f'<p class="wiring-call"><b>{route.method}</b> '
                f"{html.escape(route.path)}</p>"
            )
            parts.append(f'<p class="wiring-tables">{chips(route.tables)}</p>')
            parts.append(f'<pre class="wiring-sql">{html.escape(route.sql)}</pre>')
            parts.append(f'<p class="wiring-note">{html.escape(route.note)}</p>')
        else:
            parts.append('<p class="wiring-none">no request</p>')
        if pin.note:
            parts.append(f'<p class="wiring-note">{html.escape(pin.note)}</p>')
        if pin.gap:
            parts.append(
                f'<p class="wiring-gap"><b>Open question.</b> '
                f"{html.escape(pin.gap)}</p>"
            )
        items.append(f'<li class="wiring-item">{"".join(parts)}</li>')

    return f"""<aside class="wiring" aria-label="Backend wiring">
  <div class="wiring-head">
    <p class="wiring-kicker">wiring</p>
    <h2 class="wiring-title">{html.escape(title)}</h2>
    <p class="wiring-lede">{html.escape(lede)}</p>
  </div>
  <ol class="wiring-list">
    {"".join(items)}
  </ol>
  <p class="wiring-foot">Generated by annotate.py from the screens in
    <a href="../share-flow-v3-light/index.html">share-flow-v3-light</a>.
    The full map is in <a href="index.html">index.html</a>.</p>
</aside>
"""


def annotate(screen: str, title: str, lede: str, pins: tuple[Pin, ...]) -> str:
    source = (SRC / screen).read_text(encoding="utf-8")

    # Point the three sheets back at the folder that owns them, and add the
    # only one this folder owns. Order matters: annotations.css must win.
    for sheet in SHEETS:
        needle = f'<link rel="stylesheet" href="{sheet}"/>'
        if needle not in source:
            raise SystemExit(f"{screen}: expected a link to {sheet}")
        source = source.replace(
            needle, f'<link rel="stylesheet" href="../share-flow-v3-light/{sheet}"/>'
        )
    source = source.replace(
        "</head>", '<link rel="stylesheet" href="annotations.css"/>\n</head>', 1
    )
    # So a tab holding the annotated screen is not mistaken for the real one.
    source = source.replace(" · Invoice Pilot</title>", " · wiring · Invoice Pilot</title>", 1)

    source = mark(source, pins, screen)
    return source.replace("</body>", f"{legend(title, lede, pins)}</body>", 1)


def index() -> str:
    """The contact sheet: every screen, then every endpoint, from one table."""
    cards = "".join(
        f'<li class="map-card"><a href="{name}">'
        f'<span class="map-file">{name}</span>'
        f"<span class=\"map-title\">{html.escape(SCREENS[name][0])}</span>"
        f'<span class="map-count">{len(SCREENS[name][2])} pins</span></a></li>'
        for name in SCREENS
    )

    # Which screens pin each route, so the table reads both ways.
    used: dict[str, list[str]] = {key: [] for key in ENDPOINTS}
    for name, (_, _, pins) in SCREENS.items():
        for pin in pins:
            if pin.endpoint and name not in used[pin.endpoint]:
                used[pin.endpoint].append(name)

    rows = []
    for key, route in ENDPOINTS.items():
        screens = "".join(
            f'<a href="{name}">{name.removesuffix(".html")}</a>' for name in used[key]
        )
        ships = "" if route.is_new else "<em>ships today</em>"
        rows.append(
            f"<tr><td><code>{route.method}</code></td>"
            f"<td><code>{html.escape(route.path)}</code>{ships}</td>"
            f'<td class="map-tables">{chips(route.tables)}</td>'
            f'<td class="map-screens">{screens}</td></tr>'
        )

    gaps = "".join(
        f"<li><b>{html.escape(pin.element)}</b> "
        f'<a href="{name}">{name}</a><p>{html.escape(pin.gap)}</p></li>'
        for name, (_, _, pins) in SCREENS.items()
        for pin in pins
        if pin.gap
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="light"/>
<title>Wiring map · Invoice Pilot</title>
<meta name="description" content="Every element of the share flow, and what powers it."/>
<link rel="stylesheet" href="../../../frontend/src/styles/tokens.css"/>
<link rel="stylesheet" href="../share-flow-v3-light/tokens-v3.css"/>
<link rel="stylesheet" href="annotations.css"/>
</head>
<body class="map-body">
<main class="map">
  <header class="map-head">
    <p class="wiring-kicker">annotated</p>
    <h1>Share flow, and what powers it</h1>
    <p class="map-lede">The screens from
      <a href="../share-flow-v3-light/index.html">share-flow-v3-light</a>, marked
      with the request that fills each element. Nothing here restyles the flow:
      the three stylesheets are linked out of that folder, and this one adds
      only the pins and the panel beside them. Regenerate with
      <code>python3 annotate.py</code>.</p>
  </header>

  <section class="map-part">
    <h2>The screens</h2>
    <ol class="map-grid">{cards}</ol>
  </section>

  <section class="map-part">
    <h2>The endpoints</h2>
    <p class="map-note">Four of these ship today. The six new ones are the
      plan; <code>shares</code> is the one new table, and every route that
      reads it looks the row up by primary key.</p>
    <table class="map-table">
      <thead><tr><th>Method</th><th>Path</th><th>Tables</th><th>Screens</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </section>

  <section class="map-part">
    <h2>What nothing answers yet</h2>
    <p class="map-note">Found while mapping the screens to routes: elements
      that render data no specified endpoint can return.</p>
    <ol class="map-gaps">{gaps}</ol>
  </section>
</main>
</body>
</html>
"""


def main() -> None:
    for screen, (title, lede, pins) in SCREENS.items():
        (HERE / screen).write_text(annotate(screen, title, lede, pins), encoding="utf-8")
        print(f"wrote {screen} ({len(pins)} pins)")

    # Copied rather than annotated: 04-compose.html loads it in an iframe, and
    # a docked panel inside that frame would annotate the preview instead of
    # the composer. The mail is covered in the panel on 04 instead.
    shutil.copyfile(SRC / "email.html", HERE / "email.html")
    print("copied email.html (unannotated: it renders inside the composer)")

    (HERE / "index.html").write_text(index(), encoding="utf-8")
    print("wrote index.html")


if __name__ == "__main__":
    main()
