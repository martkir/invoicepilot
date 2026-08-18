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

Mercury, from [`.claude/skills/mercury-ui`](../../../.claude/skills/mercury-ui/SKILL.md):
dark, strictly flat, one electric-blue accent, Geist and Geist Mono, pill
interactives. It replaces the warm light system v2 proposed. Section numbers
throughout this folder refer to that skill.

Dials: `DESIGN_VARIANCE` 6, `MOTION_INTENSITY` 3, `VISUAL_DENSITY` 6.

### The stylesheets, and what each is for

Every screen links five sheets, in this order:

| File | Owner | Fate on ship |
| --- | --- | --- |
| `services/web/src/styles/tokens.css` | the app | replaced by the `:root` block of `tokens-v3.css` |
| `services/web/src/styles/dashboard.css` | the app | absorbs `reskin.css` |
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
- **Status.** One colour, `--danger: #ff6b6b`, per Section 1.B. No success
  colour, no warning colour. It appears twice in the entire flow.
- **Depth.** None. All four shadow tokens resolve to `none` and are kept only
  so an inherited `var(--sh-2)` resolves to nothing. Elevation is the
  `--canvas` / `--paper` / `--paper-hi` contrast ladder plus hairlines and
  space.
- **Radii.** Mercury's six steps, spent by one rule: pill for interactive,
  `--r-lg` for containers, `--r-sm` or `--r-xs` inside. The checkbox is the
  one documented exception and `reskin.css` says why.
- **Motion.** Two durations and two easings, no spring. Nothing loops.
- **Aliases.** `--red-*`, `--white`, `--page`, `--muted` and `--ink-2` are
  repointed at Mercury values so the shipped `dashboard.css` renders dark
  without being edited. New code should use the Mercury names.

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
  folder. For the owner it also carries the live state, `Send by email` and
  `Revoke`.
- **The right column** is what is inside the batch: the composer when it is
  open, then the manifest card with its `pdf` part and its `csv` part.

Because the rail is sticky, `Revoke` and `Download all` are reachable from
row 37 without scrolling back, which is what v2 used a second sticky element
for. That element is gone, and with it the `--sticky-top` variable the sheet's
own sticky header had to read off the page.

Below 1100px the grid is one column and the rail stops sticking: on a phone the
rail and the manifest are a full screen apart anyway.

---

## The five screens whose content changed

Everything else is the same markup in new tokens. These five carry a decision.

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

Dark, on the same canvas as the product, with the palette inlined as `style`
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
6. Revoke, and virtualization past 50 rows.

The token and reskin layer (`tokens-v3.css` + `reskin.css`) is independent of
all six and can go first or last. It touches every screen in the product, so it
wants to be its own commit either way, and it is a bigger commit than v2's was:
it inverts the app from light to dark.
