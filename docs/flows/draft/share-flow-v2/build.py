"""Regenerate the redesigned share-flow screens:
`python3 docs/flows/share-flow-v2/build.py`

Same generator idea as share-flow/build.py — the screens share most of their
markup, so writing them by hand guarantees they drift — but the markup itself
is the redesign. Structural changes against v1 that live in this file rather
than in the CSS:

  · <header>, <main>, <footer>, <section>, <figure>, <dl>, <nav> in place of
    v1's div soup, and an <h1> on the share page, which v1 never had: its
    first heading was the composer's <h3>.
  · A skip link, a real <title>/description/og block and a favicon on every
    screen. v1 had none of the four.
  · One icon set, drawn on one grid at one stroke weight. v1 mixed Lucide
    paths at 1.8 / 2 / 2.2 / 2.4.
  · Four states v1 did not draw: loading, download-in-progress,
    invalid-address, and a 404 for a mistyped token.
  · Amounts that look extracted rather than invented — see ROWS.

Not generated here: index.html (the contact sheet), email.html (the draft),
viewer.html, and the three stylesheets. Those are one-offs, edited directly.
"""

from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

OUT = Path(__file__).parent

# ---------------------------------------------------------------- data ------
# Columns match what backend/extract.py actually produces — see the real
# payloads under .data/. `invoice_no`, `net` and `vat` are blank for the Bolt
# row on purpose: that one is a ride receipt read out of the mail body, and it
# genuinely carries only issuer, date, amount, currency and VAT number. Every
# column below has to survive being empty.
#
# The amounts changed from v1. Half of them were 16.00 / 20.00 / 45.00 /
# 84.00 / 480.00 — the round numbers of a mockup, not the output of an
# extractor. These are net + VAT figures that add up: 19% where the vendor
# charges German VAT, 0% where it is reverse-charged, and one ride receipt
# with no split at all.
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
    Row("Amazon Web Services", "AW", "#232F3E", "EUINV22-441907", "733.97", "139.45", "873.42", "05.04.2026", True),
    Row("Notion Labs Inc.", "No", "#191918", "8F21C4-0031", "21.60", "0.00", "21.60", "06.04.2026", True),
    Row("Figma Inc.", "Fi", "#0D99FF", "INV-90412", "41.85", "0.00", "41.85", "09.04.2026", True),
    Row("Vercel Inc.", "Ve", "#111111", "B7A2-2026-04", "34.72", "0.00", "34.72", "12.04.2026", True),
    Row("Bolt Operations OÜ", "Bo", "#5B1D52", "", "", "", "2.37", "14.04.2026", False),
    Row("Slack Technologies", "Sl", "#4A154B", "SL-2026-77412", "56.25", "11.25", "67.50", "21.04.2026", True),
    Row("GitHub Inc.", "Gi", "#24292F", "GH-4471203", "79.20", "0.00", "79.20", "02.05.2026", True),
    Row("Linear Orbit Inc.", "Li", "#5E6AD2", "LIN-00918", "118.80", "0.00", "118.80", "08.05.2026", True),
    Row("OpenAI LLC", "Op", "#10A37F", "OAI-2026-5590", "342.80", "65.13", "407.93", "19.05.2026", True),
]
LEAVES = ROWS[:5]

LINK = "invoicepilot.app/s/7Kq2mXbN4vRt9wLpZaHc3f"
ZIP_NAME = "invoices-2026-Q2.zip"

# Two mailboxes on purpose: it is the only way to see the From picker, which
# does not exist when there is nothing to pick between.
ACCOUNTS = ["martin@kirov.dev", "billing@kirov.dev"]

# invoices.csv carries 22 columns per invoice; seven of them are on screen
# (vendor, invoice number, file, issued, net, VAT, total — "#" is a row number,
# not data). These are the rest, and they are what the "+15" column counts.
CSV_ONLY = ("VAT number, company number, currency, payment reference, service date, description, "
            "file size, SHA-256, source, mailbox, email subject, received, message id, "
            "extracted at, extracted by")

# ---------------------------------------------------------------- icons -----
# One set, one grid, one stroke weight.
#
# v1 used Lucide — the default AI icon choice — and used it at four different
# stroke widths, so the toolbar had thin icons sitting next to fat ones. These
# are drawn inside a 20px live area of the 24px box at 1.6 with round joins,
# which is the only rule the set has. The metaphors are unchanged: none of
# them was a cliché worth replacing (no rocket for "launch", no shield for
# "secure"), and an envelope that is not an envelope helps nobody.


