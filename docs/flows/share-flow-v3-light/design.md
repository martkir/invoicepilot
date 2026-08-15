# Share flow v3: what this version specifies

The flow itself is unchanged, and its specification stays where it is.
[`../share-flow/design.md`](../share-flow/design.md) is still the document for
the data model, the routes, the CSV columns, thumbnail generation, the mail
transport, and every argument about what the flow does and does not do.
[`../share-flow-v2/design.md`](../share-flow-v2/design.md) is still the
document for the four states v2 added. Neither moved, and duplicating either
here would only give it somewhere to drift.

This file covers what v3 adds on top: the design system the screens are built
on, the layout decision that came with it, and what shipping this means for the
app. The diagnosis that produced it is in [`audit.md`](audit.md); the screens
are in [`index.html`](index.html), and [`viewer.html`](viewer.html) pages
through them one at a time.

---

## The system

Mercury light, from
[`.claude/skills/mercury-ui-light`](../../../.claude/skills/mercury-ui-light/SKILL.md):
light, strictly flat, one electric-blue accent, Geist and Geist Mono, pill
interactives. It replaces the warm light system v2 proposed, keeping the
brightness and changing everything else. Section numbers throughout this folder
refer to that skill.

This is the light twin of [`../share-flow-v3`](../share-flow-v3/design.md).
The two folders hold the same fourteen screens, the same markup and the same
copy; the theme lives entirely in `tokens-v3.css`, plus four comments and one
accent step elsewhere that name a direction.

Dials: `DESIGN_VARIANCE` 6, `MOTION_INTENSITY` 3, `VISUAL_DENSITY` 6.

### The stylesheets, and what each is for

Every screen links five sheets, in this order:

| File | Owner | Fate on ship |
| --- | --- | --- |
| `frontend/src/styles/tokens.css` | the app | replaced by the `:root` block of `tokens-v3.css` |
| `frontend/src/styles/dashboard.css` | the app | absorbs `reskin.css` |
| [`tokens-v3.css`](tokens-v3.css) | this folder | *becomes* `tokens.css` |
| [`reskin.css`](reskin.css) | this folder | folded into `dashboard.css`, then deleted |
| [`flow.css`](flow.css) | this folder | ships as the share UI's own stylesheet |

The order is what makes the folder honest. The shipped sheets are linked
untouched and then overridden, so these mockups render the *real* product in
the new system. Nothing was forked to make the screens look better than the
thing they describe. `reskin.css` contains no new components, only a diff
against ones that already exist; `flow.css` contains no rule for anything that
already ships.

`dashboard.css` turns out to be almost entirely token-driven, so most of the
inversion happens in `tokens-v3.css` alone: the eight places it hard-codes a
colour, the two shadows, the radii that predate the scale, the weights above
500 and the uppercase labels are what `reskin.css` is for.

### Tokens worth knowing

- **Type.** Geist for text, Geist Mono for every figure: money, dates, counts,
  byte sizes, filenames, tokens. Anything compared down a column is tabular.
  Mercury's scale verbatim, with one clamp on `display-md` so the filename
  does not overflow a phone. Nothing above weight 500, nothing below 12px,
  nothing in upper case, no positive tracking, and no third family anywhere in
  the folder including this documentation.
- **Colour.** Five working tokens carry the screens: `--canvas`, `--paper`,
  `--ink`, `--ink-soft`, `--primary`. Mercury ships two text colours and this
  folder uses two; the third level of hierarchy is size, not another grey.
- **Derived surfaces.** `--rule`, `--rule-soft` and `--paper-hi` are
  `color-mix` compositions of Section 1 tokens rather than new colours.
  They exist because Mercury's `--hairline` is the same hex as `--paper`,
  which is right for a border on the canvas and invisible for a divider inside
  a card, and a 37-row manifest needs that divider.
- **Status.** One colour, `--danger: #b3261e`, per Section 1.B. No success
  colour, no warning colour. It appears twice in the entire flow. This is the
  one token whose value cannot be shared with the dark twin: a light red is
  2.4:1 on this canvas.
- **Depth.** None. All four shadow tokens resolve to `none` and are kept only
  so an inherited `var(--sh-2)` resolves to nothing. Elevation is the
  `--canvas` / `--paper` / `--paper-hi` contrast ladder plus hairlines and
  space.
