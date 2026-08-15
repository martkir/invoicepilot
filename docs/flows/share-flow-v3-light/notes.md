# Notes

Open decisions and things to pick up later. Nothing here is built yet; when a
note turns into a change, it moves into [`design.md`](design.md) and out of this
file.

---

## Replace revoke with a 7-day TTL — *drawn 2026-08-15*

**Decided 2026-08-14, drawn 2026-08-15.** Removed from the flow. Links get a
fixed 7 days at creation and expire on their own.

It is out of this file now, in the sense that matters: the screens no longer
draw a control that was going. What it left behind is in
[`design.md`](design.md#the-owner-block-03-previewhtml) and in
[`../share-flow-v3-light-annotated/revisions.md`](../share-flow-v3-light-annotated/revisions.md),
which names the commit to go back to if any of this is wrong.

What it touched, for anyone reading the diff: `09-revoked.html` became
`09-expired.html` with a clock in place of the crossed circle; the owner block
lost the button and gained the date; the popover, the mail footer and
`13-not-found.html` all stopped promising that someone can turn the link off;
step 13 of [`index.html`](index.html) is reached by *seven days pass* rather
than by a click.

Two of the four questions this note left open are answered, and one of the two
that are not has moved:

- **Is 7 days configurable at creation, or fixed?** *Fixed.* Same reason the
  flow refuses expiry, password and permission dials: it is a decision the user
  would have to make before getting their link.
- **Does the owner get a way to kill a link early?** *No.* If it turns out to be
  needed it comes back as `UPDATE shares SET expires_at = now()`, additive
  rather than a replacement — no new column, no new state.
- **Does the recipient see the expiry?** *Still open, and now half-decided by
  accident:* the mail footer names the date, so anyone who arrives from the mail
  has been told. [`07-recipient.html`](07-recipient.html) itself still does not
  say it. Deciding it is a one-line change to `masthead()` or to `facts()`.
- **What happens to links already live when this ships?** Still nothing to
  answer: prototype only, no live links.

---

## Whose name is on a share

**Decided 2026-08-15.** Raised by the wiring map, which found that
`07-recipient.html` greets the reader by a name the `shares` table had nowhere
to keep.

Two fields, `owner_name` and `owner_email`, written when the link is made and
frozen with the snapshot. They come off the connected mailbox: its own display
name if Unipile carries one, otherwise the local part of the address
(`martinvkirov` from `martinvkirov@gmail.com`). The owner can correct the name
on [`03b-name.html`](03b-name.html), and the correction is kept for the next
link. The address is not editable.

### Still open

- **Which mailbox, when two are connected?** Drawn as the first account.
  `POST /shares` takes an optional `account_id` for the same reason the composer
  has a From picker, but no screen offers the choice at creation, and it is not
  obvious that one should: the link is not a message.
- **What if no mailbox is connected at all?** Cannot happen in practice — the
  invoices got here somehow — but the fields are `NOT NULL`, so the route needs
  an answer rather than a crash. Probably an empty name and a masthead that
  degrades to *Shared with you*.
