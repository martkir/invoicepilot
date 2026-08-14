# Share flow v3 light, annotated: what this folder is

The fourteen screens of [`../share-flow-v3-light`](../share-flow-v3-light/design.md),
with every element that a request fills marked, and a panel beside each screen
naming the endpoint, the table and the query behind it. Open
[`index.html`](index.html) for the map, or any screen for the screen.

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
of invoice ids, and two timestamps. Ten endpoints touch these screens and
**four of them already ship** — `/api/accounts`, `/api/scan`, `/api/invoices`
and `/api/invoices/{id}/document`, read off `backend/services/api.py` rather
than imagined. The six new ones are all scoped under `/s/{token}`, and every
one of them looks the share up by primary key. There is no query in the flow
that is not a primary-key lookup or an `id = ANY(...)` over the snapshot.

## The amendment the screens predate

[`../share-flow-v3-light/notes.md`](../share-flow-v3-light/notes.md) replaced
revoke with a 7-day TTL on 2026-08-14. The wiring is annotated to that
decision: `shares` carries `expires_at` rather than `revoked_at`, set at
creation, and there is no `DELETE /s/{token}`.

The screens still draw Revoke, because they were drawn first. Rather than
quietly annotate a control that is going, the two places it appears — pin 8 on
[`03-preview.html`](03-preview.html) and the whole of
[`09-revoked.html`](09-revoked.html) — say so in the panel. A wiring map that
silently documented a route nobody intends to build would be worse than one
that argues with the screen it is drawn on.

One consequence is worth keeping when the screens are redrawn: **the manifest
query does not filter on expiry.** `WHERE expires_at > now()` would fold an
expired share into a missing one and cost the page the difference between 410
and 404 — which is the difference between
[`09-revoked.html`](09-revoked.html) and
[`13-not-found.html`](13-not-found.html). The row is fetched, then the expiry
is compared.

## What nothing answers yet

Five pins are flagged as open questions rather than descriptions. They are
collected at the foot of [`index.html`](index.html); three of them are one
problem each.

**The owner's identity.** [`03-preview.html`](03-preview.html) says *Your link
· martin@kirov.dev* and [`07-recipient.html`](07-recipient.html) says *Shared
with you by Martin Kirov · martin@kirov.dev*. `shares` as specified carries no
owner at all — not a name, not an address. Either the manifest derives it from
the mailbox on the snapshot's invoices, or the table gains a column. The
recipient's copy is the one that settles it: they have no account and can be
shown nothing the manifest does not carry.

**The composer's preview.** [`04-compose.html`](04-compose.html) has a real
`<iframe>`, and the design is explicit that it must show *the bytes the API is
about to send* rather than a mock-up. No route in any spec serves that, so
either `GET /s/{token}/email/preview` exists — the tenth endpoint in the map —
or the preview becomes a second template that can drift from the one that
sends, which is the outcome the design rules out by name.

**Revoke, twice**, as above.

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

[`viewer.html`](viewer.html) pages through all fifteen screens with the arrow
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
pins, and the caption bar carries the screen's routes and the number of open
questions on it. Paging through the flow reads as the flow *and* as its wiring.

The order is the flow's, not the filenames' — loading before the page it stands
in for, the mail between sending it and the recipient opening it. It is the
order that viewer already carried, plus `01b-row.html`, which the original list
omits because nothing in the flow passes through it. It is in this folder and
reachable, so it pages one step after the screen it opens out of.

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
