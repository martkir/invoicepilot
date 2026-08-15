# Share flow v3 light, annotated: what this folder is

The fifteen screens of [`../share-flow-v3-light`](../share-flow-v3-light/design.md),
with every element that a request fills marked, and a panel beside each screen
naming the endpoint, the table and the query behind it. Open
[`index.html`](index.html) for the map, or any screen for the screen.

For the backend on its own, without the screens around it, read
[`backend.md`](backend.md): the table, the eleven routes and every query, in
plain terms. This file is about how the annotation is made and what it turned
up. [`revisions.md`](revisions.md) is the log of what changed between drafts of
the flow, and the commit to check out to see any of them again.

This folder owns **no design**. It owns one stylesheet, one generator and this
file. The screens are read out of the design folder, the three stylesheets are
linked back at it untouched, and the only edit made to the markup is a
`data-pin` attribute on the elements being described. An annotated screen
therefore renders exactly what the design folder renders — which is the same
rule `../share-flow-v3-light` keeps against the shipped `dashboard.css`, one
level up.

---

## Where the specification actually lives

Worth writing down, because it took a search. v3-light's `design.md` defers the
data model, the routes, the CSV columns, the thumbnails and the mail transport
to `../share-flow/design.md` and `../share-flow-v2/design.md`. **Neither path
resolves.** Both documents are real and unchanged, one directory further down:

- [`../draft/share-flow/design.md`](../draft/share-flow/design.md) — the data
  model, the routes, the CSV, the thumbnails, the mail. Still the document.
- [`../draft/share-flow-v2/design.md`](../draft/share-flow-v2/design.md) — the
  four states v2 added.

The links in v3-light are off by one level. Nothing is missing; the folder just
moved under `draft/` after they were written.

## What the wiring says, in one paragraph

One new table, `shares`, holding a token, a hashed owner key, a JSONB snapshot
of invoice ids, the name and address of the mailbox it was made from, and two
timestamps. Eleven endpoints touch these screens and **four of them already
ship** — `/api/accounts`, `/api/scan`, `/api/invoices` and
`/api/invoices/{id}/document`, read off `backend/services/api.py` rather than
imagined. The seven new ones are all scoped under `/api/shares` or
`/api/s/{token}`, and every one of them looks the share up by primary key.
There is no query in the flow that is not a primary-key lookup or an
`id = ANY(...)` over the snapshot.

## The two amendments this map produced

Both started as pins nothing could answer, and both are now drawn. The map is
where they were found, which is the argument for annotating a flow at all: the
questions came out of asking *what request fills this element?* one element at
a time.

**Revoke became a 7-day TTL.**
[`../share-flow-v3-light/notes.md`](../share-flow-v3-light/notes.md) decided it
on 2026-08-14 and the screens caught up on 2026-08-15. `shares` carries
`expires_at` rather than `revoked_at`, set at creation; there is no
`DELETE /s/{token}`; the owner block states a date where a button used to be;
and `09-revoked.html` is now
[`09-expired.html`](09-expired.html), same page and same 410, different cause.

One consequence is load-bearing: **the manifest query does not filter on
expiry.** `WHERE expires_at > now()` would fold an expired share into a missing
one and cost the page the difference between 410 and 404 — which is the
difference between [`09-expired.html`](09-expired.html) and
[`13-not-found.html`](13-not-found.html). The row is fetched, then the expiry
is compared.

**A share carries who made it.** `owner_name` and `owner_email` are written at
creation from the connected mailbox — its own display name if Unipile has one,
otherwise the local part of the address — and frozen with the snapshot. The
owner can correct the name on [`03b-name.html`](03b-name.html), which is the
one `UPDATE` in the flow and the reason the owner key outlived revoke.

## What nothing answers yet

Nothing. Five pins were flagged as open questions when this folder was first
generated; all five are answered, and each keeps its entry on the screen that
raised it, marked *Answered* rather than deleted. They are collected at the
foot of [`index.html`](index.html).

