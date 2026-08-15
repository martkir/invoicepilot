"""Regenerate the share-flow screens on Mercury light:
`python3 docs/flows/share-flow-v3-light/build.py`

The light twin of ../share-flow-v3/build.py. The markup is identical, line for
line; the theme lives in tokens-v3.css, which is the whole point of landing the
tokens once. Only the two <meta> values below know which twin this is.

Same generator idea as v1 and v2 (the screens share most of their markup, so
writing them by hand guarantees they drift) but the markup is the redesign.
Structural changes against share-flow-v2/build.py that live in this file
rather than in the CSS:

  · The share page is two columns. A sticky rail carries the batch identity,
    the four facts, the download, and (for the owner) the live state, the name
    the link goes out under and the send. The right column carries the composer
    and the manifest. v2 stacked
    all of it down one column and lifted one card 44px into the band above it
    to break the stripes; without a shadow under it that overlap reads as a
    misplaced element, so the layout changed instead of the trick.
  · The sticky owner bar is gone. Its controls moved into the rail, which
    is already sticky, which also removes the --sticky-top offset the sheet's
    own sticky header had to read off the page.
  · The fan of five thumbnails is gone. See docs_part().
  · Form fields are label-above-input, which is the shape Section 4.6 asks
    for; v2 ran the label down the left on a fixed 52px column.
  · No vendor brand colours, no green, no grain, no gradients, no shadows.
  · Every dash in visible copy is a hyphen. v2 spent em dashes freely,
    including as the "no value" glyph in the manifest.

Not generated here: index.html (the contact sheet), viewer.html, email.html
(the draft) and the three stylesheets. Those are one-offs, edited directly.

Revision 2 (2026-08-15) settled three things the screens had been drawn
around; ../share-flow-v3-light-annotated/revisions.md is the log. In this file
they are: no Revoke control and no revoked screen (a link ends on a date, and
09-expired.html is what that looks like), an owner display name that the owner
can correct (03b-name.html), and a mail preview that is the mail itself.
"""

from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

OUT = Path(__file__).parent

# ---------------------------------------------------------------- data ------
# Columns match what backend/extract.py actually produces. `invoice_no`, `net`
# and `vat` are blank for the Bolt row on purpose: that one is a ride receipt
# read out of a mail body, and it genuinely carries only issuer, date, amount,
# currency and VAT number. Every column below has to survive being empty.
#
# Amounts are net + VAT figures that add up: 19% where the vendor charges
# German VAT, 0% where it is reverse-charged, and one ride receipt with no
# split at all.


class Row(NamedTuple):
    vendor: str
    ini: str
    invoice_no: str
    net: str
    vat: str
    total: str
    issued: str
    doc: bool


ROWS = [
    Row("Hetzner Online GmbH", "He", "R0012345678", "35.38", "6.72", "42.10", "03.04.2026", True),
    Row("Amazon Web Services", "Am", "EUINV22-441907", "733.97", "139.45", "873.42", "05.04.2026", True),
    Row("Notion Labs Inc.", "No", "8F21C4-0031", "21.60", "0.00", "21.60", "06.04.2026", True),
    Row("Figma Inc.", "Fi", "INV-90412", "41.85", "0.00", "41.85", "09.04.2026", True),
    Row("Vercel Inc.", "Ve", "B7A2-2026-04", "34.72", "0.00", "34.72", "12.04.2026", True),
    Row("Bolt Operations OÜ", "Bo", "", "", "", "2.37", "14.04.2026", False),
    Row("Slack Technologies", "Sl", "SL-2026-77412", "56.25", "11.25", "67.50", "21.04.2026", True),
    Row("GitHub Inc.", "Gi", "GH-4471203", "79.20", "0.00", "79.20", "02.05.2026", True),
    Row("Linear Orbit Inc.", "Li", "LIN-00918", "118.80", "0.00", "118.80", "08.05.2026", True),
    Row("OpenAI LLC", "Op", "OAI-2026-5590", "342.80", "65.13", "407.93", "19.05.2026", True),
]
# The five documents shown as tiles. The Bolt row is not among them because it
# has no document at all: it belongs to the manifest below, where the sheet
# says so in words, not to a strip whose subject is the PDFs.
TILES = ROWS[:5]

# The rest of the payload, for the one row the flow opens. ROWS carries the
# four columns the table shows; these are the other fields backend/extract.py
# files under `invoice`, `email` and `document`, which is what the panel is
# for. Dates are spelled out here because the panel renders them through
# longDate() and dateTime() rather than the table's dd.mm.yyyy.
#
# Sample values, like every figure in this folder. The vendors are real
# companies and the identifiers are not theirs; what is real is the shape of
# each field, because that is what the panel has to lay out.
DETAIL = {
    "Hetzner Online GmbH": {
        "currency": "€",
        "issued_long": "3 April 2026",
        "service_start": "1 April 2026",
        "vat_number": "DE311046661",
        "company_number": "HRB 226484",
        "reference": "R0012345678-2026-04",
        "subject": "Your Hetzner invoice R0012345678",
        "sender": "Hetzner Online GmbH &lt;accounting@hetzner.com&gt;",
        "mailbox": "billing@kirov.dev",
        "received": "3 April 2026 at 06:12",
        "bytes": "84 KB",
        "origin": "the attachment",
    },
}

