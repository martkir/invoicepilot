# Share flow

How a user hands a batch of extracted invoices to someone else — an accountant,
a co-founder, a client — without either side having an account.

Screens live beside this file as real pages linked against the app's own
`tokens.css` and `dashboard.css`; open `index.html` for the contact sheet.

---

## The whole flow

```
dashboard                      share page  /s/<token>
┌────────────────────┐         ┌──────────────────────────────┐
│ Invoices    [↗][⤓] │         │ invoices-2026-Q2.zip         │
│                    │  click  │ 37 invoices · 12.4 MB        │
│  ┌───────────────┐ │   ↗     │ Apr 1 – Jun 30, 2026         │
│  │ link copied ✓ │ │ ──────► │              [ Download ]    │
│  │ [Open][Email] │ │         ├──────────────────────────────┤
│  └───────────────┘ │         │ [▤][▤][▤][▤][▤]  +32 more    │
└────────────────────┘         │ 1 Hetzner  …pdf  Apr 3  42.10│
                               │ 2 AWS      …pdf  Apr 5 880.00│  ← a sheet
                               │ …                            │
                               │   37 invoices  36 documents  │
                               └──────────────────────────────┘
```

**Owner:** Update → click ↗ → the link exists and is already on the clipboard.
Two clicks from a scanned mailbox to a shareable link.
**Recipient:** open link → see what it is → Download. No account, no sign-up
wall, no "request access".

**Optional third step:** Send by email — one field (To), one Send. The draft is
already written.

---

## What makes it simple

Five things deliberately do **not** exist. Each one is a decision the user would
otherwise have to make before they get their link.

1. **No share dialog.** The click *is* the share. The link is minted and copied
   to the clipboard in the same gesture; the popover reports what happened, it
   does not ask anything. Nothing to configure means nothing to get wrong.
2. **No expiry picker, no password, no permission levels.** A share is live
   until revoked. The single off switch is *Revoke*, on the share page itself.
3. **Preview is not a separate screen.** The owner's "Open preview" opens the
   exact URL the recipient gets, rendered by the same page. There is no
   what-they-will-see mode to keep in step with what they actually see — and no
   doubt in the owner's mind about whether the preview was accurate.
4. **No picking on the share page.** The link *is* the batch: no checkboxes, no
   partial zip, no "which version did I send?". Wrong batch is fixed where the
   batch is chosen — tick rows on the dashboard and share again, still two
   clicks. The page's job is to let someone *check* an export, not curate it.
5. **No attachments in the email.** The mail carries the summary and a button.
   A 12 MB attachment bounces, lands in spam, and goes stale; a link does not.

## What gets shared

Whatever the table would download today: **checked rows if any are checked,
otherwise every invoice in the current view**. That reuses the checkbox column
already in `InvoiceTable`, so the selection step costs zero new UI, and the
popover names the batch (`37 invoices`) so the choice is visible after the fact.

The token snapshots **invoice ids at creation time**. A later scan that finds
new invoices does not silently widen an already-sent link — the one property
worth being strict about when the URL is the only credential.

## The table is a sheet

The dashboard's table is a working surface — checkboxes, vendor logos, per-row
actions, 52px rows — because you come back to it every week and operate it. The
share page's table is the opposite kind of object: a **manifest of what is in
the zip**, read once by someone who will never return. So it is a plain sheet.

| | dashboard | share page |
| --- | --- | --- |
| row height | 52px | 30px |
| leading column | checkbox | row number |
| vendor | logo chip + name | name |
| actions | preview, download | none — the row is the control |
| columns | vendor, amount, issued | #, vendor, document, issued, amount |
| foot | pagination | counts: invoices, documents |
| rules | horizontal only | hairline grid, tabular figures |

The **document column carries the zip's own entry name** (`2026-04-05__amazon__
880.00EUR.pdf`), which is what makes it a manifest rather than a second copy of
the dashboard: what you read is literally what lands in the recipient's folder.
The last line counts what the zip contains — the two numbers a recipient checks
before they open anything.

**No summed amount anywhere** — not in the header, not on the last line, not in
the mail. It is a real cost: a batch total is the cheapest way to spot a wrong
export, and the per-row amounts no longer add up to anything on screen. It is
also one more number to render, keep consistent across three surfaces, and get
wrong in front of an accountant. The counts carry the identification work; the
amounts are per-row facts that speak for themselves.

Nothing on the sheet is operable because nothing is decidable; the whole row is
one target and it opens that invoice. In CSS terms every rule needs a `.sheet`
prefix, since `dashboard.css` styles bare `td` / `thead th` / `tbody tr`.

---

## Data

One new table. Same spirit as `invoices`: columns only where the database needs
to look something up.

```python
class Share(Base):
    __tablename__ = "shares"

    token: Mapped[str]         # 22-char urlsafe, the URL and the credential
    owner_key: Mapped[str]     # returned once at creation, held in localStorage
    invoice_ids: Mapped[list]  # JSONB snapshot — immutable after creation
    created_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
