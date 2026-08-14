# Share flow v2 — what this version specifies

The flow itself is unchanged, and its specification stays where it is:
[`../share-flow/design.md`](../share-flow/design.md) is still the document for
the data model, the routes, the CSV columns, thumbnail generation, the mail
transport, and every argument about what the flow does and does not do. None
of it moved. Duplicating it here would only give it somewhere to drift.

This file covers what v2 adds on top: the design system the screens are built
on, the four states v1 did not draw, and what shipping this means for the app.
The diagnosis that produced it is in [`audit.md`](audit.md); the screens are in
[`index.html`](index.html).

---

## The stylesheets, and what each is for

Every screen links four sheets, in this order:

| File | Owner | Fate on ship |
| --- | --- | --- |
| `frontend/src/styles/tokens.css` | the app | replaced by the `:root` block of `tokens-v2.css` |
| `frontend/src/styles/dashboard.css` | the app | absorbs `redesign.css` |
| [`tokens-v2.css`](tokens-v2.css) | this folder | *becomes* `tokens.css` |
| [`redesign.css`](redesign.css) | this folder | folded into `dashboard.css`, then deleted |
| [`flow.css`](flow.css) | this folder | ships as the share UI's own stylesheet |

The order is what makes the folder honest. The shipped sheets are linked
untouched and then overridden, so these mockups render the *real* product in
the redesigned palette — nothing was forked to make the screens look better
than the thing they describe. `redesign.css` contains no new components, only
a diff against ones that already exist; `flow.css` contains no rule for
anything that already ships.

### Tokens worth knowing

- **Type.** Geist for text, Geist Mono for every figure — money, dates, counts,
  byte sizes, filenames, tokens. Anything that gets compared down a column is
  tabular. Sizes are a seven-step scale from `--t-2xs` to `--t-display`, the
  last a `clamp()`.
- **Colour.** One accent (`--accent-600: #A8382C`) with two darker and three
  lighter steps; one warm grey family from `--ink` to `--page`; `--paper` for
  card surfaces, which is not the same value as `--white`. The `--red-*` names
  are kept as aliases because `dashboard.css` spends them everywhere.
- **Depth.** Three layered, warm-tinted shadows plus `--edge`, the 1px inner
  highlight along a raised surface's top edge. One light source: every offset
  is `+y`.
- **Radii.** Five steps. Tight on things inside other things, soft on
  containers.
- **Motion.** Two durations (`130ms` colour, `220ms` movement) and two easings,
  one of them a spring. Everything that moves moves on `transform` or
  `opacity`. A reduced-motion block turns all of it off, including the
  skeleton shimmer.
- **Grain.** An inline `feTurbulence` data URI at 3.5%, fixed, over the page
  and again inside the header band. No network request, no image file.

**The font is the one external dependency these screens have.** For production
that becomes `@fontsource-variable/geist` rather than a Google Fonts link — a
share page that stalls waiting on `fonts.gstatic.com` is a share page that
stalls. The stack falls back to the old system fonts, so an offline open
degrades to roughly what v1 looked like.

---

## The four new states

Everything here is a state of a route that already exists in
`../share-flow/design.md`. No new endpoint.

### Loading — [`10-loading.html`](10-loading.html)

`GET /s/{token}` has to return a manifest of up to several hundred rows. The
placeholder is shaped like the page it stands in for — band, fan, rows — so
the layout does not move when the data lands, and the shimmer runs on
`transform`. The band's real headings stay visible; only the values are
skeletons, because the page's *identity* is known before its contents are.

`aria-busy="true"` on the two regions being filled.

### Downloading — [`11-zipping.html`](11-zipping.html)

`GET /s/{token}/zip` is streamed and never assembled on disk, so the total is
known before the first byte: this is a **determinate** bar, and it names what
is being built (36 documents and the CSV). It replaces the download button in
place, so nothing on the page moves.

The share stays fully readable while it runs — the zip is a download, not a
mode.

### Invalid address — [`12-invalid.html`](12-invalid.html)

The composer's one field, checked in the browser on blur, before
`POST /s/{token}/email` is called. `aria-invalid` and `aria-describedby` on the
input, an inline sentence that names the problem and guesses the fix, Send
`aria-disabled` while it stands. Never `window.alert`, and never a coloured
border with no sentence beside it.

Server-side validation does not go away: this is the cheap half that saves a
round trip, not a substitute for the transport's own rejection, which is what
[`08-send-failed.html`](08-send-failed.html) renders.

### Nothing at this link — [`13-not-found.html`](13-not-found.html)

The 404 for a token that never existed. It is a separate page from *revoked*
on purpose: revoked means the link worked once and someone turned it off, and
telling those two apart is the difference between "ask Martin for a new one"
and "check what you pasted".

The likeliest cause is specific enough to name — a 22-character token broken
across two lines by an email client — so the page names it rather than saying
"page not found".

---

## The one layout rule worth writing down

**Exactly one element lifts.** The document card overlaps the header band by
44px; when the composer is open, the composer takes that overlap and the
document card sits normally below it. Two overlapping cards is a pile, not a
foreground, and a page with no overlap at all is the flat stack of bands v1
had.

The overlap collapses to zero under 780px, where the band and the card are a
full screen apart anyway and a negative margin only crowds them.

---

## Build order

Unchanged from `../share-flow/design.md` — the redesign does not reorder the
work, it changes what each step looks like when it lands.

1. `shares` table + `POST /shares` + `GET /s/{token}` manifest.
2. Share button and popover in `InvoiceTable`'s toolbar.
3. Share page: header band, sheet, zip download. *Shippable here.*
4. Thumbnails at extraction + the fan.
5. Composer, the draft, and `POST /s/{token}/email`.
6. Revoke, and virtualization past 50 rows.

The palette and type layer (`tokens-v2.css` + `redesign.css`) is independent of
all six and can go first or last. It touches every screen in the product, so it
wants to be its own commit either way.
