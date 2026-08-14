"""Regenerate the share-flow mockup screens: `python3 docs/flows/share-flow/build.py`.

The screens share most of their markup; writing them by hand guarantees they
drift from each other. This emits all ten from one set of fragments, so a change
to the table or the summary lands everywhere at once.

Not generated here: index.html (the contact sheet), email.html (the draft), and
flow.css. Those are one-offs and are edited directly.
"""

from pathlib import Path
from typing import NamedTuple

OUT = Path(__file__).parent

# ---------------------------------------------------------------- data
# Columns match what backend/extract.py actually produces — see the real
# payloads under .data/. `invoice_no`, `net` and `vat` are blank for the Bolt
# row on purpose: that one is a ride receipt read out of the mail body, and it
# genuinely carries only issuer, date, amount, currency and VAT number. Every
# column below has to survive being empty.
class Row(NamedTuple):
    vendor: str
    ini: str
    colour: str
    invoice_no: str
    net: str
    vat: str
    total: str
    issued: str
    doc: bool


ROWS = [
    Row("Hetzner Online GmbH", "He", "#D50C2D", "R0012345678", "35.38", "6.72", "42.10", "03.04.2026", True),
    Row("Amazon Web Services", "AW", "#232F3E", "EUINV22-441907", "739.50", "140.50", "880.00", "05.04.2026", True),
    Row("Notion Labs Inc.", "No", "#191918", "8F21C4-0031", "16.00", "0.00", "16.00", "06.04.2026", True),
    Row("Figma Inc.", "Fi", "#0D99FF", "INV-90412", "45.00", "0.00", "45.00", "09.04.2026", True),
    Row("Vercel Inc.", "Ve", "#111111", "B7A2-2026-04", "20.00", "0.00", "20.00", "12.04.2026", True),
    Row("Bolt Operations OÜ", "Bo", "#5B1D52", "", "", "", "2.37", "14.04.2026", False),
    Row("Slack Technologies", "Sl", "#4A154B", "SL-2026-77412", "56.25", "11.25", "67.50", "21.04.2026", True),
    Row("GitHub Inc.", "Gi", "#24292F", "GH-4471203", "84.00", "0.00", "84.00", "02.05.2026", True),
    Row("Linear Orbit Inc.", "Li", "#5E6AD2", "LIN-00918", "96.00", "0.00", "96.00", "08.05.2026", True),
    Row("OpenAI LLC", "Op", "#10A37F", "OAI-2026-5590", "400.00", "80.00", "480.00", "19.05.2026", True),
]
THUMBS = ROWS[:5]

LINK = "invoicepilot.app/s/7Kq2mXbN4vRt9wLpZaHc3f"

# invoices.csv carries 22 columns per invoice; seven of them are on screen
# (vendor, invoice number, file, issued, net, VAT, total — "#" is a row number,
# not data). These are the rest, and they are what the "+15" column counts.
CSV_ONLY = ("VAT number, company number, currency, payment reference, service date, description, "
            "file size, SHA-256, source, mailbox, email subject, received, message id, "
            "extracted at, extracted by")

# ---------------------------------------------------------------- icons
I_SHARE = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
           'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
           '<path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7M12 3v13M8 7l4-4 4 4"/></svg>')
I_DL = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>')
I_EYE = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
         'stroke-width="1.8"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/>'
         '<circle cx="12" cy="12" r="3"/></svg>')
I_REFRESH = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6"/></svg>')
I_COPY = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
          'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
          '<rect x="9" y="9" width="12" height="12" rx="2"/>'
          '<path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/></svg>')
I_MAIL = ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
          'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
          '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 7 10 6 10-6"/></svg>')
I_TICK = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
          'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
          '<path d="m20 6-11 11-5-5"/></svg>')
I_OPEN = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
          'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
          '<path d="M14 3h7v7M10 14 21 3M18 13v7a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h7"/></svg>')
I_CARET = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
           'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
           '<path d="m6 9 6 6 6-6"/></svg>')
