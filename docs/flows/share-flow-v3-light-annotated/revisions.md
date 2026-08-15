# Revisions

Every pass over this flow, newest last, with the commit to check out to see it
again. One entry per revision, not per commit: a revision is a decision or a
set of them landing together, and it usually takes more than one commit to
draw.

```
git checkout flow-r1     # or the commit named below
git checkout main        # back
```

Each revision is tagged as well as listed, because a tag survives a rebase and
a hash in a document does not. **The tag points at the last commit of the
revision**, so checking it out gives you that revision complete.

Nothing here is running code. Going back a revision costs nothing but the
checkout, which is the reason this file exists: it should be cheap to say *no,
the previous one was better.*

---

## r1 — the flow, and the wiring map over it

**`flow-r1` · [`739e1d1`](#) · 2026-08-14 to 2026-08-15**

Fourteen screens in [`../share-flow-v3-light`](../share-flow-v3-light/index.html),
and this folder over the top of them: every element that a request fills marked
with a pin, and a panel beside each screen naming the endpoint, the table and
the query behind it.

| Commit | What it did |
| --- | --- |
| `0ba7ace` | The v3-light screens and their contact sheet, alongside a dashboard reskin and the docker/just tooling. |
| `41b04f1` | This folder: `annotate.py`, `annotations.css`, the pinned screens, the map and the viewer. |
| `739e1d1` | [`backend.md`](backend.md) — the table, the routes and every query, without the screens around them. |

**What it produced, and why there is an r2.** Mapping each element to a route
turned up five pins nothing could answer, collected at the foot of the map.
They were three problems: the owner's identity (raised on two screens), the
composer's email preview, and Revoke (also two screens, already contradicted by
a decision in `notes.md`). The map argued with the screens it was drawn on
rather than annotating controls nobody intended to build.

**Go back here to see** the flow as first specified: `09-revoked.html`, a
Revoke button in the owner block, a `shares` table of five columns, and the
open questions still open.

---

## r2 — the five open questions, answered

**`flow-r2` · [`c05de29`](#) · 2026-08-15**

Every question r1 raised, decided and drawn. The three decisions:

**1. No revoke. Links expire.** Decided 2026-08-14 in
[`notes.md`](../share-flow-v3-light/notes.md), drawn now. A fixed seven days,
set at creation, and no way to end a link early.

- `09-revoked.html` → [`09-expired.html`](09-expired.html), with a clock in
  place of the crossed-out circle. Same page, same 410, different cause.
- The owner block's Revoke button became a **date**: *this link is live … it
  stops working on 12 July 2026*. What replaced the control is the fact the
  control would have been used to establish.
- The popover, the mail footer and `13-not-found.html` stopped promising that
  somebody can turn the link off.
- No `DELETE /s/{token}`; `expires_at`, not `revoked_at`.

**2. A share carries who made it.** `shares` gains `owner_name` and
`owner_email`, resolved from the connected mailbox when the link is made and
frozen with the snapshot — the mailbox's own display name if Unipile has one,
otherwise the local part of its address.

- The recipient's page can name a person: they have no account, so everything
  they are told has to have travelled inside the link.
- The owner block states the name, because the fallback is exactly the value
  somebody will want to fix. [`03b-name.html`](03b-name.html) is new: the edit,
  in the rail, in place.
- `PATCH /api/s/{token}` is the one `UPDATE` in the feature, gated by the owner
  key — which is why the key outlived revoke. The address is not editable.

**3. The email preview is the email.** `GET /api/s/{token}/email/preview`
exists, and the send calls the same renderer, so the composer's `<iframe>` is
the bytes Unipile will get rather than a look-alike that can drift.

**Also in this revision:**

- Answered pins are kept, not deleted: a pin that raised a question and had it
  settled reads *Answered* in the panel and is listed at the foot of the map.
  Where a question was is part of the map.
- The light and dark twins have **diverged**. Fifteen screens here, fourteen in
  [`../share-flow-v3`](../share-flow-v3/index.html), which predates both
  decisions. To bring it back into step: rename `09-revoked.html`, port
  `owner_block()` and `03b-name.html`, and update the four copy strings that
  mention revoking.

| Commit | What it did |
| --- | --- |
| `1254ce6` | Revoke → expiry, `03b-name.html`, both generators, both viewers, the map. |
| `ca416b8` | [`backend.md`](backend.md): the two owner columns, the rename route, the seven endpoints. |
| `c05de29` | The hand-written documents — `design.md`, `audit.md`, `notes.md`, the contact sheet. |

**Still open after this revision**, both in
[`notes.md`](../share-flow-v3-light/notes.md):

- Does the recipient's page show the expiry date? The mail footer names it, so
  anyone arriving from the mail has been told; [`07-recipient.html`](07-recipient.html)
  itself does not say it.
- Which mailbox, when two are connected? Drawn as the first. `POST /api/shares`
  takes an `account_id`, but no screen offers the choice.

---

*Screens are generated: `python3 ../share-flow-v3-light/build.py`, then
`python3 annotate.py`, in that order. A revision that edits a screen by hand is
a revision that will be overwritten.*
