"""Deciding whether a message is worth treating as an invoice.

A template only reports a document it recognises, so a message that parses to
nothing is ambiguous: either it is not an invoice, or it is one from an issuer
nobody has taught yet. This separates the two deterministically, which is what
makes it affordable to act on the second case — see invoicepilot/learn.py.

Measured against 162 messages from a real mailbox, hand-labelled: 34 of 36
invoices pass, and 2 of 120 non-invoices do. Which way it errs matters more
than either number. A false positive costs one wasted look and files nothing;
a message rejected here is an invoice that is never seen again.

The rule doing most of the work is TOTAL_ADJACENT_RE, and why is worth
recording, because the obvious rule fails: *counting* currency amounts does
not work. Investment newsletters in the same mailbox carry 13 and 31 of them
and outrank every real receipt on that measure. What separates a receipt from
prose about money is a total-shaped label sitting next to a figure — "Total
charged €1.17" — and on that corpus the pattern matched no non-invoice at all.
"""

import re

# One money figure, with the symbol on either side or absent entirely. Absent
# is not an edge case: Telekom's receipt writes "TOTAL 29.00" and states the
# currency once in a column header.
AMOUNT = r"(?:[€$£]\s*)?\d{1,3}(?:[ ,]\d{3})*[.,]\d{2}\s*(?:[€$£]|EUR|USD|GBP|BGN|лв)?"

# What a document calls the figure you actually paid. Multilingual for the same
# reason INVOICE_KEYWORDS is: the vendors are.
TOTAL_LABEL = (
    r"total\s+charged|total\s+price|grand\s+total|amount\s+(?:paid|due|charged)"
    r"|balance\s+due|subtotal|total"
    r"|ВСИЧКО[^\n]{0,20}|Общо\s+с\s+ДДС|Общо"  # bg
    r"|Gesamtbetrag|Rechnungsbetrag"  # de
    r"|Totale|Importo"  # it
    r"|Montant\s+(?:total|dû)"  # fr
)

# The label, then the figure — same line or the next one. The gap is bounded
# deliberately: a receipt puts them together, while prose that happens to use
# the word "total" is paragraphs away from its next number.
TOTAL_ADJACENT_RE = re.compile(
    rf"(?i)(?:{TOTAL_LABEL})[^\n]{{0,12}}[\s:]*\n?[^\S\n]{{0,8}}{AMOUNT}"
)

# Addresses a billing system sends from. On its own this matched no
# non-invoice in the corpus — receipts@bolt.eu, invoicing@aws.com,
# noreply-payments@booking.com, invoice+statements@mail.anthropic.com.
SENDER_HINT_RE = re.compile(r"(?i)receipt|invoic|billing|payment|no-?reply-?pay")


def looks_like_invoice(sender: str, text: str, *, has_attachment: bool) -> bool:
    """Whether this message is worth teaching an issuer for.

    Any one of three signals is enough, because they fail independently: the
    Bolt receipt has no hint in its sender, Telekom's arrives as an attachment
    the body never describes, and AWS states a total the sender address already
    gave away. Requiring agreement would lose all three.
    """
    return (
        has_attachment
        or bool(TOTAL_ADJACENT_RE.search(text))
        or bool(SENDER_HINT_RE.search(sender))
    )