I_GMAIL = ('<svg class="source-mark" viewBox="0 0 24 24" aria-hidden="true">'
           '<path fill="#EA4335" d="M12 10.2V14h5.3c-.2 1.2-1.6 3.6-5.3 3.6A5.6 5.6 0 1 1 15.7 8l2.7-2.6A9.3 '
           '9.3 0 0 0 12 3a9 9 0 1 0 0 18c5.2 0 8.6-3.6 8.6-8.7 0-.6 0-1-.1-1.5H12z"/></svg>')


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<link rel="stylesheet" href="../../../frontend/src/styles/tokens.css"/>
<link rel="stylesheet" href="../../../frontend/src/styles/dashboard.css"/>
<link rel="stylesheet" href="flow.css"/>
</head>
<body>
{body}
</body>
</html>
"""


# ---------------------------------------------------------------- dashboard
# Two mailboxes on purpose: it is the only way to see the From picker, which
# does not exist when there is nothing to pick between.
ACCOUNTS = ["martin@kirov.dev", "billing@kirov.dev"]


def sources_card() -> str:
    unlink = ('<button class="icon-btn" aria-label="Disconnect"><svg width="15" height="15" '
              'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
              'stroke-linecap="round"><path d="M18.4 10.6a4.5 4.5 0 0 0-6.4-6.3l-1.4 1.4M5.6 13.4a4.5 '
              '4.5 0 0 0 6.4 6.3l1.4-1.4M2 2l20 20"/></svg></button>')
    rows = "".join(
        f'<div class="source">{I_GMAIL}<span class="source-mail">{mail}</span>{unlink}</div>'
        for mail in ACCOUNTS
    )
    return (
        '<section class="card sources"><div class="card-label">Email sources</div>'
        f'{rows}'
        '<button class="add-source"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>'
        'Add source</button>'
        f'<div class="accounts-note"><span class="dot"></span>{len(ACCOUNTS)} accounts connected</div>'
        '</section>'
    )


def dash_row(row: Row, checked: bool) -> str:
    mark = ' checked' if checked else ''
    cls = ' class="selected"' if checked else ''
    return (
        f'<tr{cls}><td class="col-check"><input type="checkbox"{mark}></td>'
        f'<td><div class="vendor"><span class="vendor-logo" style="background:{row.colour}">{row.ini}</span>'
        f'<span><span class="vendor-name">{row.vendor}</span></span></div></td>'
        f'<td class="col-amount">{row.total} €</td><td class="col-issued">{row.issued}</td>'
        f'<td class="col-actions"><div class="row-actions">'
        f'<button class="icon-btn" aria-label="Preview">{I_EYE}</button>'
        f'<button class="icon-btn" aria-label="Download">{I_DL}</button></div></td></tr>'
    )


def dashboard(popover: str = "", checked: bool = False) -> str:
    rows = "".join(dash_row(r, checked) for r in ROWS)
    check_all = ' checked' if checked else ''
    pop_cls = ' is-active' if popover else ''
    return f"""<main><div class="grid">
  {sources_card()}
  <section class="card">
    <div class="table-head">
      <div class="table-title">Invoices <em>37 documents</em></div>
      <div class="tools"><span class="last-update">Updated just now</span>
        <div class="tool-divider"></div>
        <button class="update-btn" data-busy="false">{I_REFRESH}<span>Update</span></button>
        <div class="tool-divider"></div>
        <span class="pop-anchor">
          <button class="icon-btn{pop_cls}" aria-label="Share invoices">{I_SHARE}</button>
          {popover}
        </span>
        <button class="icon-btn" aria-label="Download selected">{I_DL}</button>
      </div>
    </div>
    <table><thead><tr>
      <th class="col-check"><input type="checkbox"{check_all}></th><th>Vendor</th>
      <th class="col-amount sortable"><button>Amount</button></th>
      <th class="col-issued sortable sorted"><button>Issued</button></th>
      <th class="col-actions">Actions</th></tr></thead>
      <tbody>{rows}</tbody></table>
    <div class="table-foot"><span class="per-page">{'37 selected' if checked else '10 of 37 shown'}</span>
      <span class="pager"><span class="page-num">1</span></span></div>
  </section>