LINK = "invoicepilot.app/s/7Kq2mXbN4vRt9wLpZaHc3f"
ZIP_NAME = "invoices-2026-Q2.zip"
PERIOD = "Apr 1 - Jun 30, 2026"
SUBJECT = "Invoices, Apr to Jun 2026 (37 invoices)"

# Two mailboxes on purpose: it is the only way to see the From picker, which
# does not exist when there is nothing to pick between.
ACCOUNTS = ["martin@kirov.dev", "billing@kirov.dev"]

# Who the recipient is told this came from. The address is the connected
# mailbox and is not the owner's to type; the name is a display name taken from
# that mailbox and correctable, because a mailbox often carries no name at all
# and half an email address ("martinvkirov") is not what anyone wants to be
# introduced as.
OWNER_MAIL = ACCOUNTS[0]
OWNER_NAME = "Martin Kirov"
# What the name falls back to before anyone corrects it: the local part of the
# address, verbatim. It is drawn on 03b-name.html as the value being replaced.
OWNER_FALLBACK = OWNER_MAIL.split("@")[0]

# Links stop working seven days after they are made, so every screen that
# mentions the link's life mentions a date rather than a promise. The batch
# ends 30 June and the share is made a few days later.
MADE_ON = "5 July 2026"
EXPIRES = "12 July 2026"

# invoices.csv carries 22 columns per invoice; seven of them are on screen
# (vendor, invoice number, file, issued, net, VAT, total; "#" is a row number,
# not data). These are the rest, and they are what the "+15" column counts.
CSV_ONLY = ("VAT number, company number, currency, payment reference, service date, description, "
            "file size, SHA-256, source, mailbox, email subject, received, message id, "
            "extracted at, extracted by")

# ---------------------------------------------------------------- icons -----
# One set, one grid, one stroke weight, emitted from one helper so the set
# cannot drift (Section 3.C). Inline SVG is the only option in a file:// draft
# with no npm, and is correct there.
#
# The metaphors are unchanged from v2: none of them was a cliche worth
# replacing (no rocket for "launch", no shield for "secure"), and an envelope
# that is not an envelope helps nobody.


def icon(path: str, size: int = 16, extra: str = "") -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true"{extra}>{path}</svg>')


I_SHARE = icon('<path d="M12 15.5V3.6"/><path d="m8.2 7.2 3.8-3.6 3.8 3.6"/>'
               '<path d="M5 13v4.9A2.1 2.1 0 0 0 7.1 20h9.8a2.1 2.1 0 0 0 2.1-2.1V13"/>')
I_DL = icon('<path d="M12 3.6v11.9"/><path d="m8.2 11.9 3.8 3.6 3.8-3.6"/>'
            '<path d="M5 13v4.9A2.1 2.1 0 0 0 7.1 20h9.8a2.1 2.1 0 0 0 2.1-2.1V13"/>')
I_DL_LG = icon('<path d="M12 3.6v11.9"/><path d="m8.2 11.9 3.8 3.6 3.8-3.6"/>'
               '<path d="M5 13v4.9A2.1 2.1 0 0 0 7.1 20h9.8a2.1 2.1 0 0 0 2.1-2.1V13"/>', 18)
I_EYE = icon('<path d="M2.8 12S6.9 5.9 12 5.9 21.2 12 21.2 12 17.1 18.1 12 18.1 2.8 12 2.8 12Z"/>'
             '<circle cx="12" cy="12" r="2.9"/>')
I_REFRESH = icon('<path d="M20.4 12a8.4 8.4 0 1 1-2.5-6"/><path d="M20.4 4v4.4H16"/>', 15)
I_COPY = icon('<rect x="8.6" y="8.6" width="11.8" height="11.8" rx="2.4"/>'
              '<path d="M5.2 15.4H4.9A1.3 1.3 0 0 1 3.6 14V4.9a1.3 1.3 0 0 1 1.3-1.3H14a1.3 1.3 0 0 1 1.3 1.3v.3"/>', 15)
I_MAIL = icon('<rect x="3.2" y="5.2" width="17.6" height="13.6" rx="2.4"/>'
              '<path d="m3.9 7.4 7 4.7a2.1 2.1 0 0 0 2.2 0l7-4.7"/>', 15)
I_TICK = icon('<path d="m4.6 12.4 4.7 4.6 10.1-10"/>', 14)
I_OPEN = icon('<path d="M14.4 3.6h6v6"/><path d="M10.2 13.8 20.4 3.6"/>'
              '<path d="M18.6 13.2v5.2a2.1 2.1 0 0 1-2.1 2.1H5.7a2.1 2.1 0 0 1-2.1-2.1V7.6a2.1 2.1 0 0 1 2.1-2.1h5.2"/>', 15)
I_CARET = icon('<path d="m6.6 9.4 5.4 5.2 5.4-5.2"/>', 14)
I_ALERT = icon('<circle cx="12" cy="12" r="8.6"/><path d="M12 7.8v4.6"/><path d="M12 16.1h.01"/>', 16)
# Expiry is a clock, not a crossed-out circle. The link was not turned off by
# anyone; its time ran out, and the mark should say which of those happened.
I_EXPIRED = icon('<circle cx="12" cy="12" r="8.6"/><path d="M12 7.2V12l3.2 2"/>', 22)
I_PEN = icon('<path d="M14.8 5.4 18.6 9.2"/>'
             '<path d="M16.4 3.8a2.1 2.1 0 0 1 3 3L8.6 17.6l-4 1.2 1.2-4Z"/>', 14)
