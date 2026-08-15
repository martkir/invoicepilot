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
   invoice ids, and an expiry date 7 days out.
3. The token is the URL. Anyone who has it can read those invoices and download
   them as a zip. After 7 days it stops working on its own.

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
    created_at      timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz NOT NULL
);
```

Five columns, one line each:

| Column | What it is |
| --- | --- |
| `token` | 22 random characters. It is the URL **and** the password — having the link is what grants access. |
| `owner_key_hash` | A second secret, returned once when the link is made and kept in the creator's browser. It is what lets *them* send the email and stops a recipient doing it. We store only its sha256, never the key itself. It is **not** part of any lookup: which invoices a link covers is `invoice_ids` and nothing else. A new owner key is minted per share, so it identifies a row, not a person. |
| `invoice_ids` | The list of invoice ids this link covers, frozen at creation. |
| `created_at` | When it was made. |
| `expires_at` | `created_at + 7 days`. After this the link stops working. |

**Why the id list is frozen.** If you share 37 invoices today and a scan finds 5
more tomorrow, the link you already sent must still show 37. Storing the ids at
creation is what guarantees that.

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

Ten routes touch these screens. **Four already exist** — they are listed first
so it is clear what is not new work.

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
POST /api/shares      {invoice_ids?}
   -> {token, url, owner_key, expires_at}
```

The only place anything is written. If the caller sends no ids, we snapshot
everything.

```sql
-- only when no ids were sent
SELECT id FROM invoices ORDER BY issued_on DESC NULLS LAST, id;

INSERT INTO shares
  (token, owner_key_hash, invoice_ids, created_at, expires_at)
VALUES ($1, $2, $3::jsonb, now(), now() + interval '7 days');
```

`owner_key` comes back in this response and **never again** — the browser keeps
it in `localStorage`.

#### 2. Read the link

```
GET /api/s/{token}    -> the manifest: summary + one row per invoice
```

Two queries.

```sql
SELECT token, invoice_ids, created_at, expires_at
FROM shares WHERE token = $1;

SELECT id, issued_on, data FROM invoices
WHERE id = ANY($1::text[])
ORDER BY issued_on DESC NULLS LAST, id;
```

Everything on the share page — the filename, the four facts, the whole manifest
table — comes from these two queries. Nothing is stored pre-computed.

**One thing to get right:** the first query does *not* say
`WHERE expires_at > now()`. It looks the row up, then checks the date in code.
That is deliberate — see [Expired vs missing](#expired-vs-missing) below.

#### 3. Thumbnails

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

#### 4. The zip

```
GET /api/s/{token}/zip    -> a streamed zip file
```

Same two queries as the manifest. The rows give us the filenames and build
`invoices.csv`; the PDFs are streamed off disk as the zip is written, so we
never hold the whole batch in memory.

No parameters — the link *is* the batch. There is nothing to choose.

#### 5. Preview the email

```
GET /api/s/{token}/email/preview    -> the email, as HTML
```

Same queries again, for the summary the email quotes. This exists so the preview
in the composer is the *actual* email that will be sent, rather than a
look-alike that could drift from it.

#### 6. Send the email

```
POST /api/s/{token}/email    {to, from_account_id, owner_key}   -> 204
```

```sql
SELECT owner_key_hash, invoice_ids, expires_at
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

There are only three shapes, and none of them can get slow:

```sql
SELECT ... FROM shares   WHERE token = $1;        -- primary key
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

The screens still draw a **Revoke** button, but
[`../share-flow-v3-light/notes.md`](../share-flow-v3-light/notes.md) replaced it
with the 7-day expiry on 2026-08-14. So: no `DELETE /s/{token}`, and the column
is `expires_at`, not `revoked_at`.

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

## Two questions nothing answers yet

Found by mapping each screen element to a route. Both need deciding before the
screens can be built as drawn.

**Who shared this?** The recipient's page says *"Shared with you by Martin Kirov
· martin@kirov.dev"*. The `shares` table has no owner — no name, no address. So
either the manifest works it out from the mailbox on the invoices, or `shares`
needs another column.

**The email preview.** Endpoint 5 above is not in any spec. It is listed here
because the composer has a real iframe in it and the design insists the preview
be the real email. Either that route exists, or the preview becomes a second
template that can silently drift from the one that actually sends.

---

## Suggested order

1. `shares` table + `POST /shares` + `GET /s/{token}`.
2. Share button and popover on the dashboard.
3. Share page + zip download. **Usable by real people from here.**
4. Thumbnails.
5. Composer + send.
6. Virtualize the manifest past 50 rows.

---

*The routes and SQL above are also held in `ENDPOINTS` in
[`annotate.py`](annotate.py), which is what draws them onto the screens. If one
changes, change both.*
