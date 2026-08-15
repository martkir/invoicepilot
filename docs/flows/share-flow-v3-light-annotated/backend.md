# The backend, in plain terms

What has to be built for the share flow to work: **one table and seven new
endpoints.** This file explains all of it in order. The same facts are pinned
onto the screens themselves — open [`index.html`](index.html) for that, or read
this straight through. What changed between drafts, and the commit to go back
to, is in [`revisions.md`](revisions.md).

---

## The short version

1. A user ticks some invoices and clicks **Share**.
2. We write **one row** to a new `shares` table: a random token, the list of
   invoice ids, who is sharing them, and an expiry date 7 days out.
3. The token is the URL. Anyone who has it can see who shared with them, read
   those invoices and download them as a zip. After 7 days it stops working on
   its own.

That is the whole feature. Everything below is detail.

---

## The one new table

**One click, one row.** Clicking Share writes a new `shares` row and puts the
link on the clipboard in the same gesture — there is no dialog in between, so
the click *is* the share.

```sql
CREATE TABLE shares (
    token           text        PRIMARY KEY,
    owner_key_hash  text        NOT NULL,
    invoice_ids     jsonb       NOT NULL,
    owner_name      text        NOT NULL,
    owner_email     text        NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz NOT NULL
);
```

Seven columns, one line each:

| Column | What it is |
| --- | --- |
| `token` | 22 random characters. It is the URL **and** the password — having the link is what grants access. |
| `owner_key_hash` | A second secret, returned once when the link is made and kept in the creator's browser. It is what lets *them* send the email and rename the link, and stops a recipient doing either. We store only its sha256, never the key itself. It is **not** part of any lookup: which invoices a link covers is `invoice_ids` and nothing else. A new owner key is minted per share, so it identifies a row, not a person. |
| `invoice_ids` | The list of invoice ids this link covers, frozen at creation. |
| `owner_name` | Who the recipient is told shared this. Taken from the connected mailbox when the link is made, and the only column that can be changed afterwards. |
| `owner_email` | The mailbox it was made from. Shown to the recipient so a reply has somewhere to go, and never editable. |
| `created_at` | When it was made. |
| `expires_at` | `created_at + 7 days`. After this the link stops working. |

**Why the id list is frozen.** If you share 37 invoices today and a scan finds 5
more tomorrow, the link you already sent must still show 37. Storing the ids at
creation is what guarantees that.

### Where the owner's name comes from

The recipient has no account. Everything they are told about who shared with
them has to have travelled inside the link, which is why these two columns
exist rather than a join to something.

Both are resolved once, when the link is made, from the connected mailbox:

1. **The address** is the mailbox's own — `martinvkirov@gmail.com`.
2. **The name** is that mailbox's display name if Unipile carries one.
3. **If it does not**, the local part of the address, verbatim:
   `martinvkirov`. Recognisable, and clearly not what anyone wants to be
   introduced as, which is the point — it is shown to the owner rather than
   hidden, with one control beside it.
4. **The owner can correct the name** (endpoint 3 below). The browser keeps the
   correction and sends it with the next `POST /api/shares`, so it is made once
   rather than once per link.

**Why they are frozen too.** Disconnecting a mailbox, or connecting a second
one, must not change what a link already sent says about who sent it. The row
is the record of a share that happened.

**Why the address is not editable.** It is the mailbox that will actually send,
and the send checks it against `/api/accounts`. A typed address would make that
line a claim the send would then have to refuse.

**Why there is no `title` column.** The filename on the share page
(`invoices-2026-Q2.zip`) is worked out from the dates of the invoices in the
list. Nothing to store means nothing that can go stale.

**Why no expiry index.** Every read looks the row up by `token`, which is the
primary key. There is no query that scans for expired shares.

### Links are disposable, and that is fine

Nothing stops the same invoices being shared twice. Two clicks make two rows,
two tokens, two live links — and that is the intended behaviour rather than a
hole in it:

- **A second browser makes a second link.** The owner key lives in
  `localStorage`, so a different browser has no way to recognise the first
  share. It mints a new one.
- **Closing the browser mid-flow costs the owner key, not the link.** The row
  is written before the popover appears, so the link is live and stays live.
  What is lost is the ability to send email for that share, because the key
  existed only in that browser. Since there is no revoke, an orphaned key costs
  nothing and the share lapses on its own after 7 days.
- **Nothing needs deduplicating.** A share is a snapshot with an expiry, not a
  named thing somebody maintains. Two links to the same 37 invoices both work
  and both lapse.

The one thing this rules out is treating a share as *the* link for a batch. If
that is ever wanted — one durable link per selection, reused — it is a
different feature with a different table, not a tweak to this one.