I_LOST = icon('<circle cx="10.8" cy="10.8" r="6.8"/><path d="m15.7 15.7 4.7 4.7"/>'
              '<path d="M8.6 8.6 13 13"/><path d="M13 8.6 8.6 13"/>', 22)
I_BACK = icon('<path d="M19.4 12H4.6"/><path d="m10.4 5.6-5.8 6.4 5.8 6.4"/>', 15)

# The wordmark: a document with a folded corner, which is the thing the
# product moves around.
I_MARK = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
          'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
          '<path d="M13.4 3.4H7.9A2.3 2.3 0 0 0 5.6 5.7v12.6a2.3 2.3 0 0 0 2.3 2.3h8.2a2.3 2.3 0 0 0 '
          '2.3-2.3V8.3Z"/><path d="M13.4 3.4v4.9h4.7"/></svg>')

# Gmail's own mark, drawn in currentColor rather than in Google's four brand
# colours: Section 4.9 asks single-colour logos to render in --ink or --cloud,
# and a four-colour glyph beside a one-accent palette is a second accent.
I_GMAIL = ('<svg class="source-mark" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
           '<path d="M12 10.2V14h5.3c-.2 1.2-1.6 3.6-5.3 3.6A5.6 5.6 0 1 1 15.7 8l2.7-2.6A9.3 '
           '9.3 0 0 0 12 3a9 9 0 1 0 0 18c5.2 0 8.6-3.6 8.6-8.7 0-.6 0-1-.1-1.5H12z"/></svg>')

# ---------------------------------------------------------------- shell -----
# The wordmark glyph on the accent, inlined so it costs no request.
FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<rect width="24" height="24" rx="6" fill="#5266eb"/>'
    '<path d="M13.4 4.4H8.4A2 2 0 0 0 6.4 6.4v11.2a2 2 0 0 0 2 2h7.2a2 2 0 0 0 2-2V8.4Z" '
    'fill="none" stroke="#fff" stroke-width="1.7" stroke-linejoin="round"/>'
    '<path d="M13.4 4.4v4h4" fill="none" stroke="#fff" stroke-width="1.7" stroke-linejoin="round"/>'
    '</svg>'
)
FAVICON = "data:image/svg+xml," + quote(FAVICON_SVG, safe="")


def page(title: str, body: str, *, desc: str, body_class: str = "") -> str:
    """One <head> for every screen.

    The share page is a public URL that gets pasted into Slack and WhatsApp,
    so the og: block is not decoration: it is what the recipient sees before
    they decide to click.
    """
    cls = f' class="{body_class}"' if body_class else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="light"/>
