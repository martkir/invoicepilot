# Notes

Open decisions and things to pick up later. Nothing here is built yet; when a
note turns into a change, it moves into [`design.md`](design.md) and out of this
file.

---

## Replace revoke with a 7-day TTL

**Decided 2026-08-14.** Remove revoke from the flow. Shareable links get a
default TTL of 7 days at creation; after that they expire on their own.

### Why

Revoke is the only owner-side action the recipient-facing link carries, and it
pays for itself badly. It drags along a whole screen
([`09-revoked.html`](09-revoked.html)), a step in the flow map, and most of the
reason the owner key exists at all — [`index.html`](index.html) currently
explains the key as the thing that "gates sending and revoking". It also asks
the owner to remember a link exists and come back to kill it, which is work the
link should be doing itself.

A TTL answers the same question — how does a link stop working? — without an
action. Today the answer is "live until revoked", which means in practice most
links live forever, because nobody goes back.

### What it touches

- [`09-revoked.html`](09-revoked.html) — the screen goes, or becomes an
  *Expired* screen. Probably the latter: the state still exists, only its cause
  changes. Worth deciding whether expired keeps the neutral treatment revoked
  had.
- [`index.html`](index.html) — step 13 and the "owner clicks Revoke" arrow out
  of preview; the security line at the top of the notes column that reads "no
  expiry, password, or permission levels; live until revoked"; the two passages
  explaining the owner key.
- [`13-not-found.html`](13-not-found.html) — defines itself against revoked
  ("revoked means it worked once, this means it never did"). The distinction
  survives with expiry substituted, but the copy needs rewriting.
- The owner key in `localStorage` — it still gates sending, so it stays, but the
  rationale in `index.html` is now half wrong.
- [`design.md`](design.md) and [`audit.md`](audit.md) — prose only.
- The data model in [`../share-flow/design.md`](../share-flow/design.md) — a
  `revoked_at` becomes an `expires_at`, set at creation rather than on an
  action. That is the one real behavioural change; everything above is surface.

### Still open

- **Is 7 days configurable at creation, or fixed?** Fixed is simpler and matches
  the flow's existing refusal of expiry/password/permission dials. A picker on
  [`02-link.html`](02-link.html) is the obvious place if it becomes a choice.
- **Does the owner get a way to kill a link early?** Dropping revoke means no.
  If that turns out to be needed, it comes back and the TTL is additive rather
  than a replacement.
- **Does the recipient see the expiry?** Showing "expires in 6 days" on
  [`07-recipient.html`](07-recipient.html) sets an expectation and prompts them
  to download now. Not showing it keeps the page clean.
- **What happens to links already live when this ships?** Prototype-only for
  now, so nothing — but the answer matters if any exist by then.

### Older versions

`../share-flow`, `../share-flow-v2` and `../share-flow-v3` all carry the same
revoke screen. Treat them as historical snapshots and leave them alone unless we
decide otherwise.