- **Radii.** Mercury's six steps, spent by one rule: pill for interactive,
  `--r-lg` for containers, `--r-sm` or `--r-xs` inside. The checkbox is the
  one documented exception and `reskin.css` says why.
- **Motion.** Two durations and two easings, no spring. Nothing loops.
- **Aliases.** `--red-*`, `--white`, `--page`, `--muted` and `--ink-2` are
  repointed at Mercury values so the shipped `dashboard.css` picks up the new
  palette without being edited. New code should use the Mercury names.

**The font is the one external dependency these screens have.** For production
that becomes `@fontsource-variable/geist` and `@fontsource-variable/geist-mono`
rather than a Google Fonts link: a share page that stalls waiting on
`fonts.gstatic.com` is a share page that stalls. The stack falls back to the
system fonts, so an offline open degrades to roughly what v1 looked like.

---

## The one layout rule worth writing down

**The page is two columns, and the left one sticks.**

v2's rule was that exactly one element lifts: the document card overlapped the
header band by 44px, and three layered shadows said which one was in front.
Flat, that overlap is a misaligned element, so the hierarchy had to come from
somewhere else.

- **The rail (320px)** is what the batch *is* and the one thing to do with it:
  the `zip` chip, the filename at display size, four labelled facts on a
  hairline rhythm, `Download all`, and the sentence naming what lands in the
  folder. For the owner it also carries the live state with the date the link
  ends, the name recipients will see it from with one control to correct it,
  and `Send by email`.
- **The right column** is what is inside the batch: the composer when it is
  open, then the manifest card with its `pdf` part and its `csv` part.

Because the rail is sticky, the owner block and `Download all` are reachable
from row 37 without scrolling back, which is what v2 used a second sticky element
for. That element is gone, and with it the `--sticky-top` variable the sheet's
own sticky header had to read off the page.

Below 1100px the grid is one column and the rail stops sticking: on a phone the
rail and the manifest are a full screen apart anyway.

---

## The screens whose content changed

Everything else is the same markup in new tokens. These carry a decision.

### The opened row, [`01b-row.html`](01b-row.html)

A branch off step 1, not a step through it: nothing in the share flow passes
through this screen. It is here because the flow starts on the invoice table
and the table's other interaction had never been drawn in Mercury. The
direction is the one picked in
[`../../ui-sketches/invoice-preview/`](../../ui-sketches/invoice-preview/index.html),
which is `e-refined`: the row expands in place, so its neighbours stay readable
and there is nothing to dismiss.

The panel answers one question, whether the parser read the document
correctly, so it puts the document beside the fields taken off it. Three
decisions follow from that.

**The open row drops the accent.** A ticked row is `--primary-soft`, and the
shipped rule drew an open row in the same tint, so two unrelated states were
one colour. Disclosure is neither an action nor a selection, so the row and its
panel take `--canvas-deep`: the page colour, cut into the card as a well, which
also makes the two read as one block rather than a row with a stranger
underneath. A row that is both ticked and open still shows the accent, because
that half of it is still a selection.

**The document is a thumbnail, not a viewer.** No width this panel can afford
makes an A4 page readable, so the box is sized to be recognised, at the same
3:4 proportion as the tiles on the share page. Reading the document is what
opening it full size is for. In the draft it renders the state where the page
has not arrived, which is the vendor's mark on a blank sheet; production puts
the invoice's own PDF in that box.

**The amount leads and is not repeated.** It is the figure the row was opened
to check, so it is the panel's headline with net and VAT beside it; a second
copy four rows down the list would be two answers to one question. Everything
else is a label/value row on the hairline rhythm the rail's facts already use,
with identifiers in mono so they can be read a character at a time. Fields the
extractor came back empty on are not rendered at all: templates are per issuer,
and a fixed list would report the template's coverage rather than the invoice.

Landing it needs three things `InvoiceDetail` does not emit today: a wrapper
around each heading and its pairs, an `is-id` class on identifier values, and
the amount lifted out of the pair list into a block of its own. The rest is
`reskin.css`.

### The document tiles, [`03-preview.html`](03-preview.html)

