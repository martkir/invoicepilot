"""The mail a share can be sent with, and the one call that sends it.

One renderer, used twice: the composer's iframe loads exactly what the send
hands to Unipile. A preview that can drift from the real template is worse than
no preview, because it is believed.

600px, tables, inline styles, no external stylesheet — the shape that survives
Outlook. The palette is duplicated from the product's tokens on purpose: mail
clients strip <link> and most <style>, so nothing here can reference them.
"""

from dataclasses import dataclass
from datetime import datetime
from html import escape

from invoicepilot.shares import Snapshot, Summary
from invoicepilot.unipile import send_email

# Mercury, light. If the tokens move, these move with them.
CANVAS = "#eef0f6"
CARD = "#fbfcfd"
BAND = "#e4e6ef"
BORDER = "#c9cad0"
HAIRLINE = "#e6e7ea"
INK = "#1e1e2a"
MUTED = "#5a5a66"
ACCENT = "#5266eb"

SANS = "'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "'Geist Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


@dataclass(frozen=True)
class Draft:
    """What goes to Unipile, and what the composer's iframe shows."""

    subject: str
    html: str


def subject(summary: Summary) -> str:
    """What the mail's subject line says this batch is.

    Its own function because the composer quotes it before anything is sent —
    the share page asks for it, rather than assembling a second version of this
    sentence in the browser.
    """
    if summary.months:
        return f"Invoices, {summary.months} ({summary.invoices} invoices)"
    return f"Invoices ({summary.invoices})"


def draft(snapshot: Snapshot, url: str) -> Draft:
    """The mail for one share: who sent it, what is in it, and where to get it.

    Deliberately carries no thumbnails, no vendor list and no total. The page
    has all of that, and an inbox is not where anyone reviews 37 invoices — the
    mail's whole job is who sent this, what is it, where do I get it.
    """
    share, summary = snapshot.share, snapshot.summary
    line = subject(summary)
    return Draft(
        subject=line,
        html=_document(
            summary,
            subject=line,
            # The heading is on first-name terms because the recipient knows
            # the sender; the footer says the full name once.
            first=escape((share.owner_name.split() or [share.owner_name])[0]),
            what=f"{summary.label} invoices" if summary.label else "invoices",
            expires=_day(share.expires_at),
            link=escape(url, quote=True),
            # Shown without its scheme, the way a URL reads in print.
            plain_link=escape(url.split("://", 1)[-1]),
        ),
    )


def send(
    base: str,
    api_key: str,
    account_id: str,
    *,
    to: str,
    mail: Draft,
) -> None:
    """Hand the mail to Unipile, to go out as the connected mailbox.

    Nothing is written down: no table records that a share was mailed. The link
    was live before the mail and stays live if it fails, which is why the
    composer can stay open on an error and simply try again.
    """
    send_email(base, api_key, account_id, to=to, subject=mail.subject, body=mail.html)


def _document(
    summary: Summary,
    *,
    subject: str,
    first: str,
    what: str,
    expires: str,
    link: str,
    plain_link: str,
) -> str:
    """The mail itself. Every value reaching markup is escaped by the caller."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="light"/>
<meta name="supported-color-schemes" content="light"/>
<title>{subject}</title>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet"/>
</head>
<body style="margin:0;padding:0;background:{CANVAS};">

<div style="display:none;max-height:0;overflow:hidden;opacity:0;">
  {summary.invoices} invoices, {escape(summary.period or "undated")}, in one download. No account needed.
</div>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:{CANVAS};padding:32px 12px;">
<tr><td align="center">

  <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
         style="width:600px;max-width:100%;background:{CARD};border-radius:16px;overflow:hidden;
                border:1px solid {BORDER};font-family:{SANS};">

    <tr><td style="background:{BAND};border-bottom:1px solid {BORDER};padding:24px 30px 28px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-size:16px;font-weight:500;color:{INK};letter-spacing:-.01em;">
            Invoice&nbsp;Pilot
          </td>
          <td align="right" style="font-size:12px;line-height:1.5;color:{MUTED};font-family:{MONO};">
            {summary.invoices} invoices<br/>{escape(summary.months or "")}
          </td>
        </tr>
      </table>
      <div style="padding-top:24px;font-size:26px;line-height:1.2;font-weight:500;color:{INK};
                  letter-spacing:-.02em;">
        {first} shared {what} with you
      </div>
      <div style="padding-top:10px;font-size:14px;line-height:1.5;color:{MUTED};">
        Every invoice in the batch, in one download
      </div>
    </td></tr>

    <tr><td style="padding:26px 30px 0;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        {_fact("Invoices", str(summary.invoices))}
        {_fact("Period", escape(summary.period)) if summary.period else ""}
        <tr>
          <td style="padding:12px 0;font-size:14px;color:{MUTED};">Download
            <div style="padding-top:4px;font-size:12px;color:{MUTED};">
              {summary.documents} PDFs and invoices.csv
            </div>
          </td>
          <td align="right" style="padding:12px 0;font-size:14px;color:{INK};font-family:{MONO};">
            {escape(summary.filename)}
            <div style="padding-top:4px;font-size:12px;color:{MUTED};">{_size(summary.bytes)}</div>
          </td>
        </tr>
        <tr><td colspan="2" style="border-top:1px solid {BORDER};font-size:0;line-height:0;">&nbsp;</td></tr>
      </table>
    </td></tr>

    <tr><td style="padding:24px 30px 0;">
      <a href="{link}"
         style="display:block;padding:16px 0;background:{ACCENT};color:#ffffff;font-size:16px;
                font-weight:500;text-align:center;text-decoration:none;border-radius:9999px;">
        View and download
      </a>
      <div style="padding-top:14px;font-size:12px;line-height:1.6;color:{MUTED};">
        The page lists every invoice with its amount, date and filename, so you can check the batch
        before you download it. No account, nothing to install.
      </div>
    </td></tr>

    <tr><td style="height:28px;font-size:0;line-height:0;">&nbsp;</td></tr>

  </table>

  <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
         style="width:600px;max-width:100%;font-family:{SANS};">
    <tr><td align="center" style="padding:20px 24px 0;font-size:12px;line-height:1.75;color:{MUTED};">
      Anyone with this link can download these invoices, until it expires on {expires}.<br/>
      <a href="{link}" style="color:#33333f;font-family:{MONO};">{plain_link}</a><br/>
      Sent with Invoice Pilot on {first}&rsquo;s behalf. Reply to this message to reach them.
    </td></tr>
  </table>

</td></tr>
</table>

</body>
</html>
"""


def _fact(label: str, value: str) -> str:
    """One label/value line of the receipt block, and the hairline under it."""
    return f"""<tr>
          <td style="padding:12px 0;font-size:14px;color:{MUTED};">{label}</td>
          <td align="right" style="padding:12px 0;font-size:14px;color:{INK};font-family:{MONO};">
            {value}
          </td>
        </tr>
        <tr><td colspan="2" style="border-top:1px solid {HAIRLINE};font-size:0;line-height:0;">&nbsp;</td></tr>"""


def _size(size: int) -> str:
    """`12.4 MB` — the figure a recipient checks against what they downloaded."""
    if size >= 1_000_000:
        return f"{size / 1_000_000:.1f} MB"
    if size >= 1_000:
        return f"{size / 1_000:.0f} KB"
    return f"{size} bytes"


def _day(when: datetime) -> str:
    """`12 July 2026` — a date a person reads, in the footer of the mail."""
    return f"{when.day} {when:%B} {when.year}"
