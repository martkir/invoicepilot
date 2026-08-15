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
and the data model in ../draft/share-flow/design.md, amended twice by
../share-flow-v3-light/notes.md: revoke is replaced by a 7-day TTL, so the table
carries `expires_at` and there is no DELETE route, and a share carries the name
and address of the mailbox it was made from, so the recipient can be told who
shared with them.

Both amendments started here, as pins this file could not answer. A pin that
raised a question and had it settled keeps its entry and says so - `decided`
rather than `gap` - because where the question was is as much a part of the map
as the answer, and a map that quietly closed its own open questions would be
harder to trust than one that shows them being closed.

Queries are written as the SQL the SQLAlchemy in backend/ emits, not as ORM
calls, because the question this folder answers is what the database is asked
to do. The four endpoints that ship today were read off backend/services/api.py
and backend/invoices.py; the six new ones are the plan.
"""

import html
import json
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
        "/api/shares  {invoice_ids?, owner_name?, account_id?}",
        (("shares", True), ("invoices", False)),
        "-- only when the caller sent no ids: snapshot the whole view\n"
        "SELECT id FROM invoices ORDER BY issued_on DESC NULLS LAST, id;\n"
        "\n"
        "-- who this goes out as, resolved before the insert:\n"
        "-- GET {unipile_dsn}/api/v1/accounts -> the mailbox and its name\n"
        "-- name = account.name or the local part of the address\n"
        "\n"
        "INSERT INTO shares\n"
        "  (token, owner_key_hash, invoice_ids,\n"
        "   owner_name, owner_email, created_at, expires_at)\n"
        "VALUES ($1, $2, $3::jsonb, $4, $5, now(), now() + interval '7 days');",
        "The only write the flow makes, and the only place the owner's identity "
        "is decided. `invoice_ids` is a JSONB snapshot and is never updated: a "
        "later scan must not widen a link that has already been sent. The two "
        "owner fields are frozen for the same reason - disconnecting a mailbox "
        "must not change what an already-sent link says about who sent it. "
        "Returns {token, url, owner_key, owner_name, expires_at}, and the owner "
        "key is returned exactly once - only its sha256 is stored.",
    ),
    "manifest": Endpoint(
        "GET",
        "/api/s/{token}",
        (("shares", True), ("invoices", False)),
        "SELECT token, invoice_ids, owner_name, owner_email,\n"
        "       created_at, expires_at\n"
        "FROM shares WHERE token = $1;     -- primary key, no index needed\n"
        "\n"
        "SELECT id, issued_on, data FROM invoices\n"
        "WHERE id = ANY($1::text[])\n"
        "ORDER BY issued_on DESC NULLS LAST, id;",
        "Two queries, and the first one deliberately does not filter on "
        "expires_at. `WHERE expires_at > now()` would fold an expired share "
        "into a missing one and cost the page the difference between 410 and "
        "404 - which is the difference between the two dead-end screens. The "
        "row is fetched, then the expiry is compared.\n\n"
        "It also carries `owner_name` and `owner_email`, which is what lets the "
        "recipient's page name a person: they have no account and can be shown "
        "nothing this response does not hold.",
    ),
    "share_rename": Endpoint(
        "PATCH",
        "/api/s/{token}  {owner_name, owner_key}",
        (("shares", True),),
        "SELECT owner_key_hash FROM shares WHERE token = $1;\n"
        "-- compare_digest(sha256(owner_key), owner_key_hash)\n"
        "\n"
        "UPDATE shares SET owner_name = $2 WHERE token = $1;",
        "The one column of a live share that can change, and the only write in "
        "the flow that is not the insert. Gated by the same owner key that gates "
        "the send, so a recipient cannot rewrite the name they were greeted by. "
        "`owner_email` is not writable: it is the mailbox that will actually "
        "send, and a typed address would make that line a claim rather than a "
        "fact. The browser keeps the corrected name in localStorage and passes "
        "it to the next POST /api/shares, so the correction is made once rather "
        "than once per link.",
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
        "SELECT token, invoice_ids, owner_name, expires_at\n"
        "FROM shares WHERE token = $1;\n"
        "\n"
        "SELECT id, issued_on, data FROM invoices\n"
        "WHERE id = ANY($1::text[])\n"
        "ORDER BY issued_on DESC NULLS LAST, id;",
        "Serves the rendered mail as a document, for the composer's iframe to "
        "load. It exists so the preview is the bytes the send will use rather "
        "than a second template that can drift from it: one renderer, called "
        "here with the response written to the iframe and called on the send "
        "with the same output handed to Unipile. The mail names the owner twice "
        "and its footer names the expiry date, so both come out of this row "
        "rather than out of the template.",
    ),
    "email_send": Endpoint(
        "POST",
        "/api/s/{token}/email  {to, from_account_id, owner_key}",
        (("shares", True),),
        "SELECT owner_key_hash, invoice_ids, owner_name, expires_at\n"
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
    # A question this pin raised and that has since been answered. Kept rather
    # than deleted: the elements that turned out to need a decision are worth
    # knowing about, and quietly closing them would leave a map that had never
    # been wrong about anything.
    decided: str = ""
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
                "min and max issued date across the snapshot; the date the "
                "link stops working is `expires_at`, straight off the "
                "response. " + DERIVED,
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
                "`owner_email`, which is the mailbox the link was made from. "
                "The owner's copy of this line needs only the address; the "
                "recipient's copy on 07-recipient.html is what the name is "
                "for.",
                decided="`shares` as first specified carried no owner at all, "
                "so neither this line nor its recipient-facing twin could be "
                "filled. Settled 2026-08-15: two columns, `owner_name` and "
                "`owner_email`, written at creation from the connected mailbox "
                "and frozen with the snapshot. Deriving them at read time from "
                "the invoices was the alternative and is worse - the mailbox "
                "that received an invoice is not necessarily the person "
                "sharing it, and disconnecting an account would rewrite what a "
                "link already sent says about who sent it.",
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
                '<p class="live">',
                "It stops working on 12 July 2026",
                "manifest",
                "`expires_at`, formatted. Nothing computes a countdown and "
                "nothing polls: the date is in the response the page already "
                "made, and it cannot change afterwards.",
                decided="This line used to be a Revoke button. Settled "
                "2026-08-14 in notes.md and drawn 2026-08-15: no DELETE "
                "/s/{token}, no `revoked_at`, and a fixed seven days set at "
                "creation instead. What replaced the control is not another "
                "control but the fact it would have been used to establish.",
            ),
            Pin(
                '<p class="sent-as">',
                "Recipients see it from Martin Kirov",
                "manifest",
                "`owner_name` off the same response. It is stated on the "
                "owner's own page because it is the one thing here that is "
                "shown to people the owner cannot see - and because the "
                "fallback, the local part of the address, is exactly the value "
                "somebody will want to fix.",
            ),
            Pin(
                '<a class="btn-quiet" href="03b-name.html"',
                "Change",
                "share_rename",
                "The only owner-side write left in the flow, and the reason "
                "the owner key survived the removal of revoke: without it "
                "anyone holding the link could rewrite the name they were "
                "greeted by. The editing state is 03b-name.html.",
            ),
        ),
    ),
    "03b-name.html": (
        "Correcting the name",
        "One field, one write, and the only column of a live share that can "
        "change.",
        (
            Pin(
                '<input id="sent-as"',
                "The name, as taken from the mailbox",
                "manifest",
                "Filled with `owner_name` as it stands - here the fallback "
                "value, the local part of the address, which is what a mailbox "
                "carrying no display name of its own produces. The field is "
                "seeded from the response, not from the browser.",
            ),
            Pin(
                '<p class="field-note"',
                "Taken from martin@kirov.dev",
                "manifest",
                "`owner_email`, which is not editable. It is the mailbox that "
                "will actually send, checked against /api/accounts when it is "
                "used, so a typed address here would be a claim the send would "
                "then have to refuse.",
            ),
            Pin(
                '<a class="btn btn-secondary" href="03-preview.html"',
                "Save",
                "share_rename",
                "One UPDATE of one column, gated by the owner key. The browser "
                "also keeps the new name in localStorage and sends it with the "
                "next POST /api/shares, so a correction made here does not "
                "have to be made again on the next link.",
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
                "The iframe's `src` is the route: the composer fetches the "
                "rendered mail rather than drawing one. Loading is what makes "
                "it the real thing - the same renderer, the same row, the same "
                "bytes the send will hand to Unipile.",
                decided="No route in any spec served this, and the design "
                "rules out the alternative by name: the iframe must show what "
                "is about to be sent, not a look-alike. Settled 2026-08-15 - "
                "the route exists, GET /api/s/{token}/email/preview, and it is "
                "the tenth endpoint in the map. A second template that could "
                "drift from the sending one was the only other answer.",
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
                "`owner_name` and `owner_email`, both off the manifest. This "
                "is the screen the two columns exist for: the reader has no "
                "account, so every word about who shared with them has to have "
                "travelled inside the link. The name is whatever the owner "
                "last corrected it to; the address is the mailbox, and it is "
                "here so a reply has somewhere to go.",
                decided="The same question as 03-preview.html and the reason "
                "it had to be answered rather than dropped. Settled "
                "2026-08-15: resolved from the connected mailbox at creation "
                "and stored on the row - the mailbox's own display name, or "
                "the local part of its address when it has none.",
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
    "09-expired.html": (
        "Expired",
        "A 410, and the reason the manifest query is written the way it is.",
        (
            Pin(
                '<section class="dead"',
                "This link has expired",
                "manifest",
                "The row came back and `expires_at` had passed: 410 Gone. This "
                "is why the first query does not say `WHERE expires_at > "
                "now()` - a filtered query returns no row for an expired share "
                "and could only ever answer 404, which is the other screen and "
                "the other instruction to the reader. The 410 body carries the "
                "two owner fields and the two dates and nothing else: no "
                "invoice ids, no manifest, because the second query is never "
                "run once the expiry has failed.",
                decided="Drawn as a revoked share until 2026-08-15, when the "
                "screens caught up with the TTL: nobody turns a link off, its "
                "seven days run out. Same page, same status code, different "
                "cause - and no DELETE route to serve it.",
            ),
            Pin(
                '<div class="dead-actions"',
                "Ask for a new link",
                "manifest",
                "The address it mails is `owner_email` and the name on the "
                "button is `owner_name`, both off the row that just answered "
                "410. Nothing else is retried: the state is settled, so the "
                "one action left is asking the person who shared for another "
                "link.",
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
                "filtered in the query. It is also the one dead end that can "
                "name nobody: with no row there is no owner to mail, which is "
                "the visible difference between this page and 09-expired.html.",
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
        if pin.decided:
            parts.append(
                f'<p class="wiring-decided"><b>Answered.</b> '
                f"{html.escape(pin.decided)}</p>"
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
        source = swap(
            source,
            f'<link rel="stylesheet" href="{sheet}"/>',
            f'<link rel="stylesheet" href="../share-flow-v3-light/{sheet}"/>',
            screen,
        )
    source = swap(
        source, "</head>", '<link rel="stylesheet" href="annotations.css"/>\n</head>', screen
    )
    # So a tab holding the annotated screen is not mistaken for the real one.
    source = swap(
        source, " · Invoice Pilot</title>", " · wiring · Invoice Pilot</title>", screen
    )

    source = mark(source, pins, screen)
    return swap(source, "</body>", f"{legend(title, lede, pins)}</body>", screen)


# The order the viewer pages through, which is the flow's order rather than
# the filenames': loading comes before the page it stands in for, and the mail
# sits between sending it and the recipient opening it. Taken from the list
# ../share-flow-v3-light/viewer.html already carried, plus 01b-row, which that
# list omits because nothing in the flow passes through it. It is in this
# folder and reachable, so it pages here, one step after the screen it opens
# out of.
VIEWER_ORDER = (
    "01-idle.html",
    "01b-row.html",
    "02-link.html",
    "10-loading.html",
    "03-preview.html",
    "03b-name.html",
    "11-zipping.html",
    "04-compose.html",
    "05-from.html",
    "12-invalid.html",
    "06-sent.html",
    "email.html",
    "07-recipient.html",
    "08-send-failed.html",
    "09-expired.html",
    "13-not-found.html",
)


def swap(source: str, needle: str, replacement: str, where: str) -> str:
    """`str.replace` that refuses to do nothing.

    A replacement that silently misses is the failure this folder exists to
    avoid: it leaves a file that looks generated and is not. Every rewrite goes
    through here for the same reason every pin is anchored.
    """
    if needle not in source:
        raise SystemExit(
            f"{where}: expected to find {needle!r}. Re-read the file in "
            f"../share-flow-v3-light/ and fix the needle in annotate.py."
        )
    return source.replace(needle, replacement, 1)


def cut(source: str, start: str, end: str, replacement: str, what: str) -> str:
    """Replace everything between two anchors, or stop naming the one that moved.

    Used instead of matching the whole block: viewer.html is a hand-edited
    one-off, and anchoring on the two ends of a region survives edits inside it
    that an exact match of the whole thing would not.
    """
    head = source.find(start)
    tail = source.find(end, head + len(start)) if head >= 0 else -1
    if head < 0 or tail < 0:
        raise SystemExit(
            f"viewer.html: could not find the {what} block "
            f"({start.strip()!r} .. {end.strip()!r}). Re-read "
            f"../share-flow-v3-light/viewer.html and fix the anchors."
        )
    return source[:head] + replacement + source[tail:]


def viewer() -> str:
    """The paginated viewer, pointed at the annotated screens.

    The screens are the design folder's viewer, with its screen list replaced.
    That list is the one thing it cannot keep: it discovers screens by fetching
    index.html and reading `.step` sections off the contact sheet, and this
    folder's index.html is a map rather than a flow diagram, so the parse would
    fail into a hard-coded fallback that nothing keeps in step. Here the list
    has a real single source - SCREENS above - so it is written out rather than
    rediscovered.
    """
    source = (SRC / "viewer.html").read_text(encoding="utf-8")
    source = swap(
        source,
        '<link rel="stylesheet" href="tokens-v3.css"/>',
        '<link rel="stylesheet" href="../share-flow-v3-light/tokens-v3.css"/>',
        "viewer.html",
    )
    source = swap(
        source,
        "Flow viewer · Share flow v3 light",
        "Flow viewer · Share flow v3 light, annotated",
        "viewer.html",
    )

    entries = []
    for name in VIEWER_ORDER:
        stem = name.removesuffix(".html")
        if name not in SCREENS:
            # email.html: copied rather than annotated, and the viewer says so
            # rather than leaving a screen with no panel unexplained.
            entries.append(
                {
                    "src": name,
                    "num": "mail",
                    "title": "The email",
                    "route": "no pins",
                    "caption": "<p>The draft, copied unannotated: the composer "
                    "loads this file in an <code>iframe</code>, and a panel "
                    "inside that frame would annotate the preview instead of "
                    "the composer. What sends it is pin 5 on "
                    "<code>04-compose.html</code>.</p>",
                }
            )
            continue

        title, lede, pins = SCREENS[name]
        # Distinct routes, in the order they are first pinned.
        routes: list[str] = []
        for pin in pins:
            if pin.endpoint and pin.endpoint not in routes:
                routes.append(pin.endpoint)
        calls = " ".join(
            f"<code>{ENDPOINTS[key].method} {html.escape(ENDPOINTS[key].path)}</code>"
            for key in routes
        )
        gaps = sum(1 for pin in pins if pin.gap)
        decided = sum(1 for pin in pins if pin.decided)
        caption = f"<p>{html.escape(lede)}</p>"
        caption += f"<p>{calls}</p>" if calls else "<p>No request at all.</p>"
        if gaps:
            caption += (
                f"<p><b>{gaps} open question{'s' if gaps > 1 else ''}</b> on this "
                f"screen - see the panel.</p>"
            )
        if decided:
            caption += (
                f"<p><b>{decided} answered question{'s' if decided > 1 else ''}</b> "
                f"on this screen - the panel says what was decided and what it "
                f"replaced.</p>"
            )
        entries.append(
            {
                "src": name,
                "num": stem.split("-")[0],
                "title": title,
                "route": f"{len(pins)} pin{'s' if len(pins) > 1 else ''}",
                "caption": caption,
            }
        )

    listing = ",\n".join(
        "  {"
        + ", ".join(f"{key}: {json.dumps(value)}" for key, value in entry.items())
        + "}"
        for entry in entries
    )

    source = cut(
        source,
        "// Screens are read from index.html",
        "\nconst el = {",
        f"""// The screen list, written out by annotate.py from the same table that