def icon(path: str, size: int = 16, extra: str = "") -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true"{extra}>{path}</svg>')


I_SHARE = icon('<path d="M12 15.5V3.6"/><path d="m8.2 7.2 3.8-3.6 3.8 3.6"/>'
               '<path d="M5 13v4.9A2.1 2.1 0 0 0 7.1 20h9.8a2.1 2.1 0 0 0 2.1-2.1V13"/>')
I_DL = icon('<path d="M12 3.6v11.9"/><path d="m8.2 11.9 3.8 3.6 3.8-3.6"/>'
            '<path d="M5 13v4.9A2.1 2.1 0 0 0 7.1 20h9.8a2.1 2.1 0 0 0 2.1-2.1V13"/>')
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
I_ALERT = icon('<circle cx="12" cy="12" r="8.6"/><path d="M12 7.8v4.6"/><path d="M12 16.1h.01"/>', 15)
I_REVOKED = icon('<circle cx="12" cy="12" r="8.6"/><path d="m6.4 6.4 11.2 11.2"/>', 22)
I_LOST = icon('<circle cx="10.8" cy="10.8" r="6.8"/><path d="m15.7 15.7 4.7 4.7"/>'
              '<path d="M8.6 8.6 13 13"/><path d="M13 8.6 8.6 13"/>', 22)
I_BACK = icon('<path d="M19.4 12H4.6"/><path d="m10.4 5.6-5.8 6.4 5.8 6.4"/>', 15)

# The wordmark. A document with a folded corner — the thing the product moves
# around — rather than the two initials v1 set in a red square.
I_MARK = ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
          'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
          '<path d="M13.4 3.4H7.9A2.3 2.3 0 0 0 5.6 5.7v12.6a2.3 2.3 0 0 0 2.3 2.3h8.2a2.3 2.3 0 0 0 '
          '2.3-2.3V8.3Z"/><path d="M13.4 3.4v4.9h4.7"/></svg>')

# Kept as-is: a provider's own mark is a brand asset, not part of the icon set.
I_GMAIL = ('<svg class="source-mark" viewBox="0 0 24 24" aria-hidden="true">'
           '<path fill="#EA4335" d="M12 10.2V14h5.3c-.2 1.2-1.6 3.6-5.3 3.6A5.6 5.6 0 1 1 15.7 8l2.7-2.6A9.3 '
           '9.3 0 0 0 12 3a9 9 0 1 0 0 18c5.2 0 8.6-3.6 8.6-8.7 0-.6 0-1-.1-1.5H12z"/></svg>')

# ---------------------------------------------------------------- shell -----
# A favicon, which v1 did not have on any screen: the wordmark glyph on the
# accent, inlined so it costs no request.
FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<rect width="24" height="24" rx="6" fill="#A8382C"/>'
    '<path d="M13.4 4.4H8.4A2 2 0 0 0 6.4 6.4v11.2a2 2 0 0 0 2 2h7.2a2 2 0 0 0 2-2V8.4Z" '
    'fill="none" stroke="#fff" stroke-width="1.7" stroke-linejoin="round"/>'
    '<path d="M13.4 4.4v4h4" fill="none" stroke="#fff" stroke-width="1.7" stroke-linejoin="round"/>'
    '</svg>'
)
FAVICON = "data:image/svg+xml," + quote(FAVICON_SVG, safe="")


def page(title: str, body: str, *, desc: str, body_class: str = "") -> str:
    """One <head> for every screen.

    v1 emitted a title and nothing else — no description, no social card, no
    favicon, no theme colour. The share page is a public URL that gets pasted
    into Slack and WhatsApp, so the og: block is not decoration: it is what
    the recipient sees before they decide to click.
    """
    cls = f' class="{body_class}"' if body_class else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title} · Invoice Pilot</title>