```

`token` is the primary key and the whole access-control model: possession of the
URL is permission to read. `owner_key` is the second, private half — it gates
the two actions a recipient must not have (send mail as the owner, revoke), and
the creating browser keeps it in `localStorage` so the owner never sees or types
it. Single-tenant today, but it is the shape that survives multi-tenant later.

No `title` column: the filename derives from the date range of the snapshot, so
there is nothing to store and nothing that can drift.

## API

Everything a link-holder can reach is scoped under `/s/{token}` and bounded by
that share's manifest. Invoice ids never appear on a public route outside the
snapshot they belong to, so a token grants exactly its own 37 documents and
guessing an id from another share buys nothing.

| Route | Purpose |
| --- | --- |
| `POST /shares` `{invoice_ids?}` | → `{token, url, owner_key}`. Omit ids to snapshot everything. |
| `GET /s/{token}` | Manifest: summary + one entry per invoice. 404 once revoked. |
| `GET /s/{token}/thumb/{invoice_id}` | First-page WebP, ~240px. Five per share, ever. |
| `GET /s/{token}/zip` | Streamed zip of the whole manifest. No parameters — the link is the batch. |
| `POST /s/{token}/email` `{to, from_account_id, owner_key}` | Sends as that connected mailbox. |
| `DELETE /s/{token}` `{owner_key}` | Revoke. |

**There is no single-document route**, because nothing on the page opens one:
no overlay, no pdf.js, no viewer screen, and no per-row link. Whoever wants to
read one invoice downloads the zip and opens it in the reader they already have
— which is better at PDFs than anything worth writing here. If that ever needs
to change, the cheap version is a row that links straight at the file and lets
the browser render it; the overlay is the expensive version and it is not
missed.

The zip is streamed, never assembled on disk: 37 invoices at 12 MB is small, but
the memory profile should not depend on the batch. Entry names reuse
`invoice_store.folder_name()` — `2026-04-03__hetzner__42.10EUR.pdf` — so the
recipient's folder sorts by date without anyone renaming anything.

## What the recipient actually gets

Two things, and the second one is the one an accountant opens first. **The page
is laid out as the zip's contents**, because "what am I about to download?" is
the only question a share page has to answer:

```
[zip] invoices-2026-Q2.zip · 37 invoices · 12.4 MB      [ Download all ]
──────────────────────────────────────────────────────────────────────
[pdf] 36 documents   the vendors' own files · 5 shown     ← grey band
      [▤][▤][▤][▤][▤]  +32 more
──────────────────────────────────────────────────────────────────────
[csv] invoices.csv   one row per invoice · 22 columns     ← white sheet
      #  Vendor  Invoice #  Document  Issued  Net  VAT  Total  +15 in csv
```

Each half is a **named part carrying its own file-type chip**, under a header
already chipped `zip`. That is the whole explanation — no sentence anywhere says
"the download contains PDFs and a spreadsheet", because the layout says it. The
two are separated by a full rule and a background change rather than the
hairline that divides rows: the grey band is one file, the white sheet another.

### On the page: eight columns, then a count

`#` · `Vendor` · `Invoice #` · `Document` · `Issued` · `Net` · `VAT` · `Total €`
· **`+15 in csv`**

Eight is the ceiling — past that a sheet stops being readable at a glance — and
the ninth column is not data at all. It is **the number of columns the CSV
carries and the page does not**, with a `…` in every row saying the record
continues past the right edge. Without it the sheet reads as the whole truth,
`invoices.csv` looks like a duplicate of what is already on screen, and fifteen
extracted fields quietly go unnoticed. Its `title` lists them.

The net/VAT split and the invoice number are on screen because they are the
reason the batch was sent — an accountant reconciling a quarter needs the number
to match a bank line and the VAT to reclaim it. Everything else in the payload
is one field too many for a page someone reads once, so it goes to the CSV.