// places the pins. The design folder's viewer discovers this by fetching
// index.html and reading `.step` sections off it; this folder's index.html is
// a map rather than a flow diagram, so there is nothing there to parse and
// nothing gained by parsing it - the list already has one source.
const SCREENS = [
{listing},
];
""",
        "screen list",
    )

    return cut(
        source,
        "async function loadScreens() {",
        "\nconst slug =",
        "async function loadScreens() {\n  return SCREENS;\n}\n",
        "loadScreens",
    )


WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven",
         8: "Eight", 9: "Nine", 10: "Ten", 11: "Eleven", 12: "Twelve"}


def index() -> str:
    """The contact sheet: every screen, then every endpoint, from one table."""
    total = len(ENDPOINTS)
    shipped = sum(1 for route in ENDPOINTS.values() if not route.is_new)
    planned = total - shipped
    shipped = WORDS.get(shipped, str(shipped))
    planned, total = (WORDS.get(n, str(n)).lower() for n in (planned, total))
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
    open_part = (
        f"""
  <section class="map-part">
    <h2>What nothing answers yet</h2>
    <p class="map-note">Elements that render data no specified endpoint can
      return.</p>
    <ol class="map-gaps">{gaps}</ol>
  </section>
"""
        if gaps
        else """
  <section class="map-part">
    <h2>What nothing answers yet</h2>
    <p class="map-note">Nothing, at the moment. Every element on these screens
      has a route behind it and every route has a query. The five questions this
      map raised are below, with what was decided.</p>
  </section>