<meta name="description" content="{desc}"/>
<meta property="og:type" content="website"/>
<meta property="og:title" content="{title} · Invoice Pilot"/>
<meta property="og:description" content="{desc}"/>
<meta name="theme-color" content="#A8382C"/>
<link rel="icon" href="{FAVICON}"/>
<link rel="stylesheet" href="../../../frontend/src/styles/tokens.css"/>
<link rel="stylesheet" href="../../../frontend/src/styles/dashboard.css"/>
<link rel="stylesheet" href="tokens-v2.css"/>
<link rel="stylesheet" href="redesign.css"/>
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
    return (
        '<section class="card sources" aria-label="Email sources">'
        '<h2 class="card-label">Email sources</h2>'
        f'{rows}'
        f'<button class="add-source">{plus}Add source</button>'
        f'<p class="accounts-note"><span class="dot"></span>{len(ACCOUNTS)} accounts connected</p>'
        '</section>'
    )


def dash_row(row: Row, checked: bool) -> str:
    mark = ' checked' if checked else ''
    cls = ' class="selected"' if checked else ''
    return (
        f'<tr{cls}><td class="col-check">'
        f'<input type="checkbox" aria-label="Select {row.vendor}"{mark}></td>'
        f'<td><div class="vendor"><span class="vendor-logo" style="background:{row.colour}" '
        f'aria-hidden="true">{row.ini}</span>'
        f'<span class="vendor-name">{row.vendor}</span></div></td>'
        f'<td class="col-amount">{row.total} €</td><td class="col-issued">{row.issued}</td>'
        f'<td class="col-actions"><div class="row-actions">'
        f'<button class="icon-btn" aria-label="Preview {row.vendor}">{I_EYE}</button>'
        f'<button class="icon-btn" aria-label="Download {row.vendor}">{I_DL}</button>'
        f'</div></td></tr>'
    )


def dashboard(popover: str = "", checked: bool = False) -> str:
    rows = "".join(dash_row(r, checked) for r in ROWS)
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
          <button class="icon-btn{pop_cls}" aria-label="Share these invoices"
            aria-expanded="{'true' if popover else 'false'}">{I_SHARE}</button>
          {popover}
        </span>
        <button class="icon-btn" aria-label="Download selected invoices">{I_DL}</button>
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


# The popover reports; it does not ask. Two changes from v1: the actions are
# no longer a filled button next to an outlined one — a matched pair reads as
# two equal decisions when only one of them is the point — and the second is a
# text link, which is the tertiary rung v1's button set did not have.
POPOVER = f"""<div class="share-pop" role="status">
            <p class="pop-title"><span class="ok">{I_TICK}</span>Link copied</p>
            <p class="pop-sub">All 37 invoices, Apr 1 – Jun 30. Anyone with this link can view and
            download them. It stays live until you revoke it.</p>
            <div class="link-row"><code>{LINK}</code>
              <button class="icon-btn" aria-label="Copy the link again">{I_COPY}</button></div>
            <div class="pop-actions">
              <a class="btn btn-primary btn-grow" href="03-preview.html">{I_OPEN}Open the link</a>
              <a class="btn-quiet" href="04-compose.html">{I_MAIL}Send by email</a>
            </div>
          </div>"""


# ---------------------------------------------------------------- share page
def masthead(owner: bool) -> str:
    who = ('<p class="shared-by">Your link<b>martin@kirov.dev</b></p>' if owner else
           '<p class="shared-by">Shared with you by<b>Martin Kirov</b>martin@kirov.dev</p>')
    return (f'<header class="masthead"><a class="brand" href="index.html">'
            f'<span class="mark">{I_MARK}</span>Invoice Pilot</a>{who}</header>')


def owner_bar() -> str:
    """The only thing that differs between the owner's page and everyone
    else's, and the reason there is no separate preview mode to keep in step.

    Sticky, because Revoke should be reachable from the bottom of a 37-row
    sheet without scrolling back to the top.
    """
    return f"""<div class="owner-bar">
    <span class="live">This link is live</span>
    <span>anyone with it can download these invoices</span>
    <span class="spacer"></span>
    <a class="btn" href="04-compose.html">{I_MAIL}Send by email</a>
    <a class="revoke" href="09-revoked.html">Revoke</a>
  </div>"""


def facts() -> str:
    pairs = [("Invoices", "37"), ("Documents", "36"),
             ("Size", "12.4 MB"), ("Period", "Apr 1 – Jun 30, 2026")]
    items = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in pairs)
    return f'<dl class="facts">{items}</dl>'