**The count tracks the width.** Narrow screens drop columns in order of what can
be recovered elsewhere — `Document` and the money split at 900px, `Invoice #` at
640px — and each one moves into the count, so it reads `+15`, then `+18`, then
`+19`. A number that ignored the breakpoint would be a small lie. `data-*`
attributes plus `::after` do it with no JavaScript.

**No currency column:** the batch is EUR throughout, and a column that says the
same word 37 times is width spent on nothing. It should appear only when a
share actually holds more than one currency — the same rule as the From caret.

**Layout is `table-layout: fixed`** so column widths are a design decision
rather than an outcome of the longest filename in the batch, and every cell
clips to one line — a sheet whose row height changes with its data is not a
sheet. One trap worth writing down: under fixed layout a `display: none` column
**still reserves its declared width**, so the responsive rules zero the width
and padding instead of hiding the cells. Hiding them the obvious way silently
crushes the Vendor column to nothing.

### In the zip: `invoices.csv`

Columns below are exactly what `backend/extract.py` yields today — checked
against the real payloads in `.data/`, not invented. Order matters: an
accountant reads left to right and stops when they have what they need.

**Accounting — the block that gets used**

| Column | From | Example |
| --- | --- | --- |
| `invoice_number` | `invoice.invoice_number` | `1000376323` |
| `issued_on` | `invoice.date` | `2026-08-03` |
| `vendor` | `invoice.issuer` | `Bolt Operations OÜ` |
| `vendor_vat_number` | `invoice.vat_number` | `BG3170069438` |
| `vendor_company_number` | `invoice.company_number` | `14532901` |
| `currency` | `invoice.currency` | `EUR` |
| `amount_net` | `invoice.amount_untaxed` | `1.36` |
| `amount_vat` | `invoice.amount_tax` | `0.27` |
| `amount_total` | `invoice.amount` | `1.63` |
| `payment_reference` | `invoice.reference` | `BG3170069438-1BG-1000376323` |
| `service_date` | `invoice.service_start` | `2026-08-03 18:00` |
| `description` | `invoice.desc` | `Invoice from Bolt Operations OÜ` |

`service_date` earns its place: it is when the thing was *bought*, which can
fall in a different VAT period from when it was *invoiced*.

**The file — so a row can be tied to a PDF without opening it**

| Column | From | Example |
| --- | --- | --- |
| `file` | zip entry name | `2026-08-03__bolt__1.63EUR.pdf` |
| `file_bytes` | `document.bytes` | `30903` |
| `file_sha256` | `document.sha256` | `96811b22…` |

**Provenance — the audit trail, already computed, free to include**

| Column | From | Example |
| --- | --- | --- |
| `source` | `source.kind` / `document.origin` | `email-body`, `attachment`, `linked` |
| `source_mailbox` | `email.mailbox` | `kiraesq124@gmail.com` |
| `email_subject` | `email.subject` | `Fwd: Your Bolt Scooter ride on Monday` |
| `email_received` | `email.date` | `2026-08-10T14:26:27Z` |
| `email_message_id` | `email.message_id` | `<CALnsD3Y…@mail.gmail.com>` |
| `extracted_at` | `extraction.extracted_at` | `2026-08-13T08:56:16Z` |
| `extracted_by` | `extraction.tool` + `template_name` | `invoice2data 1.0.1 / bolt_invoice_bg.yml` |

The last two are how a disputed row gets settled: `email_message_id` points at
the exact message the figure came from, and `extracted_by` names the template
that read it. When a number looks wrong, the question is always *where did this
come from* — and the answer costs nothing to carry.

**Half these columns will be empty, and that is the honest case.** Of the three
real Bolt invoices on disk, two were parsed from the PDF and carry the invoice
number, the net/VAT split, the company number, the reference and the service
time. The third is a ride receipt read out of the mail body: `bolt_ride_receipt`
does not even *require* an invoice number, because Bolt's receipts do not carry
one, so that row has issuer, date, amount, currency and VAT number and nothing
else. Every column has to render blank without looking broken — a dash on the
page, an empty cell in the CSV.

## Thumbnails

Rendered **once at extraction**, in `process.py`, right after the document is
stored: page 1 → ~240px WebP written next to the PDF as `thumb.webp`. Page one
of an invoice is recognisable at that size — logo, layout, big total — which is
the highest signal-per-pixel the preview can offer, and it costs the client
nothing.