Six cells for six things: five documents and the count of the other 31. Each
tile is the thumbnail panel the product renders **when the page-1 render is
missing**, which is the vendor's initials on a plain panel; production drops an
`<img>` into the same box and the initials stay behind it as the alt case.

This replaces v2's fan of overlapped, rotated sheets, which read as a stack of
paper only because of the shadow between each sheet. It also fixes an
off-by-one: v2's tail said `+32` under a heading that said 36 documents.

The invoice with no document is not in this strip. The strip is the PDFs; that
row belongs to the manifest below, which says `no document` in words.

### The owner block, [`03-preview.html`](03-preview.html)

The only difference between the owner's page and everyone else's, now at the
foot of the rail rather than in a bar across the top of the window. One status
dot, static, because "this link is live" is real state and Section 7.A allows
exactly that.

Three things, in the order the owner asks about them: how long the link lives,
whose name is on it, and how to send it.

**The live line names a date.** `Revoke` is gone — [`notes.md`](notes.md)
replaced it with a fixed seven days on 2026-08-14 — and what replaced it is not
another control but a fact. A link that ends on its own needs no switch, and
the date is worth more on the page than the switch was. It is the same sentence
in three places: the popover that mints the link, this block, and the footer of
the mail.

**The name is shown, and it is correctable.** Everything the recipient is told
about who shared with them has to be carried by the link itself, because they
have no account. Both fields come off the connected mailbox when the link is
made: its display name if it has one, and otherwise the local part of the
address — `martinvkirov` from `martinvkirov@gmail.com`. That is recognisable
enough to send under and wrong enough to want fixing, so the block states it
rather than hiding it, with one quiet control beside it.

### Correcting the name, [`03b-name.html`](03b-name.html)

A branch off the share page, usually skipped. The edit happens in the rail, in
place, with the page it changes still behind it — the name is shown to people
the owner cannot see, so it belongs beside the sentence that says who those
people are.

Only the name is editable. The address under it is the mailbox that will
actually send, and a typed address would make that line a claim rather than a
fact. The correction is kept for the next link too, so this is a screen most
people see once, if at all.

### The composer, [`04-compose.html`](04-compose.html)

Labels above their fields, which is the shape Section 4.6 asks for and which
v2 did not have. The From row is still a statement with a caret rather than a
`<select>`, and its label is still a `<span>`, because a `<label for>` pointing
at no control promises a screen reader something that is not there.

### The two error states, [`12-invalid.html`](12-invalid.html) and [`08-send-failed.html`](08-send-failed.html)

The only two places `--danger` appears. v2 drew both in the accent, which read
as an error only because the accent was a red; against an electric blue the
same treatment says nothing at all.

Neither the mechanism nor the copy changed: client-side validation on blur with
`aria-invalid` and `aria-describedby`, and the Unipile detail shown verbatim
because "something went wrong" is not something anyone can act on.

### The email, [`email.html`](email.html)

Light, on the same canvas as the product, with the palette inlined as `style`
attributes because mail clients strip `<link>` and most `<style>`. That is the
one carve-out Section 1.A allows, and the literals are Mercury's own.

The branded band is no longer a slab of the accent: the accent is rationed to
real actions, and this mail has exactly one, its button.

---

## Build order

Unchanged from `../share-flow/design.md`. The redesign does not reorder the
work, it changes what each step looks like when it lands.

1. `shares` table + `POST /shares` + `GET /s/{token}` manifest.
2. Share button and popover in `InvoiceTable`'s toolbar.
3. Share page: rail, manifest card, zip download. *Shippable here.*
4. Thumbnails at extraction, filling the tiles.
5. Composer, the draft, and `POST /s/{token}/email`.
6. Correcting the display name (`PATCH /s/{token}`), and virtualization past
   50 rows.

The opened row is not in that list because it is not part of the share flow.
It rides along with the reskin, apart from the three markup changes named
above.

The token and reskin layer (`tokens-v3.css` + `reskin.css`) is independent of
all six and can go first or last. It touches every screen in the product, so it
wants to be its own commit either way. Unlike the dark twin it does not invert
the app, so it is the cheaper of the two to land: the surfaces stay bright and
only their hue, their flatness and their scales change.