### Creating it

No Alembic needed. `scripts/migrate_db.py` calls `Base.metadata.create_all()`,
which only ever adds what is missing. Add the model to `backend/models.py`, run
the script, done.

---

## The endpoints

Eleven routes touch these screens. **Four already exist** — they are listed
first so it is clear what is not new work.

### Already built

| Route | What it does |
| --- | --- |
| `GET /api/accounts` | Lists connected mailboxes. Touches no table; the answer comes from Unipile. |
| `POST /api/scan` | Starts a scan. Writes to `invoices`. |
| `GET /api/invoices` | One page of invoices for the dashboard. |
| `GET /api/invoices/{id}/document` | One invoice's PDF. |

### New

#### 1. Make a link

```
POST /api/shares      {invoice_ids?, owner_name?, account_id?}
   -> {token, url, owner_key, owner_name, expires_at}
```

The only place a row is created. If the caller sends no ids, we snapshot
everything. Before the insert, one call to Unipile settles who this goes out
as.

```sql
-- only when no ids were sent
SELECT id FROM invoices ORDER BY issued_on DESC NULLS LAST, id;

-- who it goes out as, before the insert:
-- GET {unipile_dsn}/api/v1/accounts  -> the mailbox and its name
-- name = owner_name from the caller, else account.name,
--        else the part of the address before the @

INSERT INTO shares
  (token, owner_key_hash, invoice_ids,
   owner_name, owner_email, created_at, expires_at)
VALUES ($1, $2, $3::jsonb, $4, $5, now(), now() + interval '7 days');
```

`owner_key` comes back in this response and **never again** — the browser keeps
it in `localStorage`.

`account_id` picks the mailbox when more than one is connected; without it, the
first. No screen offers that choice at creation, and it is not obvious that one
should — the link is not a message.

#### 2. Read the link

```
GET /api/s/{token}    -> the manifest: summary + one row per invoice
```

Two queries.

```sql
SELECT token, invoice_ids, owner_name, owner_email,
       created_at, expires_at
FROM shares WHERE token = $1;

SELECT id, issued_on, data FROM invoices
WHERE id = ANY($1::text[])
ORDER BY issued_on DESC NULLS LAST, id;
```

Everything on the share page — the filename, the four facts, the whole manifest
table, the line naming who shared it — comes from these two queries. Nothing is
stored pre-computed.