<title>{title} · Invoice Pilot</title>
<meta name="description" content="{desc}"/>
<meta property="og:type" content="website"/>
<meta property="og:title" content="{title} · Invoice Pilot"/>
<meta property="og:description" content="{desc}"/>
<meta name="theme-color" content="#eef0f6"/>
<link rel="icon" href="{FAVICON}"/>
<link rel="stylesheet" href="../../../frontend/src/styles/tokens.css"/>
<link rel="stylesheet" href="../../../frontend/src/styles/dashboard.css"/>
<link rel="stylesheet" href="tokens-v3.css"/>
<link rel="stylesheet" href="reskin.css"/>
<link rel="stylesheet" href="flow.css"/>
</head>
<body{cls}>
<a class="skip" href="#content">Skip to the content</a>
{body}
</body>
</html>
"""


# ---------------------------------------------------------------- dashboard -
def sources_card() -> str:
    unlink = ('<button class="icon-btn" aria-label="Disconnect this mailbox">'
              + icon('<path d="M18.1 10.7a4.3 4.3 0 0 0-6.1-6.1l-1.3 1.3"/>'
                     '<path d="M5.9 13.3a4.3 4.3 0 0 0 6.1 6.1l1.3-1.3"/>'
                     '<path d="m3.6 3.6 16.8 16.8"/>', 15) + '</button>')
    rows = "".join(
        f'<div class="source">{I_GMAIL}<span class="source-mail">{mail}</span>{unlink}</div>'
        for mail in ACCOUNTS
    )
    plus = icon('<path d="M12 5.4v13.2"/><path d="M5.4 12h13.2"/>', 14)
    # No status dot on the count. v2 carried one; a dot that is always the same
    # colour conveys no state, and Section 7.A allows none by default.
    return (
        '<section class="card sources" aria-label="Email sources">'
        '<h2 class="card-label">Email sources</h2>'
        f'{rows}'
        f'<button class="add-source">{plus}Add source</button>'
        f'<p class="accounts-note">{len(ACCOUNTS)} accounts connected</p>'
        '</section>'
    )


def dash_row(row: Row, checked: bool, is_open: bool = False) -> str:
    mark = ' checked' if checked else ''
    classes = " ".join(c for c in (checked and "selected", is_open and "is-open") if c)
    cls = f' class="{classes}"' if classes else ''
    # The eye is the disclosure, so it says which way it goes and carries the
    # state in aria-expanded rather than only in colour.
    eye = (f'<button class="icon-btn" aria-expanded="{str(is_open).lower()}" '
           f'aria-label="{"Hide" if is_open else "Preview"} {row.vendor}">{I_EYE}</button>')
    return (
        f'<tr{cls}><td class="col-check">'
        f'<input type="checkbox" aria-label="Select {row.vendor}"{mark}></td>'
        f'<td><div class="vendor"><span class="vendor-logo" aria-hidden="true">{row.ini}</span>'
        f'<span class="vendor-name">{row.vendor}</span></div></td>'
        f'<td class="col-amount">{row.total} €</td><td class="col-issued">{row.issued}</td>'
        f'<td class="col-actions"><div class="row-actions">{eye}'
        f'<button class="icon-btn" aria-label="Download {row.vendor}">{I_DL}</button>'
        f'</div></td></tr>'
    )


def pair(label: str, value: str, ident: bool = False) -> str:
    """One field the parser found.

    A pair the extractor came back empty on is not rendered at all. Templates
    are per issuer and they differ in how much they capture, so a fixed list
    would be mostly dashes for every vendor but one, and the panel would report
    the template's coverage rather than the invoice.
    """
    v = ' class="v is-id"' if ident else ' class="v"'
    return f'<div class="pair"><div class="k">{label}</div><div{v}>{value}</div></div>'


def detail_panel(row: Row) -> str:
    """The open row's panel: the document, and every field read off it.

    Left is the vendor's own page, right is what the parser claims it says.
    Reading one against the other is the entire reason the row opens, which is
    also why this is two columns and not a stack.

    The amount is not repeated in the field list below it. It is the figure the
    row was opened to check, so it is the panel's headline, and a second copy
    four rows down a list would be two answers to one question.
    """
    d = DETAIL[row.vendor]
    return f"""<tr class="expansion"><td colspan="5">
            <div class="exp">
              <figure class="exp-doc">
                <div class="doc-alt" aria-hidden="true">
                  <span class="vendor-logo">{row.ini}</span></div>
                <figcaption class="doc-cap">
                  <span class="file">{doc_name(row)}</span></figcaption>
                <p class="doc-origin"><span class="ftype">pdf</span>
                  {d['bytes']}, saved from {d['origin']}.</p>
              </figure>
              <div class="meta">
                <div class="exp-total"><span class="big">{row.total} {d['currency']}</span>
                  <dl class="split"><div><dt>Net</dt><dd>{row.net}</dd></div>
                    <div><dt>VAT</dt><dd>{row.vat}</dd></div></dl>
                </div>
                <div class="pair-group">
                  <h3>Invoice</h3>
                  <div class="pairs">
                    {pair("Invoice number", row.invoice_no, ident=True)}
                    {pair("Issued", d['issued_long'], ident=True)}
                    {pair("Service start", d['service_start'], ident=True)}
                    {pair("VAT number", d['vat_number'], ident=True)}
                    {pair("Company number", d['company_number'], ident=True)}
                    {pair("Reference", d['reference'], ident=True)}
                  </div>
                </div>
                <div class="pair-group">
                  <h3>Email it arrived in</h3>
                  <div class="pairs">
                    {pair("Subject", d['subject'])}
                    {pair("From", d['sender'])}
                    {pair("Mailbox", d['mailbox'])}
                    {pair("Received", d['received'], ident=True)}
                  </div>
                </div>
              </div>
            </div>
          </td></tr>"""


def dashboard(popover: str = "", checked: bool = False, opened: str = "") -> str:
    rows = "".join(
        dash_row(r, checked, r.vendor == opened)
        + (detail_panel(r) if r.vendor == opened else "")
        for r in ROWS
    )
    check_all = ' checked' if checked else ''
    pop_cls = ' is-active' if popover else ''
    return f"""<main id="content"><div class="grid">
  {sources_card()}
  <section class="card" aria-label="Invoices">
    <div class="table-head">
      <h1 class="table-title">Invoices <em>37 documents</em></h1>
      <div class="tools"><span class="last-update">Updated just now</span>
        <div class="tool-divider"></div>
        <button class="update-btn" data-busy="false">{I_REFRESH}<span>Update</span></button>
        <div class="tool-divider"></div>
        <span class="pop-anchor">
          <button class="share-btn{pop_cls}"
            aria-expanded="{'true' if popover else 'false'}">{I_SHARE}<span>Share</span></button>
          {popover}
        </span>
      </div>
    </div>
    <table><thead><tr>
      <th class="col-check"><input type="checkbox" aria-label="Select all"{check_all}></th>
      <th scope="col">Vendor</th>
      <th class="col-amount sortable" scope="col"><button>Amount</button></th>
      <th class="col-issued sortable sorted" scope="col"><button>Issued</button></th>
      <th class="col-actions" scope="col">Actions</th></tr></thead>
      <tbody>{rows}</tbody></table>
    <div class="table-foot"><span class="per-page">{'37 selected' if checked else '10 of 37 shown'}</span>
      <span class="pager"><span class="page-num">1</span></span></div>
  </section>