"""
    )

    settled = "".join(
        f"<li><b>{html.escape(pin.element)}</b> "
        f'<a href="{name}">{name}</a><p>{html.escape(pin.decided)}</p></li>'
        for name, (_, _, pins) in SCREENS.items()
        for pin in pins
        if pin.decided
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
    <p class="map-note">Each one carries a panel naming what fills its pinned
      elements. <a href="viewer.html">viewer.html</a> pages through them one at
      a time, with the routes and the open questions in the caption bar.</p>
    <ol class="map-grid">{cards}</ol>
  </section>

  <section class="map-part">
    <h2>The endpoints</h2>
    <p class="map-note">{shipped} of these ship today. The {planned} new ones
      are the plan; <code>shares</code> is the one new table, and every route
      that reads it looks the row up by primary key.
      <a href="backend.md">backend.md</a> explains all {total} and their queries
      in plain terms.</p>
    <table class="map-table">
      <thead><tr><th>Method</th><th>Path</th><th>Tables</th><th>Screens</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </section>

{open_part}
  <section class="map-part">
    <h2>What the map asked, and what was decided</h2>
    <p class="map-note">Found while mapping the screens to routes, and settled
      afterwards. Each one is pinned on the screen that raised it;
      <a href="revisions.md">revisions.md</a> names the commit each answer landed
      in.</p>
    <ol class="map-gaps is-settled">{settled}</ol>
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

    (HERE / "viewer.html").write_text(viewer(), encoding="utf-8")
    print(f"wrote viewer.html ({len(VIEWER_ORDER)} screens)")


if __name__ == "__main__":
    main()