def batch(action: str) -> str:
    """The header band.

    v1 opened on a 15px row: filename, count and size on one line, with the
    download button beside it. The filename is the answer to the only
    question the page has to settle before anyone clicks — is this the right
    export? — so here it is the largest thing on the screen, and the four
    facts under it are labelled rather than run together with separators.
    """
    return f"""<section class="batch" aria-labelledby="batch-name">
    <div>
      <p class="batch-kicker"><span class="ftype is-zip">zip</span>One download, no account needed</p>
      <h1 class="batch-name" id="batch-name">{ZIP_NAME}</h1>
      {facts()}
    </div>
    {action}
  </section>"""


DOWNLOAD = f"""<div class="get">
      <a class="btn btn-primary btn-lg" href="11-zipping.html">{I_DL}Download all</a>
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


def leaf(row: Row, i: int) -> str:
    """One sheet in the fan.

    Not a link and not a button: nothing on this page opens a single
    document — no overlay, no pdf.js, no viewer screen. Whoever wants to read
    one downloads the zip and opens it in the reader they already have.
    """
    if not row.doc:
        inner = "No document —<br/>read from the<br/>email body"
        return f'<div class="leaf is-textonly" style="--i:{i}">{inner}</div>'
    return (
        f'<div class="leaf" style="--i:{i}">'
        f'<div class="leaf-mark" style="background:{row.colour}">{row.ini}</div>'
        '<div class="leaf-line w-70"></div><div class="leaf-line w-52"></div>'
        '<div class="leaf-line w-80 gap"></div><div class="leaf-line w-74"></div>'
        '<div class="leaf-line w-40"></div>'
        f'<div class="leaf-foot"><div class="leaf-vendor">{row.vendor.split()[0]}</div>'
        f'<div class="leaf-total">{row.total} €</div></div></div>'
    )


def docs_part() -> str:
    """Exactly five thumbnails and a count. Never more.

    A scrolling strip would mean lazy loading, a scroll affordance and a
    virtualization story for something nobody flicks through. Five is enough
    to recognise a batch, and the sheet below lists all 37 by name anyway.

    Redesigned as a fan rather than a row of five equal boxes: overlapped,
    each turned about a degree off square, so the block reads as a stack of
    paper instead of as five more cards.
    """
    leaves = "".join(leaf(r, i) for i, r in enumerate(LEAVES))
    return f"""<section class="part part-docs">
      <div>
        <h2 class="part-head"><span class="ftype is-pdf">pdf</span>36 documents</h2>
        <p class="part-note">The vendors&rsquo; own files, renamed by date so the folder sorts
          itself. Five of the 36 shown.</p>
      </div>
      <figure class="fan">{leaves}<div class="leaf is-more" style="--i:5">+32</div>
        <figcaption class="sr-only">First pages of five of the 36 documents in this download.</figcaption>
      </figure>
    </section>"""


def doc_name(row: Row) -> str:
    """The entry name this invoice gets inside the zip.

    Same shape as invoice_store.folder_name() — date first, so the
    recipient's folder sorts itself. Showing it here is what makes the sheet
    a manifest rather than a second copy of the dashboard.
    """
    if not row.doc:
        return ""
    d, m, y = row.issued.split(".")
    slug = row.vendor.split()[0].lower().strip(".")
    return f"{y}-{m}-{d}__{slug}__{row.total}EUR.pdf"


def blank(value: str, cls: str) -> str:
    """A cell the extractor had nothing for.

    An em dash, not an empty cell: blank reads as "we forgot to render it", a
    dash reads as "this invoice does not carry one" — which is the truth for
    every receipt parsed out of a mail body.
    """
    return f'<td class="{cls}">{value}</td>' if value else f'<td class="{cls} is-none">—</td>'


def sheet_row(row: Row, n: int) -> str:
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


def csv_part() -> str:
    """A plain sheet: hairline grid, tabular figures, counts on the last line.

    Columns are what backend/extract.py actually yields — invoice number and
    the net/VAT split included, because that is what the batch is *for*. No
    currency column: the whole batch is EUR, and one would only earn its
    width if a share ever mixed two.

    Eight is the ceiling, and the ninth column is not data: it is the count of
    columns the CSV carries and the page does not. Without it the sheet reads
    as the whole truth and invoices.csv looks like a duplicate of it.
    """
    rows = "".join(sheet_row(r, i + 1) for i, r in enumerate(ROWS))
    more = ('<th class="c-more" scope="col" data-wide="+15" data-mid="+18" data-narrow="+19" '
            f'title="Also in invoices.csv: {CSV_ONLY}"></th>')
    return f"""<section class="part part-csv">
      <div>
        <h2 class="part-head"><span class="ftype is-csv">csv</span>invoices.csv</h2>
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


