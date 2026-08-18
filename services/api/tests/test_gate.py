"""The rule that decides a message is worth teaching an issuer for.

The fixtures are the shapes that actually appear in a mailbox, including the
ones that fooled the obvious rule: an investment newsletter carries more
currency figures than any real receipt, so counting them ranks it top. What
separates the two is a total-shaped label sitting next to a figure.
"""

import pytest

from invoicepilot.gate import looks_like_invoice

RECEIPT = """\
Purchase confirmation
Thanks for riding with us

Total charged

€1.17

Sat, 2026-08-08
"""

NEWSLETTER = """\
Palantir grew revenue to $1.2B this quarter, up from $980.00 a year ago.
Nebius trades at $42.50 against a $61.00 target, and Moody's at $412.30.
My position is up $1,240.00 since June; the portfolio total return figure
sits well above where I expected it in a market this jumpy.
"""

PLAIN_TEXT_RECEIPT = """\
Receipt from Contoso Software Receipt #4444-5555
Amount paid
$6.00
"""

BULGARIAN = """\
Дан.осн.:
ВСИЧКО(ЗА ПЛАЩАНЕ):
 63.91 €
76.69 EUR
"""


@pytest.mark.parametrize(
    ("sender", "text", "attachment"),
    [
        ("receipts@bolt.eu", RECEIPT, False),
        ("noreply@uber.com", RECEIPT, False),
        ("receipts@webshare.io", PLAIN_TEXT_RECEIPT, False),
        ("info@vp-consulting.org", BULGARIAN, False),
        # No usable body at all — Telekom attaches the receipt and the mail
        # around it says nothing a rule could read.
        ("hotspotservice@telekom.de", "Your receipt is attached.", True),
        # Nothing in the body, but the address is a billing system's.
        ("invoicing@aws.com", "Your statement is ready to view online.", False),
    ],
    ids=["bolt", "uber", "webshare", "bulgarian", "attachment-only", "sender-only"],
)
def test_an_invoice_passes(sender, text, attachment):
    assert looks_like_invoice(sender, text, has_attachment=attachment)


def test_a_newsletter_full_of_money_does_not_pass():
    """The case that rules out counting currency amounts.

    This fixture carries five figures — more than any real receipt in the
    corpus — and no label that claims one of them is what was charged.
    """
    assert not looks_like_invoice("typef@substack.com", NEWSLETTER, has_attachment=False)


@pytest.mark.parametrize(
    ("sender", "text"),
    [
        ("uber@uber.com", "Want up to 40% off? Skip the store run."),
        ("no-reply@email.claude.com", "Claude Fable 5 is now available."),
        ("support@unipile.com", "Thank you for subscribing. Explore our unified API."),
        ("mike@marketing.tailride.so", "That retroactive scan button isn't just for show."),
    ],
    ids=["marketing", "product", "onboarding", "cold-outreach"],
)
def test_ordinary_mail_does_not_pass(sender, text):
    assert not looks_like_invoice(sender, text, has_attachment=False)


def test_the_label_has_to_be_near_the_figure():
    """ "Total" three paragraphs from a number is prose, not a receipt."""
    prose = "The total picture is complicated.\n\n" + ("filler\n" * 20) + "It cost $9.99.\n"

    assert not looks_like_invoice("someone@example.com", prose, has_attachment=False)