</div></main>"""


POPOVER = f"""<div class="share-pop">
            <div class="pop-title"><span class="ok">{I_TICK}</span>Link copied</div>
            <p class="pop-sub">All 37 invoices, Apr 1 – Jun 30. Anyone with this link can view and
            download them. It stays live until you revoke it.</p>
            <div class="link-row"><code>{LINK}</code>
              <button class="icon-btn" aria-label="Copy again">{I_COPY}</button></div>
            <div class="pop-actions">
              <a class="btn btn-primary btn-grow" href="03-preview.html">{I_OPEN}Open link</a>
              <a class="btn btn-grow" href="04-compose.html">{I_MAIL}Send by email</a>
            </div>
          </div>"""


# ---------------------------------------------------------------- share page
def thumb(row: Row) -> str:
    """A thumbnail is a picture, not a link.

    Nothing on this page opens a single document: no overlay, no pdf.js, no
    viewer screen. Whoever wants to read one downloads the zip and opens it in
    the reader they already have.
    """
    short = row.vendor.split()[0]
    if not row.doc:
        inner = ('<div class="thumb-page is-textonly">No document<br/>read from<br/>the email body</div>')
    else:
        inner = (f'<div class="thumb-page">'
                 f'<div class="thumb-logo" style="background:{row.colour}">{row.ini}</div>'
                 '<div class="thumb-line" style="width:70%"></div>'
                 '<div class="thumb-line" style="width:52%"></div>'
                 '<div class="thumb-line" style="width:80%;margin-top:14px"></div>'
                 '<div class="thumb-line" style="width:74%"></div>'
                 '<div class="thumb-line" style="width:40%"></div>'
                 f'<div class="thumb-total">{row.total} €</div></div>')
    return (f'<div class="thumb">{inner}'
            f'<div class="thumb-cap"><b>{short}</b>{row.total} €</div></div>')


def thumb_strip() -> str:
    """Five thumbnails and a count. Never more.

    A scrolling strip would mean lazy loading, a scroll affordance and a
    virtualization story for something nobody flicks through — five is enough
    to recognise the batch, and the sheet below lists all 37 by name anyway.
    """
    cells = "".join(thumb(r) for r in THUMBS)
    return (f'<div class="zip-part is-docs">'
            f'{part_head("pdf", "36 documents", "the vendors&rsquo; own files · 5 shown")}'
            f'<div class="thumbs">{cells}<div class="thumb-more">+32 more</div></div></div>')


def doc_name(row: Row) -> str:
    """The entry name this invoice gets inside the zip.

    Same shape as invoice_store.folder_name() — date first, so the recipient's
    folder sorts itself. Showing it here means the table doubles as the zip's
    manifest, which is the spreadsheet-ish job this column is doing.
    """
    if not row.doc:
        return ""
    d, m, y = row.issued.split(".")
    slug = row.vendor.split()[0].lower().strip(".")
    return f"{y}-{m}-{d}__{slug}__{row.total}EUR.pdf"


def blank(value: str, cls: str) -> str:
    """A cell the extractor had nothing for.

    An em dash, not an empty cell: blank reads as "we forgot to render it",
    a dash reads as "this invoice does not carry one" — which is the truth for
    every receipt parsed out of a mail body.
    """
    return f'<td class="{cls}">{value}</td>' if value else f'<td class="{cls} is-none">—</td>'


def share_row(row: Row, n: int) -> str:
    """One line of the sheet: no checkbox, no logo, no actions, no link.

    A row is a fact about the zip, not a control.
    """
    doc_cell = (f'<td class="c-doc">{doc_name(row)}</td>' if row.doc else
                '<td class="c-doc is-none" title="Read from an email body — no attachment">'
                'no document</td>')
    return (
        f'<tr><td class="c-num">{n}</td>'
        f'<td class="c-vendor">{row.vendor}</td>'
        f'{blank(row.invoice_no, "c-inv")}{doc_cell}'
        f'<td class="c-date">{row.issued}</td>'
        f'{blank(row.net, "c-money")}{blank(row.vat, "c-money")}'
        f'<td class="c-amt">{row.total}</td>'
        f'<td class="c-more">…</td></tr>'
    )


def share_table() -> str:
    """A plain sheet: hairline grid, tabular figures, counts on the last line.

    Columns are what backend/extract.py actually yields — invoice number and
    the net/VAT split included, because that is what the batch is *for*. No
    currency column: the whole batch is EUR, and one would only earn its width
    if a share ever mixed two.

    Eight is the ceiling, and the ninth column is not data: it is the count of
    columns the CSV carries and the page does not. Without it the sheet reads
    as the whole truth and invoices.csv looks like a duplicate of it.

    Deliberately unlike the dashboard's table, which is a working surface with
    checkboxes, logos and per-row actions. Nothing here is to be operated —
    it is a document that happens to be rendered as rows, so it reads like the
    export it describes.
    """
    rows = "".join(share_row(r, i + 1) for i, r in enumerate(ROWS))
    # The count is CSV columns minus the ones on screen, so it grows as the
    # breakpoints drop columns. data-* + CSS ::after keeps that honest at every
    # width without a line of JavaScript.
    more = ('<th class="c-more" data-wide="+15" data-mid="+18" data-narrow="+19" '
            f'title="Also in invoices.csv: {CSV_ONLY}"></th>')
    head = part_head("csv", "invoices.csv", "one row per invoice · 22 columns")
    return f"""<div class="zip-part">{head}<table class="sheet"><thead><tr>
      <th class="c-num">#</th><th class="c-vendor">Vendor</th><th class="c-inv">Invoice&nbsp;#</th>
      <th class="c-doc">Document</th><th class="c-date">Issued</th>
      <th class="c-money">Net</th><th class="c-money">VAT</th>
      <th class="c-amt">Total&nbsp;€</th>{more}</tr></thead>
      <tbody>{rows}<tr class="more"><td class="c-num">…</td>
        <td colspan="8">27 more rows</td></tr></tbody>
      <tfoot><tr><td class="c-num"></td><td class="c-vendor">37 invoices</td>
        <td class="c-inv"></td><td class="c-doc">36 documents</td>
        <td class="c-date"></td><td class="c-money"></td><td class="c-money"></td>
        <td class="c-amt"></td><td class="c-more"></td></tr></tfoot></table></div>"""


def summary() -> str:
    # "invoices", not "files": one of the 37 was read out of an email body and
    # has no document, so a file count here would not survive a recount.
    return f"""<div class="summary">
      <div class="summary-text">
        <div class="summary-title"><span class="ftype is-zip">zip</span>
          invoices-2026-Q2.zip <em>37 invoices · 12.4 MB</em></div>
        <div class="summary-meta">Apr 1 – Jun 30, 2026</div>
      </div>
      <a class="btn btn-primary btn-lg" href="#">{I_DL}Download all</a>
    </div>"""


def part_head(kind: str, name: str, note: str) -> str:
    """The heading over each half of the zip's contents.

    The page's job is to answer "what am I downloading?" before anyone clicks,
    and the honest answer is two things: the vendors' PDFs and a spreadsheet.
    Naming both with their file type — under a header already chipped `zip` —
    makes the containment legible without a word of explanation.
    """
    return (f'<div class="part-head"><span class="ftype is-{kind}">{kind}</span>'
            f'<b>{name}</b><span class="part-note">{note}</span></div>')


def brand(owner: bool) -> str:
    who = "Your link" if owner else "Shared by Martin Kirov · martin@kirov.dev"
    return (f'<div class="share-brand"><span class="mark">IP</span>Invoice Pilot'
            f'<span class="from">{who}</span></div>')


OWNER_BAR = f"""<div class="owner-bar"><span class="dot"></span>
      This link is live — anyone with it can download.
      <span class="spacer"></span>
      <a class="btn" href="04-compose.html">{I_MAIL}Send by email</a>
      <a class="revoke" href="#">Revoke</a>
    </div>"""


def share_page(*, owner: bool, banner: str = "", composer: str = "") -> str:
    return f"""<main class="share-main">
  {brand(owner)}
  <section class="card">
    {banner}
    {summary()}
    {OWNER_BAR if owner and not composer else ''}
    {composer}
    {thumb_strip()}
    {share_table()}
    <div class="share-foot"><span>invoices.csv carries all 22 columns per invoice.</span>
      <span class="spacer"></span>
      <span>1 invoice has no document; it rides along in the CSV.</span>
    </div>
  </section>