# A public page with no privacy line and no terms link is the omission the
# audit calls out; two links is the whole of it. Nothing else belongs here —
# a four-column link farm on a page someone opens once would be worse than
# leaving it empty.
SHARE_FOOT = """<footer class="share-foot">
    <span>invoices.csv carries all 22 columns per invoice.</span>
    <span class="spacer"></span>
    <span>1 invoice has no document; it rides along in the CSV.</span>
    <nav aria-label="Legal"><a href="#privacy">Privacy</a><a href="#terms">Terms</a></nav>
  </footer>"""


def share_page(*, owner: bool, banner: str = "", composer: str = "",
               action: str = DOWNLOAD) -> str:
    """Owner and recipient are the same page.

    There is no what-they-will-see mode to keep in step with what they
    actually see, and no doubt in the owner's mind about whether the preview
    was accurate. The owner strip above is the entire difference.
    """
    # Exactly one element lifts into the header band — whichever comes first.
    # Two overlapping cards would be a pile, not a foreground.
    lifted = f'<div class="lift">{composer}</div>' if composer else ""
    card_cls = "doc-card stacked" if composer else "doc-card lift"
    return f"""{owner_bar() if owner else ''}
<main id="content" class="share-main">
  {masthead(owner)}
  {banner}
  {batch(action)}
  {lifted}
  <div class="{card_cls}">
    {docs_part()}
    {csv_part()}
  </div>
  {SHARE_FOOT}
</main>"""


# ---------------------------------------------------------------- composer --
def from_field(menu_open: bool = False) -> str:
    """The sending mailbox: an address, and a caret only if there is a choice.

    A closed menu is the resting state, so what the row says is simply which
    mailbox this goes out as — the way it would read on a sent message. Not a
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
        <code>HTTP 401 — account credentials need reauthorising</code>.
        Your address is still here, and the link is live either way: copy it and send it yourself,
        or reconnect the mailbox and try again.</span></p>"""

# Client-side validation, which v1 had none of. Checked on blur, before
# anything is sent, and it says what is wrong rather than that something is.
INVALID = """
      <p class="field-error" id="to-error">That address is missing its domain —
        did you mean <b>anna@ledger.co</b>?</p>"""


def composer(error: str = "", menu_open: bool = False, invalid: bool = False) -> str:
    """One address to fill — nothing else — and the actual mail underneath it.

    No note field: an optional message box is a decision every sender then
    has to make, and the draft already says everything the recipient needs.

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
        <span class="hint">Subject: <b>Invoices — Apr–Jun 2026 (37 invoices)</b>.
          The link is sent, not the files.</span>
      </div>{error}
      <div class="mail-preview">
        <div class="mail-preview-head">Preview — what anna@ledger.co opens
          <a href="email.html" target="_blank" rel="noopener">Full size {I_OPEN}</a></div>
        <iframe src="email.html" title="Preview of the email that will be sent" loading="lazy"></iframe>
      </div>
    </div>"""


SENT_BANNER = f"""<p class="banner" role="status"><span class="tick">{I_TICK}</span>
      <span>Sent to <b>anna@ledger.co</b> from martin@kirov.dev. Replies come back to you.</span>
      <a class="btn-quiet undo" href="04-compose.html">Send to someone else</a></p>"""