**One thing to get right:** the first query does *not* say
`WHERE expires_at > now()`. It looks the row up, then checks the date in code.
That is deliberate — see [Expired vs missing](#expired-vs-missing) below. The
410 it answers with when the date has passed carries the two owner fields and
the two dates, so the expired page can name a person and a day; the second
query never runs.

#### 3. Rename the link

```
PATCH /api/s/{token}   {owner_name, owner_key}   -> 204
```

```sql
SELECT owner_key_hash FROM shares WHERE token = $1;
-- compare_digest(sha256(owner_key), owner_key_hash)

UPDATE shares SET owner_name = $2 WHERE token = $1;
```

The only `UPDATE` in the feature, and the only column it may touch. Gated by
the owner key, so a recipient cannot rewrite the name they were greeted by.

This is the reason the owner key survived the removal of revoke: without it
anyone holding the link could rename the person who sent it.

#### 4. Thumbnails

```
GET /api/s/{token}/thumb/{invoice_id}    -> a small WebP image
```

```sql
SELECT invoice_ids, expires_at FROM shares WHERE token = $1;
-- the requested id must be in that list, or 404
SELECT data FROM invoices WHERE id = $1;
```

The check that the id is in *this* share's list is the security: a token gets
you its own invoices and nothing else, so guessing an id from someone else's
share gets you a 404.

The image is not in Postgres. It is a `thumb.webp` file sitting next to the PDF,
made when the invoice was extracted. If it is missing we render it on the first
request, so nothing has to be backfilled.

#### 5. The zip

```
GET /api/s/{token}/zip    -> a streamed zip file
```

Same two queries as the manifest. The rows give us the filenames and build
`invoices.csv`; the PDFs are streamed off disk as the zip is written, so we
never hold the whole batch in memory.

No parameters — the link *is* the batch. There is nothing to choose.

#### 6. Preview the email

```
GET /api/s/{token}/email/preview    -> the email, as HTML
```

Same queries again, for the summary the email quotes, the name it signs off
with and the expiry date in its footer. The composer's `<iframe>` points
straight at this URL.

It exists so the preview in the composer is the *actual* email that will be
sent, rather than a look-alike that could drift from it: **one renderer**,
called here and called again on the send, with the same output going to
Unipile.

#### 7. Send the email

```
POST /api/s/{token}/email    {to, from_account_id, owner_key}   -> 204
```

```sql
SELECT owner_key_hash, invoice_ids, owner_name, expires_at
FROM shares WHERE token = $1;
```

Then three things, in order:

1. Check `owner_key` against `owner_key_hash` (with `compare_digest`, not `==`).
2. Check `from_account_id` is really one of the user's connected mailboxes —
   it arrives from the browser, so it cannot be trusted.
3. Hand it to Unipile.

**Nothing is written.** No table records that an email went out.

---

## Every query in the feature

There are only four shapes, and none of them can get slow:

```sql
SELECT ... FROM shares   WHERE token = $1;        -- primary key
UPDATE shares SET owner_name = $2 WHERE token = $1;
SELECT ... FROM invoices WHERE id = ANY($1);      -- primary key, many
SELECT ... FROM invoices ORDER BY issued_on ...;  -- already indexed
```

That is the whole point of keeping the ids in a JSONB column: there is no join,
no second table, and no query that grows worse as shares pile up.

---

## Three decisions worth knowing

### Expired vs missing

Two different dead ends, and users need to tell them apart:

- **410 Gone** — this link worked, and it has expired. *Ask for a new one.*
- **404 Not Found** — no such link ever existed. *Check what you pasted.*

If the query filtered with `WHERE expires_at > now()`, an expired share would
come back as no row at all and we could only ever answer 404. So we fetch the
row and compare the date ourselves.

### There is no revoke

[`../share-flow-v3-light/notes.md`](../share-flow-v3-light/notes.md) replaced it
with the 7-day expiry on 2026-08-14, and the screens caught up on 2026-08-15. So:
no `DELETE /s/{token}`, the column is `expires_at` rather than `revoked_at`, and
the owner block on the share page states a date where a button used to be.

Nothing ever has to be cleaned up. The link stops working because the date has
passed, not because a row changed, so there is no job to run and nothing to
schedule.

If revoke is ever wanted back, it is cheap: `UPDATE shares SET expires_at =
now()`. No new column, no new state.

### `/s/{token}` is two different things

- `/s/{token}` — the **page** a person opens. Static frontend.
- `/api/s/{token}` — the **data** that page fetches.

They must not be confused, because nginx sends everything under `/api/` to the
backend and everything else to the frontend.

---

## Four things that do not exist yet

Small, but each one blocks something:

1. **A `PUBLIC_BASE_URL` setting.** `POST /shares` has to return a full URL, and
   the email needs one for its button. `backend/core/config.py` only knows the
   host and port it binds to.
2. **Sending email.** `backend/unipile.py` can list mail and download
   attachments, but it cannot send. Needs one function calling Unipile's
   `POST /api/v1/emails`.
3. **Pillow.** Already have `pypdfium2` for rendering the PDF page, but encoding
   it to WebP needs Pillow. One line in `pyproject.toml`.
4. **Zip streaming.** Python's built-in `zipfile` wants a file it can seek
   around in. Use `zipstream-ng` with no compression (PDFs do not compress
   anyway) rather than hand-writing the zip format.

Plus one frontend change: the share page needs its own entry point, and nginx
needs a rule for `/s/`, otherwise the dashboard's catch-all swallows it.

---

## The two questions this file used to end on

Both were found by mapping each screen element to a route, and both are
answered. They are kept here because the answers are the two least obvious
things above.

**Who shared this?** The recipient's page says *"Shared with you by Martin Kirov
· martin@kirov.dev"* and the `shares` table had nowhere to keep either half.
*Answered:* two columns, filled from the connected mailbox at creation and
frozen — see [Where the owner's name comes from](#where-the-owners-name-comes-from).
The alternative was deriving it at read time from the mailbox that received the
invoices, which is a different person as soon as anyone forwards an invoice to
their accountant.

**The email preview.** The composer has a real iframe and the design insists the
preview be the real mail. *Answered:* endpoint 6 exists, and the send calls the
same renderer. The alternative was a second template that could silently drift
from the one that actually sends.

---

## Suggested order

1. `shares` table + `POST /shares` + `GET /s/{token}`.
2. Share button and popover on the dashboard.
3. Share page + zip download. **Usable by real people from here.**
4. Thumbnails.
5. Composer + preview + send.
6. `PATCH /s/{token}`, and virtualize the manifest past 50 rows.

Step 5 is where the owner's name first has to be right, because the mail is
signed with it — but it is written in step 1, and it is worth getting the
fallback right there rather than discovering in step 5 that every link says
`martinvkirov`.

---

*The routes and SQL above are also held in `ENDPOINTS` in
[`annotate.py`](annotate.py), which is what draws them onto the screens. If one
changes, change both.*