No new PDF engine: **pypdfium2 is already a dependency** (it is invoice2data's
text backend, `pyproject.toml`), and `page.render(scale=…)` gives the bitmap.
The one addition is **Pillow**, to encode it — `bitmap.to_pil()` raises without
it. That also sidesteps PyMuPDF, whose AGPL licence is a decision this repo does
not need to make for a thumbnail.

`GET /s/{token}/thumb/{id}` falls back to rendering on first request when the
file is missing, so invoices extracted before this shipped still show a
thumbnail and no backfill migration is needed.

**The strip is exactly five and a count** — `[▤][▤][▤][▤][▤] +32 more` — and it
does not scroll. Five is enough to recognise a batch; a scrolling strip would
buy nothing and cost lazy loading, a scroll affordance and a horizontal
virtualization story for something nobody flicks through. Five thumbnails means
five requests, so no image on this page is ever lazy. The sheet below lists all
37 by name in any case, and past ~50 rows *it* virtualizes.

## Sending mail

Unipile already holds the mailbox credentials and already does mail transport
(`backend/unipile.py`), so this is `POST /api/v1/emails` with the chosen
`account_id` — no second OAuth, no Gmail client to write. `backend/gmail.py` is
still a placeholder and stays one. The id has to be checked against
`accounts.list_connected()` on the way through: it arrives from the browser, and
the only thing that may send as a mailbox is that mailbox's owner.

- **From:** a connected mailbox. The recipient sees a name they recognise,
  which is most of why this beats a no-reply link.
- **Reply-To:** the same address, so a reply reaches a human.
- **Which mailbox, when there are several.** The From row **states the answer**
  — the address as text, the way it reads on a sent message — with a caret
  button beside it that opens the other connected mailboxes. Not a `<select>`:
  a form control frames a settled fact as a question, and the resting state
  should say *this goes out as martin@kirov.dev*, not *choose a sender*.
  The caret is rendered **only when `/accounts` returns more than one**, since a
  control that leads nowhere is worse than no control. The menu keeps the
  current mailbox in the list and ticks it, so it answers "which am I on?" as
  well as "what else is there?". Default to the last mailbox this browser sent
  from (`localStorage`), falling back to the first connected, so the choice is
  asked once rather than every time.
- **The user's only input is the address.** No note field: an optional message
  box is a decision every sender then has to make, and the draft already says
  everything the recipient needs. One field, one button.

### The mail itself

Shaped like a receipt, because that is the genre a recipient already knows how
to read: a branded band, one heading, a short label/value block, one action.

What it deliberately does *not* carry: thumbnails, the vendor list, a total, a
second call to action, footer links. The page has all of that, and an inbox is
not where anyone reviews 37 invoices — the mail's whole job is *who sent this,
what is it, where do I get it*. Dropping the images also drops the third of mail
clients that block them by default, so nothing important arrives as an empty
box, and dropping the closing link rows leaves exactly one thing to click.

`email.html` beside this file is the rendered draft — 600px, tables, inline
styles, no external CSS, plain-text alternative always, because that is what
mail clients survive.

### Previewing it

The composer renders **that same document in an iframe**, under the To field.
Not a mock-up of the mail and not a description of it: the bytes the API is
about to send. Sending something in your own name, from your own address, to
your accountant is exactly the case where "trust me, it looks fine" is not good
enough — and a preview that can drift from the real template is worse than
none, because it is believed.

## Failure states worth having

- **Revoked link.** The page says so plainly and offers nothing else. Not a 404
  — the recipient knows the link once worked, and pretending otherwise reads as
  a bug.
- **Invoice with no document.** Already a real case: some invoices were read out
  of an email body. Its row reads *no document* in the document column, and if it
  lands in the first five it shows a text-only thumbnail; it rides along in
  `invoices.csv`, so it is still part of the batch. The header counts
  **invoices** and the last line names how many are documents — "37 files" would
  be a number that does not survive a recount of the zip.
- **Send failed.** Composer stays open with the address intact and the Unipile
  detail shown. The link is already live either way — mail is the optional half.

---

## Build order

1. `shares` table + `POST /shares` + `GET /s/{token}` manifest.
2. Share button and popover in `InvoiceTable` toolbar.
3. Share page: summary, sheet, zip download. *Shippable here.*
4. Thumbnails at extraction + the five-up strip.
5. Composer, the draft, and `POST /s/{token}/email`.
6. Revoke, and virtualization past 50 rows.