</div></main>"""


# The popover reports; it does not ask. Opening the link is the button and
# sending it by email is a text link: a matched pair of filled and outlined
# buttons reads as two equal decisions when only one of them is the point.
POPOVER = f"""<div class="share-pop" role="status">
            <p class="pop-title"><span class="ok">{I_TICK}</span>Link copied</p>
            <p class="pop-sub">All 37 invoices, {PERIOD}. Anyone with this link can view and
            download them. It stops working on <b>{EXPIRES}</b>.</p>
            <div class="link-row"><code>{LINK}</code>
              <button class="icon-btn" aria-label="Copy the link again">{I_COPY}</button></div>
            <div class="pop-actions">
              <a class="btn btn-primary btn-grow" href="03-preview.html">{I_OPEN}Open the link</a>
              <a class="btn-quiet" href="04-compose.html">{I_MAIL}Send by email</a>
            </div>
          </div>"""


# ---------------------------------------------------------------- share page
def masthead(owner: bool) -> str:
    """Whose link this is.

    Both halves are the same two fields off the share - a display name and the
    mailbox it was made from - frozen when the link was made. The recipient has
    no account and can be told nothing the link does not carry, so this line is
    the reason those fields exist.
    """
    who = (f'<p class="shared-by">Your link<b>{OWNER_MAIL}</b></p>' if owner else
           f'<p class="shared-by">Shared with you by<b>{OWNER_NAME}</b>{OWNER_MAIL}</p>')
    return (f'<header class="masthead"><a class="brand" href="index.html">'
            f'<span class="mark">{I_MARK}</span>Invoice Pilot</a>{who}</header>')


def facts() -> str:
    pairs = [("Invoices", "37"), ("Documents", "36"), ("Size", "12.4 MB"), ("Period", PERIOD)]
    items = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in pairs)
    return f'<dl class="facts">{items}</dl>'


DOWNLOAD = f"""<div class="get">
      <a class="btn btn-primary btn-lg" href="11-zipping.html">{I_DL_LG}Download all</a>
      <p class="get-note">36 PDFs and <b>invoices.csv</b>, zipped. 12.4 MB.</p>
    </div>"""

# Determinate, because a streamed zip knows its own size before the first
# byte. v1 had no download state at all: the button was an href="#".
ZIPPING = """<div class="get">
      <div class="zipping" role="status">
        <p class="row">Preparing your download<span>7.9 of 12.4 MB</span></p>
        <div class="bar"><div class="bar-fill" style="width:64%"></div></div>
        <p class="get-note">Zipping 36 documents and building invoices.csv.
          The file starts saving on its own.</p>
      </div>
    </div>"""


def owner_block(editing: bool = False) -> str:
    """The only thing that differs between the owner's page and everyone
    else's, and the reason there is no separate preview mode to keep in step.

    It lives at the foot of the rail rather than in a bar across the top of
    the window, so the whole of it is reachable from row 37 without a second
    sticky element on the page.

    Three things, in the order the owner asks about them: how long the link
    lives, whose name is on it, and how to send it. The first replaced Revoke -
    a link that ends on a date needs no button, and the date is worth more on
    the page than the button was. The second is here rather than in the
    masthead because it is the one field the owner may correct, and owner-only
    controls belong in the owner block.
    """
    if editing:
        return f"""<div class="owner-block">
        <p class="live"><b>This link is live.</b> Anyone with it can download these invoices.
          It stops working on <b>{EXPIRES}</b>.</p>
        <div class="name-edit">
          <div class="field"><label for="sent-as">Recipients see it from</label>
            <input id="sent-as" name="sent-as" type="text" autocomplete="name"
              value="{OWNER_FALLBACK}" aria-describedby="sent-as-note"/></div>
          <p class="field-note" id="sent-as-note">Taken from {OWNER_MAIL}, which carries no name.
            Shown on this page and in the email.</p>
          <div class="rail-actions">
            <a class="btn btn-secondary" href="03-preview.html">Save</a>
            <a class="btn-quiet" href="03-preview.html">Cancel</a>
          </div>
        </div>
      </div>"""
    return f"""<div class="owner-block">
        <p class="live"><b>This link is live.</b> Anyone with it can download these invoices.
          It stops working on <b>{EXPIRES}</b>.</p>
        <p class="sent-as">Recipients see it from <b>{OWNER_NAME}</b>
          <a class="btn-quiet" href="03b-name.html">{I_PEN}Change</a></p>
        <div class="rail-actions">
          <a class="btn btn-secondary" href="04-compose.html">{I_MAIL}Send by email</a>
        </div>
      </div>"""


def rail(owner: bool, action: str, editing: bool = False) -> str:
    """What the batch is, and the one thing to do with it.

    The filename is the largest thing on the page because "is this the right
    export?" is the only question the page has to settle before anyone clicks.
    Sticky, so the answer and the action stay on screen through 37 rows.
    """
    return f"""<section class="rail" aria-labelledby="batch-name">
      <div>
        <p class="rail-kicker"><span class="ftype">zip</span>One download, no account needed</p>
        <h1 class="batch-name" id="batch-name">{ZIP_NAME}</h1>
      </div>
      {facts()}
      {action}
      {owner_block(editing) if owner else ''}
    </section>"""


def doc_name(row: Row) -> str:
    """The entry name this invoice gets inside the zip.

    Same shape as invoice_store.folder_name(): date first, so the recipient's
    folder sorts itself. Showing it is what makes the sheet a manifest rather
    than a second copy of the dashboard.
    """
    if not row.doc:
        return ""
    d, m, y = row.issued.split(".")
    slug = row.vendor.split()[0].lower().strip(".")
    return f"{y}-{m}-{d}__{slug}__{row.total}EUR.pdf"


def tile(row: Row) -> str:
    """One document.

    v2 drew these as a fan: five sheets of paper overlapped and rotated a
    degree off square. That reads as a stack only because of the shadow
    between each sheet, and there are no shadows here, so it would have been
    six rotated rectangles in a pile.

    What replaces it is the thumbnail panel the product actually renders, in
    the state where the page-1 render is missing: the vendor's initials on a
    plain panel. Production drops an <img src="{thumb}"> into .doc-thumb and
    this stays behind it as the alt case. It is not a mock-up of a document,
    which is the thing Section 4.9 rules out.
    """
    return (f'<article class="doc-tile" title="{doc_name(row)}">'
            f'<div class="doc-thumb" aria-hidden="true">{row.ini}</div>'
            f'<p class="doc-file">{row.vendor.split()[0]}</p>'
            f'<p class="doc-amt">{row.total} €</p></article>')


def docs_part() -> str:
    """Six tiles for six things: five documents, one count. Never more.

    A scrolling strip would mean lazy loading, a scroll affordance and a
    virtualization story for something nobody flicks through. Six is enough to
    recognise a batch, and the sheet below lists all 37 by name anyway.
    """
    tiles = "".join(tile(r) for r in TILES)
    return f"""<section class="part part-docs">
      <div>
        <h2 class="part-head"><span class="ftype">pdf</span>36 documents</h2>
        <p class="part-note">The vendors&rsquo; own files, renamed by date so the folder sorts
          itself. Five of the 36 shown.</p>
      </div>
      <figure class="docs-figure">
        <div class="doc-grid">{tiles}
          <article class="doc-tile is-more"><div class="doc-thumb">+31</div>
            <p class="doc-file">more</p></article>
        </div>
        <figcaption class="sr-only">Five of the 36 documents in this download, each with the
          amount on the invoice.</figcaption>
      </figure>
    </section>"""


def blank(value: str, cls: str) -> str:
    """A cell the extractor had nothing for.

    A hyphen, not an empty cell: blank reads as "we forgot to render it", a
    dash reads as "this invoice does not carry one", which is the truth for
    every receipt parsed out of a mail body. v2 used an em dash here; Section
    7.D bans it in visible output, data included.
    """
    return f'<td class="{cls}">{value}</td>' if value else f'<td class="{cls} is-none">-</td>'


def sheet_row(row: Row, n: int) -> str:
    doc_cell = (f'<td class="c-doc">{doc_name(row)}</td>' if row.doc else
                '<td class="c-doc is-none" title="Read from an email body, no attachment">'
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


def csv_part() -> str:
    """A plain sheet: hairline grid, tabular figures, counts on the last line.

    Columns are what backend/extract.py actually yields, the net/VAT split
    included, because that is what the batch is for. No currency column: the
    whole batch is EUR, and one would only earn its width if a share ever
    mixed two.

    Eight is the ceiling, and the ninth column is not data: it is the count of
    columns the CSV carries and the page does not. Without it the sheet reads
    as the whole truth and invoices.csv looks like a duplicate of it.
    """
    rows = "".join(sheet_row(r, i + 1) for i, r in enumerate(ROWS))
    more = ('<th class="c-more" scope="col" data-wide="+15" data-mid="+18" data-narrow="+19" '
            f'title="Also in invoices.csv: {CSV_ONLY}"></th>')
    return f"""<section class="part part-csv">
      <div>
        <h2 class="part-head"><span class="ftype">csv</span>invoices.csv</h2>
        <p class="part-note">One row per invoice, 22 columns. Everything the extractor read,
          including where it read it from.</p>
      </div>
      <div class="sheet-wrap">
      <table class="sheet">
      <caption class="sr-only">Every invoice in this download, with the filename it carries
        inside the zip.</caption>
      <thead><tr>
      <th class="c-num" scope="col">#</th><th class="c-vendor" scope="col">Vendor</th>
      <th class="c-inv" scope="col">Invoice&nbsp;#</th>
      <th class="c-doc" scope="col">Document</th><th class="c-date" scope="col">Issued</th>
      <th class="c-money" scope="col">Net</th><th class="c-money" scope="col">VAT</th>
      <th class="c-amt" scope="col">Total&nbsp;€</th>{more}</tr></thead>
      <tbody>{rows}<tr class="more"><td class="c-num">…</td>
        <td colspan="8">27 more rows</td></tr></tbody>
      <tfoot><tr><td class="c-num"></td><td class="c-vendor">37 invoices</td>
        <td class="c-inv"></td><td class="c-doc">36 documents</td>
        <td class="c-date"></td><td class="c-money"></td><td class="c-money"></td>
        <td class="c-amt"></td><td class="c-more"></td></tr></tfoot></table></div>
    </section>"""


# A public page with no privacy line and no terms link is an omission
# (Section 6.A); two links is the whole of it. A four-column link farm on a
# page someone opens once would be worse than leaving it empty.
SHARE_FOOT = """<footer class="share-foot">
    <span>invoices.csv carries all 22 columns per invoice.</span>
    <span class="spacer"></span>
    <span>1 invoice has no document; it rides along in the CSV.</span>
    <nav aria-label="Legal"><a href="#privacy">Privacy</a><a href="#terms">Terms</a></nav>
  </footer>"""


def share_page(*, owner: bool, banner: str = "", composer: str = "",
               action: str = DOWNLOAD, editing: bool = False) -> str:
    """Owner and recipient are the same page.

    There is no what-they-will-see mode to keep in step with what they
    actually see, and no doubt in the owner's mind about whether the preview
    was accurate. The rail's owner block is the entire difference.
    """
    return f"""<main id="content" class="share-main">
  {masthead(owner)}
  {banner}
  <div class="share-cols">
    {rail(owner, action, editing)}
    <div class="stack">
      {composer}
      <div class="doc-card">
        {docs_part()}
        {csv_part()}
      </div>
    </div>
  </div>
  {SHARE_FOOT}