# ---------------------------------------------------------------- loading ---
# Shaped like the page it stands in for, so nothing jumps when the manifest
# lands. v1 drew no loading state, which in practice means a blank white page
# for the length of a request that has to stream a 37-row manifest.
def loading_page() -> str:
    leaves = "".join('<div class="skel skel-leaf"></div>' for _ in range(5))
    rows = "".join('<div class="skel skel-row"></div>' for _ in range(6))
    return f"""<main id="content" class="share-main">
  {masthead(False)}
  <section class="batch" aria-busy="true" aria-label="Loading this share">
    <div>
      <p class="batch-kicker"><span class="ftype is-zip">zip</span>One download, no account needed</p>
      <h1 class="batch-name"><span class="sr-only">Loading this share</span>
        <span class="skel skel-name"></span></h1>
      <dl class="facts" aria-hidden="true">
        <div><dt>Invoices</dt><dd><span class="skel skel-fact"></span></dd></div>
        <div><dt>Documents</dt><dd><span class="skel skel-fact"></span></dd></div>
        <div><dt>Size</dt><dd><span class="skel skel-fact"></span></dd></div>
      </dl>
    </div>
    <div class="get"><div class="skel skel-btn"></div></div>
  </section>
  <div class="doc-card lift" aria-busy="true">
    <section class="part part-docs">
      <div>
        <h2 class="part-head"><span class="ftype is-pdf">pdf</span>Documents</h2>
        <p class="part-note">Loading the manifest…</p>
      </div>
      <div class="fan">{leaves}</div>
    </section>
    <section class="part part-csv"><div class="skel-sheet">{rows}</div></section>
  </div>
  {SHARE_FOOT}
</main>"""


# ---------------------------------------------------------------- dead ends -
def dead(mark: str, title: str, body: str, actions: str, desc_id: str) -> str:
    return f"""<main id="content" class="share-main">
  {masthead(False)}
  <section class="dead" aria-labelledby="{desc_id}">
    <span class="dead-mark">{mark}</span>
    <h1 id="{desc_id}">{title}</h1>
    {body}
    <div class="dead-actions">{actions}</div>
  </section>
  {SHARE_FOOT}
</main>"""


REVOKED = dead(
    I_REVOKED,
    "This link was turned off",
    "<p>Martin Kirov revoked it, so the invoices behind it are no longer downloadable. "
    "Nothing was deleted — ask him for a new link and it takes him two clicks.</p>"
    "<p class='quiet'>Revoked links stay revoked; a new link gets a new address.</p>",
    f'<a class="btn btn-primary" href="mailto:martin@kirov.dev">{I_MAIL}Email Martin</a>'
    f'<a class="btn-quiet" href="index.html">{I_BACK}Back to the flow</a>',
    "revoked-title",
)

# The 404 v1 did not have. A mistyped or truncated token is the likeliest way
# anyone lands here — a link that broke across two lines in an email — so the
# page says that rather than "page not found".
NOT_FOUND = dead(
    I_LOST,
    "There is nothing at this link",
    "<p>The address is not one we recognise. Links that get broken across two lines in an "
    "email are the usual cause — check that the whole thing after <code>/s/</code> made it, "
    "all 22 characters.</p>"
    "<p class='quiet'>If it was copied whole, the share may have been revoked. "
    "The person who sent it can tell you.</p>",
    f'<a class="btn btn-primary" href="03-preview.html">{I_BACK}Try the link again</a>'
    '<a class="btn-quiet" href="index.html">Back to the flow</a>',
    "notfound-title",
)


# ---------------------------------------------------------------- write -----
D_DASH = "The invoice table, with one new control in the toolbar: share."
D_SHARE = "37 invoices from April to June 2026, in one download. No account needed."

SCREENS = {
    "01-idle.html": ("The share icon", dashboard(), D_DASH, ""),
    "02-link.html": ("Link created", dashboard(POPOVER), D_DASH, ""),
    "03-preview.html": ("The share page", share_page(owner=True), D_SHARE, "share-page"),
    "04-compose.html": ("Composer", share_page(owner=True, composer=composer()), D_SHARE, "share-page"),
    "05-from.html": ("Choosing the mailbox",
                     share_page(owner=True, composer=composer(menu_open=True)), D_SHARE, "share-page"),
    "06-sent.html": ("Sent", share_page(owner=True, banner=SENT_BANNER), D_SHARE, "share-page"),
    "07-recipient.html": ("Recipient's view", share_page(owner=False), D_SHARE, "share-page"),
    "08-send-failed.html": ("Send failed",
                            share_page(owner=True, composer=composer(MAIL_ERROR)), D_SHARE, "share-page"),
    "09-revoked.html": ("Revoked", REVOKED, "This share link has been turned off.", "share-page"),
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
