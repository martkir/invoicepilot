"""Extraction, replayed against invoices earlier scans actually filed.

Every case here runs on stored bytes: no Unipile, no vendor servers, no
temporary mailbox. That is deliberate — the extraction rules are the part worth
regression-testing, and they are pure.
"""

from pathlib import Path

from backend import extract
from backend.invoice_store import folder_name, mail_token
from backend.invoices import issued_on, row_id


def read(directory: Path, name: str) -> bytes:
    return (directory / name).read_bytes()


def test_body_markup_still_parses_to_the_filed_fields(corpus):
    """The stored source.html re-parses to the issuer that was recorded from it."""
    checked = 0
    for item in corpus:
        source = item["payload"]["source"]
        if source["file"] != "source.html" or not item["payload"]["source"]["kind"].endswith(
            "body"
        ):
            continue
        markup = read(item["dir"], "source.html")
        text = extract.readable_text(markup, is_html=True)
        fields, error = extract.parse_bytes(text.encode(), ".txt")

        assert error is None, f"{item['id']}: {error}"
        assert fields, f"{item['id']}: body no longer recognised as an invoice"
        assert fields["issuer"] == item["payload"]["invoice"]["issuer"]
        checked += 1
    assert checked, "no body-parsed fixtures to check"


def test_vendor_pdf_still_parses(with_pdf):
    fields, error = extract.parse_bytes(read(with_pdf["dir"], "invoice.pdf"), ".pdf")

    assert error is None
    assert fields
    assert fields["issuer"] == with_pdf["payload"]["invoice"]["issuer"]


def test_amount_and_date_survive_the_round_trip(corpus):
    for item in corpus:
        invoice = item["payload"]["invoice"]
        assert invoice["amount"] is not None
        assert issued_on(invoice) is not None, f"{item['id']}: date no longer parses"


def test_row_id_matches_the_folder_it_was_filed_under(corpus):
    """The database key and the directory name are the same string, by construction."""
    for item in corpus:
        email = item["payload"]["email"]
        token = mail_token(email.get("message_id"), email.get("id") or "")
        assert row_id(item["payload"]["invoice"], token) == item["id"]
        assert folder_name(item["payload"]["invoice"], token) == item["id"]


def test_identity_survives_reconnecting_a_mailbox():
    """The whole point of keying on the Message-ID.

    Disconnecting and reconnecting mints a new Unipile account, and every
    message in it is issued a fresh id. Keying on that filed every invoice a
    second time; keying on the sender's Message-ID does not.
    """
    message_id = "<CALnsD3ZZM6@mail.gmail.com>"
    fields = {"issuer": "Bolt", "amount": 1.2, "currency": "EUR", "date": "2026-08-05"}

    before = row_id(fields, mail_token(message_id, "Xff-jzc8WYaKb5mrxGccyA"))
    after = row_id(fields, mail_token(message_id, "3l1k7f9SWzQqiRv4APqTuw"))

    assert before == after


def test_mail_token_falls_back_when_a_message_has_no_id():
    assert mail_token(None, "Xff-jzc8WYaKb5") == "Xff-jz"
    assert mail_token("", "") == "unknown"


def test_readable_text_drops_style_and_script_bodies():
    markup = b"<style>.a{color:red}</style><p>Total 12.00</p><script>x=1</script>"
    text = extract.readable_text(markup, is_html=True)

    assert "Total 12.00" in text
    assert "color:red" not in text
    assert "x=1" not in text


def test_invoice_links_only_takes_https_that_looks_like_a_document():
    markup = """
      <a href="https://vendor.test/invoice.pdf">Download invoice</a>
      <a href="http://vendor.test/invoice.pdf">insecure</a>
      <a href="https://vendor.test/unsubscribe">Unsubscribe</a>
    """
    assert extract.invoice_links(markup) == ["https://vendor.test/invoice.pdf"]


def test_invoice_links_are_capped():
    markup = "".join(
        f'<a href="https://vendor.test/{n}/invoice.pdf">invoice</a>' for n in range(20)
    )
    assert len(extract.invoice_links(markup)) == extract.MAX_LINKS_PER_INVOICE


def test_merge_fields_lets_the_document_win_but_only_where_it_speaks():
    body = {"issuer": "Bolt", "amount": 1.2, "invoice_number": None}
    document = {"amount": 1.25, "invoice_number": "INV-1", "currency": ""}

    merged = extract.merge_fields(body, document)

    assert merged["amount"] == 1.25  # document overrides
    assert merged["invoice_number"] == "INV-1"  # document fills a gap
    assert merged["issuer"] == "Bolt"  # document silent, body kept
    assert "currency" not in merged  # an empty value is never carried over at all


def test_enrich_rejects_a_document_from_a_different_issuer(with_pdf):
    """Following a link is not proof the PDF belongs to this invoice."""
    from backend.invoice_store import Document

    document = Document("invoice.pdf", read(with_pdf["dir"], "invoice.pdf"), "linked")
    fields = {"issuer": "Some Other Vendor Ltd", "amount": 999.0}

    merged, templates, error = extract.enrich(fields, document)

    assert error is None
    assert merged == fields, "a mismatched document must not overwrite the body's fields"
    assert templates == ()