That the five were three problems is worth keeping in view, because it is the
shape this kind of review tends to have:

**The owner's identity**, raised twice — on
[`03-preview.html`](03-preview.html) and on
[`07-recipient.html`](07-recipient.html). The recipient's copy is what settled
it: they have no account and can be shown nothing the manifest does not carry,
so the identity has to travel inside the link. Deriving it at read time from
the mailbox on the snapshot's invoices was the alternative, and it is wrong for
a reason the screens make obvious — the mailbox that *received* an invoice is
not necessarily the person sharing it.

**The composer's preview**, on [`04-compose.html`](04-compose.html): a real
`<iframe>` whose `src` no specified route could serve.
`GET /api/s/{token}/email/preview` exists now, which keeps the design's own
rule that the preview is the bytes the send will use.

**Revoke**, raised twice, as above.

## How it is generated

```
python3 docs/flows/share-flow-v3-light-annotated/annotate.py
```

Re-run it after `../share-flow-v3-light/build.py`. Every pin names a substring
of the real markup, and **an anchor that stops matching is a hard failure**:
the script exits naming the pin, the element and the file to re-read. A map
that is silently 80% complete is worse than one that refuses to build, and
without that rule this folder would drift from the screens within one redesign.

The facts live in one table in `annotate.py`. `ENDPOINTS` defines each route
once — method, path, tables, SQL, note — and `SCREENS` pins elements at it, so
the manifest query is written once and appears on the six screens that use it.
The screens, the contact sheet and the endpoint table are all emitted from
that one structure.

### The viewer

[`viewer.html`](viewer.html) pages through all sixteen screens with the arrow
keys, the panel travelling with each one. It is the design folder's viewer with
**one thing replaced: the screen list.**

That list is the one part it cannot keep. The original discovers screens by
fetching `index.html` and reading `.step` sections off the contact sheet, so
titles and captions never have to be maintained twice — and this folder's
`index.html` is a map rather than a flow diagram, with no `.step` sections in
it. Left alone the parse would fail into a hard-coded fallback that nothing
keeps in step, which is the drift that mechanism exists to prevent. Here the
list has a real single source — the same table that places the pins — so it is
written out rather than rediscovered.

What it gains from being generated: the chip in the bar counts the screen's
pins, and the caption bar carries the screen's routes, the number of open
questions on it and the number that have been answered. Paging through the flow
reads as the flow *and* as its wiring.

The order is the flow's, not the filenames' — loading before the page it stands
in for, the mail between sending it and the recipient opening it. It is the
order that viewer already carried, plus the two branch screens `01b-row.html`
and `03b-name.html`, each paging one step after the screen it opens out of.

### The one file that is not annotated

**`email.html`** is copied verbatim. `04-compose.html` loads it in an
`<iframe>`, and a docked panel inside that frame would annotate the preview
instead of the composer. It still pages in the viewer, where the caption says
why it carries no pins; what sends it is pin 5 on the composer.

## The annotation layer itself

`annotations.css` is the only stylesheet this folder owns, and it adds only
pins and the panel.

- **The pin is drawn in `::after`,** so no node is inserted into the markup and
  no product box changes size. `annotate.py` adds one attribute and nothing
  else.
- **The pins are amber**, which is deliberately outside Mercury. The flow's one
  accent is electric blue and its one status colour is red; a third meaning
  drawn in either would read as part of the product rather than as a note on
  it.
- **Five selectors are never pinned** — `.rail`, `.doc-card`, `.share-pop`,
  `.from-menu` and `.sheet thead th`. The badge needs `position: relative` on
  what it marks, and applying that to the sticky rail would unstick the left
  column. The stylesheet carries a `:not()` guard as well, so a pin added later
  cannot break the layout it documents.
- **Below 1400px the panel stops being a panel** and becomes the last section
  of the page. The pins do not move.