</main>"""


# ---------------------------------------------------------------- composer --
def from_field(menu_open: bool = False) -> str:
    """The sending mailbox: an address, and a caret only if there is a choice.

    A closed menu is the resting state, so what the row says is simply which
    mailbox this goes out as, the way it would read on a sent message. Not a
    <select>: a form control frames a settled fact as a question.
    """
    if len(ACCOUNTS) == 1:
        return f'<span class="from-current">{I_GMAIL}{ACCOUNTS[0]}</span>'

    # Static mockup: the caret toggles between two screens instead of a menu.
    href = "04-compose.html" if menu_open else "05-from.html"
    opts = "".join(
        f'<a class="from-opt{" is-current" if i == 0 else ""}" href="04-compose.html">'
        f'{I_GMAIL}{mail}{f"<span class=tick>{I_TICK}</span>" if i == 0 else ""}</a>'
        for i, mail in enumerate(ACCOUNTS)
    )
    menu = f'<div class="from-menu" role="menu">{opts}</div>' if menu_open else ""
    return (
        f'<span class="from-anchor"><span class="from-current">{I_GMAIL}{ACCOUNTS[0]}</span>'
        f'<a class="icon-btn{" is-active" if menu_open else ""}" href="{href}" '
        f'aria-label="Send from a different mailbox" aria-expanded="{str(menu_open).lower()}">'
        f'{I_CARET}</a>{menu}</span>'
    )


MAIL_ERROR = f"""
      <p class="mail-error">{I_ALERT}<span><b>Could not send.</b> Unipile returned
        <code>HTTP 401, account credentials need reauthorising</code>.
        Your address is still here, and the link is live either way: copy it and send it yourself,
        or reconnect the mailbox and try again.</span></p>"""

# Client-side validation, which v1 had none of. Checked on blur, before
# anything is sent, and it says what is wrong rather than that something is.
INVALID = """
      <p class="field-error" id="to-error">That address is missing its domain.
        Did you mean <b>anna@ledger.co</b>?</p>"""


def composer(error: str = "", menu_open: bool = False, invalid: bool = False) -> str:
    """One address to fill, nothing else, and the actual mail underneath it.

    No note field: an optional message box is a decision every sender then has
    to make, and the draft already says everything the recipient needs.

    The preview is the same document the API sends, in an iframe over the
    rendered draft, so what the sender approves and what the recipient opens
    cannot diverge.
    """
    value = "anna@ledger" if invalid else "anna@ledger.co"
    attrs = (' aria-invalid="true" aria-describedby="to-error"' if invalid else "")
    send = ('<span class="btn btn-primary" aria-disabled="true">' + I_MAIL + 'Send</span>'
            if invalid else
            f'<a class="btn btn-primary" href="06-sent.html">{I_MAIL}Send</a>')
    return f"""<div class="composer">
      <h2>Send this link by email</h2>
      <p class="composer-lede">The subject and the body are already written. The only thing
        missing is who it goes to.</p>
      <div class="field"><span class="field-label">From</span>{from_field(menu_open)}
        <span class="field-note">Replies come back here</span></div>
      <div class="field"><label for="to">To</label>
        <input id="to" name="to" type="email" required autocomplete="email"
          placeholder="accountant@firm.com" value="{value}"{attrs}/></div>{INVALID if invalid else ''}
      <div class="composer-foot">
        {send}
        <a class="btn-quiet" href="03-preview.html">Cancel</a>
        <span class="hint">Subject: <b>{SUBJECT}</b>.
          The link is sent, not the files.</span>
      </div>{error}
      <div class="mail-preview">
        <div class="mail-preview-head">Preview: what anna@ledger.co opens
          <a href="email.html" target="_blank" rel="noopener">Full size {I_OPEN}</a></div>
        <iframe src="email.html" title="Preview of the email that will be sent" loading="lazy"></iframe>
      </div>
    </div>"""


SENT_BANNER = f"""<p class="banner" role="status"><span class="tick">{I_TICK}</span>
      <span>Sent to <b>anna@ledger.co</b> from martin@kirov.dev. Replies come back to you.</span>
      <a class="btn-quiet undo" href="04-compose.html">Send to someone else</a></p>"""


# ---------------------------------------------------------------- loading ---
# Shaped like the page it stands in for, so nothing jumps when the manifest
# lands. It does not shimmer: a placeholder that animates for the length of a
# request is a perpetual loop, and the shape already reads as "not here yet".
def loading_page() -> str:
    tiles = "".join('<div class="doc-tile"><div class="skel skel-thumb"></div>'
                    '<span class="skel skel-line"></span>'
                    '<span class="skel skel-line is-short"></span></div>' for _ in range(6))
    rows = "".join('<div class="skel skel-row"></div>' for _ in range(7))
    facts_skel = "".join(
        f"<div><dt>{k}</dt><dd><span class=\"skel skel-fact\"></span></dd></div>"
        for k in ("Invoices", "Documents", "Size", "Period")
    )
    return f"""<main id="content" class="share-main">
  {masthead(False)}
  <div class="share-cols">
    <section class="rail" aria-busy="true" aria-label="Loading this share">
      <div>
        <p class="rail-kicker"><span class="ftype">zip</span>One download, no account needed</p>
        <h1 class="batch-name"><span class="sr-only">Loading this share</span>
          <span class="skel skel-name"></span></h1>
      </div>
      <dl class="facts" aria-hidden="true">{facts_skel}</dl>
      <div class="get"><div class="skel skel-btn"></div></div>
    </section>
    <div class="stack">
      <div class="doc-card" aria-busy="true">
        <section class="part part-docs">
          <div>
            <h2 class="part-head"><span class="ftype">pdf</span>Documents</h2>
            <p class="part-note">Loading the manifest.</p>
          </div>
          <div class="doc-grid">{tiles}</div>
        </section>
        <section class="part part-csv"><div class="skel-sheet">{rows}</div></section>
      </div>
    </div>
  </div>
  {SHARE_FOOT}