</main>"""


MAIL_ERROR = """
      <div class="mail-error"><b>Could not send.</b> Unipile returned
        <code>HTTP 401 — account credentials need reauthorising</code>.
        Your address is still here, and the link is live either way — copy it and send it yourself,
        or reconnect the mailbox and try again.</div>"""


def from_field(menu_open: bool = False) -> str:
    """The sending mailbox: an address, and a caret only if there is a choice.

    A closed menu is the resting state, so what the row says is simply which
    mailbox this goes out as — the way it would read on a sent message. The
    menu marks the current one rather than hiding it, so the list answers
    "which am I on?" as well as "what else is there?".
    """
    if len(ACCOUNTS) == 1:
        return f'<span class="from-current">{I_GMAIL}{ACCOUNTS[0]}</span>'

    # Static mockup: the caret toggles between the two screens instead of a menu.
    href = "04-compose.html" if menu_open else "05-from.html"
    opts = "".join(
        f'<a class="from-opt{" is-current" if i == 0 else ""}" href="04-compose.html">'
        f'{I_GMAIL}{mail}{f"<span class=tick>{I_TICK}</span>" if i == 0 else ""}</a>'
        for i, mail in enumerate(ACCOUNTS)
    )
    menu = f'<div class="from-menu">{opts}</div>' if menu_open else ""
    return (
        f'<span class="from-anchor"><span class="from-current">{I_GMAIL}{ACCOUNTS[0]}</span>'
        f'<a class="icon-btn{" is-active" if menu_open else ""}" href="{href}" '
        f'aria-label="Send from a different mailbox" aria-expanded="{str(menu_open).lower()}">'
        f'{I_CARET}</a>{menu}</span>'
    )


def composer(error: str = "", menu_open: bool = False) -> str:
    """One address to fill — nothing else — and the actual mail underneath it.

    No note field: an optional message box is a decision every sender then has
    to make, and the draft already says everything the recipient needs.

    The preview is the same document the API sends — an iframe over the
    rendered draft, not a mock-up of one — so what the sender approves and what
    the recipient opens cannot diverge. It also answers the question the
    composer otherwise leaves hanging: what is it going to say?

    From reads as the answer, not as a question: the address in plain text,
    with a caret button beside it that opens the other connected mailboxes.
    With one account the caret is not rendered at all — there is nothing to
    open, and a control that leads nowhere is worse than no control.
    """
    return f"""<div class="composer">
      <h3>Send this link by email</h3>
      <div class="field"><label>From</label>{from_field(menu_open)}
        <span class="field-note">Replies come back here</span></div>
      <div class="field"><label for="to">To</label>
        <input id="to" type="email" placeholder="accountant@firm.com" value="anna@ledger.co"/></div>
      <div class="composer-foot">
        <a class="btn btn-primary" href="06-sent.html">{I_MAIL}Send</a>
        <a class="btn" href="03-preview.html">Cancel</a>
        <span class="hint">Subject: <b>Invoices — Apr–Jun 2026 (37 invoices)</b>.
          The link is sent, not the files.</span>
      </div>{error}
      <div class="mail-preview">
        <div class="mail-preview-head">Preview · what anna@ledger.co opens
          <a href="email.html" target="_blank">full size ↗</a></div>
        <iframe src="email.html" title="Email preview" loading="lazy"></iframe>
      </div>
    </div>"""


COMPOSER = composer()
COMPOSER_OPEN = composer(menu_open=True)
COMPOSER_FAILED = composer(MAIL_ERROR)

SENT_BANNER = f"""<div class="banner is-ok"><span class="tick">{I_TICK}</span>
      Sent to <b>anna@ledger.co</b> from martin@kirov.dev.
      <a class="undo" href="04-compose.html">Send to someone else</a></div>"""

REVOKED = f"""<main class="share-main">
  {brand(False)}
  <section class="card"><div class="dead">
    <h2>This link was revoked</h2>
    <p>Martin Kirov turned it off. Ask for a new one — the invoices are still there.</p>
  </div></section>
</main>"""


# ---------------------------------------------------------------- write
SCREENS = {
    "01-idle.html": ("Idle", dashboard()),
    "02-link.html": ("Link created", dashboard(POPOVER)),
    "03-preview.html": ("Share page — owner", share_page(owner=True)),
    "04-compose.html": ("Composer", share_page(owner=True, composer=COMPOSER)),
    "05-from.html": ("Choosing the mailbox", share_page(owner=True, composer=COMPOSER_OPEN)),
    "06-sent.html": ("Sent", share_page(owner=True, banner=SENT_BANNER)),
    "07-recipient.html": ("Recipient", share_page(owner=False)),
    "08-send-failed.html": ("Send failed", share_page(owner=True, composer=COMPOSER_FAILED)),
    "09-revoked.html": ("Revoked", REVOKED),
}

for name, (title, body) in SCREENS.items():
    (OUT / name).write_text(page(title, body), encoding="utf-8")
    print("wrote", name)
