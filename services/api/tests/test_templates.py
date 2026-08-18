"""The local invoice2data templates, and the link-following that feeds them.

Every case runs on a fixture under tests/fixtures/ rather than on live mail, so
the suite needs no Unipile and no vendor server. The fixtures are the layouts
real documents arrive in, with the identifying values replaced — what is being
tested is the shape, and the shape is what a vendor changes under you.

Templates are exercised through `parse_bytes` with a `.txt` suffix, which is
the same matching invoice2data does on a PDF once its text has been read out.
That is why the PDF templates can be covered without a PDF in the repository.
"""

from pathlib import Path

import pytest

from invoicepilot import extract

FIXTURES = Path(__file__).parent / "fixtures"


def parse(name: str) -> dict:
    fields, error = extract.parse_bytes((FIXTURES / name).read_bytes(), ".txt")
    assert error is None, error
    assert fields, f"{name} was not recognised as an invoice"
    return fields


def test_stripe_invoice_pdf_reads_the_invoice_document():
    fields = parse("stripe_invoice_pdf_invoice.txt")

    assert fields["template_name"] == "stripe_invoice_pdf.yml"
    # The Stripe account handle after the name is dropped: the same vendor
    # prints it three ways, and kept it would file one vendor under three.
    assert fields["issuer"] == "Northwind Traders, Inc."
    assert fields["invoice_number"] == "ABCDEFGH-0042"
    assert fields["date"].date().isoformat() == "2026-06-20"
    assert fields["amount"] == 180.0
    assert fields["amount_untaxed"] == 150.0
    assert fields["currency"] == "EUR"


def test_the_receipt_document_extracts_the_same_invoice():
    """Stripe issues an invoice and a receipt per charge, both attached.

    They have to agree field for field, because the invoice's identity is
    derived from the fields — disagree and one charge files as two invoices.
    """
    invoice = parse("stripe_invoice_pdf_invoice.txt")
    receipt = parse("stripe_invoice_pdf_receipt.txt")

    assert receipt["template_name"] == "stripe_invoice_pdf.yml"
    for key in ("issuer", "invoice_number", "date", "amount", "currency"):
        assert receipt[key] == invoice[key], key


def test_stripe_receipt_email_reads_the_invoiced_layout():
    """The receipt mail whose charge came from an invoice, as plain text.

    Everything is on one line here, so the issuer ends where the amount starts
    rather than at a newline.
    """
    fields = parse("stripe_receipt_email_invoiced.txt")

    assert fields["template_name"] == "stripe_receipt_email.yml"
    assert fields["issuer"] == "Northwind Traders, Inc."
    # The invoice number wins over the receipt number: it is the one the
    # vendor's own PDF repeats, which is what makes the two file as one.
    assert fields["invoice_number"] == "ABCDEFGH-0042"
    assert fields["date"].date().isoformat() == "2026-06-20"
    assert fields["amount"] == 180.0
    assert fields["currency"] == "EUR"


def test_stripe_receipt_email_reads_the_bare_charge_layout():
    """A charge with no invoice behind it: no invoice number, and a summary list."""
    fields = parse("stripe_receipt_email_charge.txt")

    assert fields["template_name"] == "stripe_receipt_email.yml"
    assert fields["issuer"] == "Contoso Software"
    assert fields["invoice_number"] == "4444-5555"
    assert fields["date"].date().isoformat() == "2026-07-09"
    assert fields["amount"] == 6.0
    assert fields["amount_untaxed"] == 5.0
    assert fields["amount_tax"] == 1.0
    # Read from the document, not from the template: one template serves every
    # vendor Stripe bills for, and they do not share a currency.
    assert fields["currency"] == "USD"


def test_the_described_issuer_is_the_one_the_document_named():
    """`desc` follows the captured issuer, not the template's declared one.

    invoice2data builds it from the declaration, which is only right for a
    template written per vendor. These are not.
    """
    assert parse("stripe_receipt_email_charge.txt")["desc"] == "Invoice from Contoso Software"


def test_telekom_hotspot_receipt():
    fields = parse("telekom_hotspot.txt")

    assert fields["template_name"] == "telekom_hotspot.yml"
    assert fields["issuer"] == "T-Mobile HotSpot GmbH"
    assert fields["invoice_number"] == "12345678"
    assert fields["date"].date().isoformat() == "2026-07-25"
    assert fields["amount"] == 29.0
    assert fields["vat_number"] == "DE258908556"
    assert fields["currency"] == "EUR"


def test_vp_consulting_invoice():
    """A PDF with no usable reading order: every field is anchored on a neighbour."""
    fields = parse("vp_consulting.txt")

    assert fields["template_name"] == "vp_consulting.yml"
    assert fields["issuer"] == "ВИ ПИ ПАРТНЪРС ООД"
    assert fields["invoice_number"] == "0000099999"
    assert fields["date"].date().isoformat() == "2026-07-05"
    assert fields["amount"] == 76.69
    assert fields["amount_untaxed"] == 63.91
    assert fields["amount_tax"] == 12.78
    # The page carries two ЕИК/ДДС pairs and does not say which is the
    # seller's, so neither is filed. Guessing would be worse than an empty field.
    assert "vat_number" not in fields


def test_a_link_whose_anchor_closes_across_a_newline_is_still_found():
    """The regression: `</a\\n>` used to hide the invoice link entirely.

    A `</a>` pattern misses that close, runs the first anchor on to the second
    anchor's close, and returns the support article it started at — so the
    document was never fetched and every one of these invoices filed without it.
    """
    markup = (FIXTURES / "receipt_with_split_close_tags.html").read_text(encoding="utf-8")

    links = extract.invoice_links(markup)

    assert len(links) == 1
    assert "doclink.example" in links[0]


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        ('<a href="https://example.com/invoice.pdf">Download</a>', "invoice.pdf"),
        ('<a href="https://example.com/doc">Your invoice</a>', "doc"),
        ('<a\n  href="https://example.com/invoice.pdf"\n  >Download</a\n>', "invoice.pdf"),
        ('<a href="https://example.com/invoice.pdf" title="a > b">Get</a>', "invoice.pdf"),
        ('<a href="https://example.com/invoice.pdf">Download', "invoice.pdf"),
        ('<a href="https://example.com/doc">Your <b>invoice</b> is here</a>', "doc"),
        ('<a href="https://example.com/doc?a=1&amp;b=2">Your invoice</a>', "doc?a=1&b=2"),
    ],
    ids=[
        "href",
        "label",
        "split-tags",
        "bracket-in-attribute",
        "unclosed",
        "label-across-tags",
        "escaped-href",
    ],
)
def test_an_invoice_link_survives_the_markup_it_arrives_in(markup, expected):
    assert extract.invoice_links(markup) == [f"https://example.com/{expected}"]


def test_links_that_do_not_advertise_a_document_are_left_alone():
    """Following a link costs a request to the vendor, so most must not qualify."""
    markup = (
        '<a href="https://example.com/support">Contact support</a>'
        '<a href="http://example.com/invoice.pdf">Insecure</a>'
    )

    assert extract.invoice_links(markup) == []