</main>"""


# ---------------------------------------------------------------- dead ends -
# A dead end has no batch, so it gets none of the batch's footnotes. Only the
# two links a public page owes anyone (Section 6.A).
DEAD_FOOT = """<footer class="share-foot">
    <span class="spacer"></span>
    <nav aria-label="Legal"><a href="#privacy">Privacy</a><a href="#terms">Terms</a></nav>
  </footer>"""


def dead(mark: str, title: str, body: str, actions: str, desc_id: str) -> str:
    return f"""<main id="content" class="share-main">
  {masthead(False)}
  <section class="dead" aria-labelledby="{desc_id}">
    <span class="dead-mark">{mark}</span>
    <h1 id="{desc_id}">{title}</h1>
    {body}
    <div class="dead-actions">{actions}</div>
  </section>
  {DEAD_FOOT}
</main>"""


# Nobody turned this off: the seven days ran out. The page says whose link it
# was and when it lapsed, because both are things the recipient would otherwise
# have to ask for, and asking is the only way out of this screen.
EXPIRED = dead(
    I_EXPIRED,
    "This link has expired",
    f"<p>{OWNER_NAME} shared these invoices on {MADE_ON}, and share links stop working seven "
    f"days later. It lapsed on {EXPIRES}. Nothing was deleted; ask for a new link and it takes "
    "two clicks.</p>"
    "<p class='quiet'>Every link expires on its own, and a new one gets a new address.</p>",
    f'<a class="btn btn-primary" href="mailto:{OWNER_MAIL}">{I_MAIL}Email {OWNER_NAME.split()[0]}</a>'
    f'<a class="btn-quiet" href="index.html">{I_BACK}Back to the flow</a>',
    "expired-title",
)

# A mistyped or truncated token is the likeliest way anyone lands here, so the
# page says that rather than "page not found".
NOT_FOUND = dead(
    I_LOST,
    "There is nothing at this link",
    "<p>The address is not one we recognise. Links that break across two lines in an email are "
    "the usual cause, so check that the whole thing after <code>/s/</code> made it, all 22 "
    "characters.</p>"
    "<p class='quiet'>A link that has run out of time says so instead, and names the day it "
    "did. This one was never an address at all.</p>",
    f'<a class="btn btn-primary" href="03-preview.html">{I_BACK}Try the link again</a>'
    '<a class="btn-quiet" href="index.html">Back to the flow</a>',
    "notfound-title",
)


# ---------------------------------------------------------------- write -----
D_DASH = "The invoice table, with one new control in the toolbar: share."
D_ROW = "One invoice opened in place: the document, beside every field read off it."
D_SHARE = "37 invoices from April to June 2026, in one download. No account needed."

SCREENS = {
    "01-idle.html": ("The Share button", dashboard(), D_DASH, ""),
    "01b-row.html": ("The row, opened", dashboard(opened="Hetzner Online GmbH"), D_ROW, ""),
    "02-link.html": ("Link created", dashboard(POPOVER), D_DASH, ""),
    "03-preview.html": ("The share page", share_page(owner=True), D_SHARE, "share-page"),
    "03b-name.html": ("Correcting the name",
                      share_page(owner=True, editing=True), D_SHARE, "share-page"),
    "04-compose.html": ("Composer", share_page(owner=True, composer=composer()), D_SHARE, "share-page"),
    "05-from.html": ("Choosing the mailbox",
                     share_page(owner=True, composer=composer(menu_open=True)), D_SHARE, "share-page"),
    "06-sent.html": ("Sent", share_page(owner=True, banner=SENT_BANNER), D_SHARE, "share-page"),
    "07-recipient.html": ("Recipient's view", share_page(owner=False), D_SHARE, "share-page"),
    "08-send-failed.html": ("Send failed",
                            share_page(owner=True, composer=composer(MAIL_ERROR)), D_SHARE, "share-page"),
    "09-expired.html": ("Expired", EXPIRED, "This share link has run out of time.", "share-page"),
    "10-loading.html": ("Loading", loading_page(), D_SHARE, "share-page"),
    "11-zipping.html": ("Preparing the download",
                        share_page(owner=False, action=ZIPPING), D_SHARE, "share-page"),
    "12-invalid.html": ("Address needs fixing",
                        share_page(owner=True, composer=composer(invalid=True)), D_SHARE, "share-page"),
    "13-not-found.html": ("Nothing at this link",
                          NOT_FOUND, "This share link does not exist.", "share-page"),
}

for name, (title, body, desc, cls) in SCREENS.items():
    (OUT / name).write_text(page(title, body, desc=desc, body_class=cls), encoding="utf-8")
    print("wrote", name)
