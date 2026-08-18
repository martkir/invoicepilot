"""Drafting, checking and keeping a template for an untaught issuer.

Nothing here reaches the network: `teach` takes the provider it should use, so
a stub stands in for the model and every check that decides whether a draft is
kept runs for real. That is the part worth testing — a template that matches
and reads the wrong figure is worse than no template, so the tests are mostly
about what gets *rejected*.
"""

import json
import os

import pytest

from invoicepilot import extract, learn

# Shaped on a real Uber receipt, discount and all: the figure actually charged
# is NOT the largest one in the document. That is why the amount check asks
# whether the value is stated, not whether it is the maximum.
RECEIPT = """\
Thanks for riding, Martin

Total
$17.46

August 1, 2026

Trip fare  $24.29
Promotion  -$7.49
Reference 4429
"""

# What a well-behaved model returns for RECEIPT: labels anchored, values not.
GOOD_DRAFT = {
    "is_invoice": True,
    "issuer": "Uber",
    "keywords": ["Thanks for riding"],
    "date_format": "%B %d, %Y",
    "currency_code": "USD",
    "decimal_separator": ".",
    "fields": {
        "date": r"(\w+ \d{1,2}, \d{4})",
        "amount": r"Total\s*\$([\d.,]+)",
        "invoice_number": "",
        "amount_untaxed": "",
        "amount_tax": "",
        "currency": "",
        "vat_number": "",
    },
}


class StubModel:
    """A provider that returns a fixed draft, standing in for the API."""

    name = "stub"

    def __init__(self, draft):
        self.draft = draft
        self.calls = 0

    def is_available(self):
        return True

    def extract_structured(self, text, json_schema, *, instructions=None):
        self.calls += 1
        return self.draft


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch):
    """No test picks up a credential this machine happens to have configured."""
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE", "DRAFTER_URL"):
        monkeypatch.delenv(name, raising=False)
    learn.get_settings.cache_clear()
    yield
    learn.get_settings.cache_clear()


@pytest.fixture
def templates_dir(tmp_path, monkeypatch):
    """Point generated templates at a temporary directory, not the data volume."""
    monkeypatch.setattr(extract, "GENERATED_TEMPLATE_DIR", tmp_path)
    extract.forget_templates()
    yield tmp_path
    extract.forget_templates()


def draft_with_amount(pattern):
    fields = dict(GOOD_DRAFT["fields"], amount=pattern)
    return dict(GOOD_DRAFT, fields=fields)


def test_a_good_draft_is_kept_and_reads_the_document(templates_dir):
    model = StubModel(GOOD_DRAFT)

    path = learn.teach(RECEIPT, "noreply@uber.com", using=model)

    assert path is not None and path.is_file()
    assert path.name == "uber-com.yml"
    fields = learn.parse_with(path.read_text(encoding="utf-8"), RECEIPT)
    assert fields["amount"] == 17.46
    assert fields["date"].date().isoformat() == "2026-08-01"


def test_a_kept_template_never_outranks_a_hand_written_one(templates_dir):
    """`priority: 1` is the guarantee, because a first match that fails blocks.

    invoice2data runs only the first template whose keywords match and does not
    try the next when its fields come up empty — so a generated template that
    sorted above a curated one would silently suppress it.
    """
    learn.teach(RECEIPT, "noreply@uber.com", using=StubModel(GOOD_DRAFT))

    assert "priority: 1" in (templates_dir / "uber-com.yml").read_text(encoding="utf-8")


def test_a_draft_that_captures_something_that_is_not_money_is_rejected(templates_dir):
    """The mis-anchoring a template does silently.

    `Reference 4429` parses perfectly and is a reference number. Nothing about
    the template gives that away — only that invoice2data's own detection,
    which shares no code with it, never saw 4429 as a figure of money.
    """
    model = StubModel(draft_with_amount(r"Reference (\d+)"))

    assert learn.teach(RECEIPT, "noreply@uber.com", using=model) is None
    assert not (templates_dir / "uber-com.yml").exists()


def test_a_discounted_total_is_kept_and_flagged_for_review(templates_dir):
    """A total below the largest line is normal, and worth a second look.

    Requiring the amount to equal the largest figure would reject the correct
    template for every issuer that discounts — this receipt included. It is
    kept, with a note naming what a reviewer should confirm.
    """
    path = learn.teach(RECEIPT, "noreply@uber.com", using=StubModel(GOOD_DRAFT))
    body = path.read_text(encoding="utf-8")

    assert "CHECK:" in body
    assert "17.46" in body and "24.29" in body


def test_a_draft_that_does_not_match_its_own_document_is_rejected(templates_dir):
    model = StubModel(draft_with_amount(r"Grand total\s*\$([\d.,]+)"))

    assert learn.teach(RECEIPT, "noreply@uber.com", using=model) is None
    assert not (templates_dir / "uber-com.yml").exists()


def test_a_rejected_issuer_is_not_paid_for_twice(templates_dir):
    """A draft that fails its checks will fail them again — record it and stop."""
    model = StubModel(draft_with_amount(r"Reference (\d+)"))

    learn.teach(RECEIPT, "noreply@uber.com", using=model)
    learn.teach(RECEIPT, "noreply@uber.com", using=model)

    assert model.calls == 1
    assert (templates_dir / "uber-com.failed").is_file()
    assert learn.attempted("uber.com")


def test_a_taught_issuer_is_not_taught_again(templates_dir):
    model = StubModel(GOOD_DRAFT)

    learn.teach(RECEIPT, "noreply@uber.com", using=model)
    learn.teach(RECEIPT, "billing@uber.com", using=model)

    assert model.calls == 1


def test_the_template_is_keyed_on_the_domain_not_the_address():
    """Stripe sends as receipts+acct_<id>@stripe.com — per-address would make
    every vendor it bills for look like a separate issuer."""
    assert learn.domain_of("receipts+acct_1BSk8qF8QbsfidwX@stripe.com") == "stripe.com"
    assert learn.slug("mail.anthropic.com") == "mail-anthropic-com"


def test_no_key_configured_disables_it_rather_than_failing(templates_dir, monkeypatch):
    """An unset key is a supported deployment, not a misconfiguration."""
    monkeypatch.setattr(learn, "provider", lambda: None)

    assert learn.teach(RECEIPT, "noreply@uber.com") is None


def test_a_generated_template_is_loaded_by_the_extractor(templates_dir):
    """The saved file has to be picked up by the running process, not just written."""
    learn.teach(RECEIPT, "noreply@uber.com", using=StubModel(GOOD_DRAFT))

    fields, error = extract.parse_bytes(RECEIPT.encode(), ".txt")

    assert error is None
    assert fields["template_name"] == "uber-com.yml"
    assert fields["amount"] == 17.46
    assert fields["currency"] == "USD"


def test_the_rendered_yaml_carries_its_provenance(templates_dir):
    """A person is meant to review this file, so it says where it came from."""
    learn.teach(RECEIPT, "noreply@uber.com", using=StubModel(GOOD_DRAFT))
    body = (templates_dir / "uber-com.yml").read_text(encoding="utf-8")

    assert "noreply@uber.com" in body
    assert "NOT reviewed by a person" in body


def test_grounding_hands_the_model_values_already_found():
    """The model writes a pattern around a value we located, not one it inferred."""
    grounded = learn.grounded(RECEIPT)

    assert RECEIPT in grounded
    assert "# Values detected" in grounded


def test_an_oauth_profile_counts_as_configured(tmp_path, monkeypatch):
    """`ant auth login` writes a profile the SDK reads on its own.

    Nothing here has to know how to use it — only that something is there, so
    the module does not disable itself in front of working credentials.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", str(tmp_path))
    (tmp_path / "credentials").mkdir()
    learn.get_settings.cache_clear()

    assert learn.credentials_available()
    assert learn.provider() is not None


def test_an_auth_token_counts_as_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "sk-ant-oat01-example")
    learn.get_settings.cache_clear()

    assert learn.credentials_available()


def test_nothing_configured_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_PROFILE", raising=False)
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", str(tmp_path / "absent"))
    learn.get_settings.cache_clear()

    assert not learn.credentials_available()
    assert learn.provider() is None


def test_an_empty_api_key_does_not_shadow_a_token(monkeypatch):
    """compose passes `${ANTHROPIC_API_KEY:-}`, so unset arrives as empty.

    Left in place it wins the SDK's resolution order and authenticates with
    nothing, which is a 401 that names neither the variable nor the token it
    hid. Removing it is what makes the auth-token deployment work at all.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "sk-ant-oat01-example")
    learn.get_settings.cache_clear()

    assert learn.provider() is not None
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_a_configured_key_wins_over_the_drafter(monkeypatch):
    """A direct request beats a spawned process, and is metered separately."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-configured")
    monkeypatch.setenv("DRAFTER_URL", "http://drafter:8100")
    learn.get_settings.cache_clear()

    assert isinstance(learn.provider(), learn.Claude)


def test_the_drafter_is_used_when_there_is_no_key(monkeypatch):
    """The only path that works on a deployment with a borrowed credential."""
    monkeypatch.setenv("DRAFTER_URL", "http://drafter:8100")
    learn.get_settings.cache_clear()

    assert isinstance(learn.provider(), learn.Drafter)
    assert learn.credentials_available()


def test_nothing_configured_is_still_not_an_error():
    assert not learn.credentials_available()
    assert learn.provider() is None


def test_the_drafter_sends_the_schema_and_reads_back_the_draft(monkeypatch):
    """The service knows nothing about invoices, so the schema travels with the
    request and the rules stay in this module."""
    seen = {}

    class Response:
        def read(self):
            return json.dumps({"draft": {"issuer": "Acme"}}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr(learn.urllib.request, "urlopen", fake_urlopen)

    draft = learn.Drafter("http://drafter:8100/").extract_structured(
        "Total 1.00", learn.TEMPLATE_SCHEMA, instructions="be terse"
    )

    assert draft == {"issuer": "Acme"}
    assert seen["url"] == "http://drafter:8100/draft"
    assert seen["body"]["system"] == "be terse"
    assert "Total 1.00" in seen["body"]["prompt"]
    assert "decimal_separator" in seen["body"]["prompt"]


DOCUMENT = """\
Фактура: 1000389093
Дата: 2026-08-08
Общо (EUR): 0.98
ДДС (EUR): 0.20
Общо с ДДС (EUR): 1.17
"""

# What the mail already established, and what a document template must not
# contradict — merge_fields lets the document win every field they share.
FROM_MAIL = {"issuer": "Bolt Operations OU", "amount": 1.17, "date": "2026-08-08"}

DOCUMENT_DRAFT = {
    "is_invoice": True,
    "issuer": "ignored — the mail's issuer wins",
    "keywords": ["Фактура"],
    "date_format": "%Y-%m-%d",
    "currency_code": "EUR",
    "decimal_separator": ".",
    "fields": {
        "date": r"Дата:\s*(\d{4}-\d{2}-\d{2})",
        "amount": r"Общо с ДДС \(EUR\):\s*([\d.,]+)",
        "invoice_number": r"Фактура:\s*(\d+)",
        "amount_untaxed": r"Общо \(EUR\):\s*([\d.,]+)",
        "amount_tax": r"(?<!с )ДДС \(EUR\):\s*([\d.,]+)",
        "currency": "",
        "vat_number": "",
    },
}


def document_draft_with(**fields):
    return dict(DOCUMENT_DRAFT, fields=dict(DOCUMENT_DRAFT["fields"], **fields))


def test_a_document_template_is_a_second_template_for_the_same_issuer(templates_dir):
    """One template reads one layout, and Bolt sends two."""
    learn.teach(RECEIPT, "receipts@bolt.eu", using=StubModel(GOOD_DRAFT))
    path = learn.teach(
        DOCUMENT,
        "receipts@bolt.eu",
        kind=learn.DOCUMENT,
        known=FROM_MAIL,
        using=StubModel(DOCUMENT_DRAFT),
    )

    assert path is not None
    assert {p.name for p in templates_dir.glob("*.yml")} == {"bolt-eu.yml", "bolt-eu-document.yml"}
    fields = learn.parse_with(path.read_text(encoding="utf-8"), DOCUMENT)
    assert fields["invoice_number"] == "1000389093"
    assert fields["amount_untaxed"] == 0.98
    assert fields["amount_tax"] == 0.20


def test_the_document_takes_the_issuer_the_mail_established(templates_dir):
    """enrich() discards the merge when the two disagree, so it is not the
    model's to choose."""
    path = learn.teach(
        DOCUMENT,
        "receipts@bolt.eu",
        kind=learn.DOCUMENT,
        known=FROM_MAIL,
        using=StubModel(DOCUMENT_DRAFT),
    )

    assert "issuer: 'Bolt Operations OU'" in path.read_text(encoding="utf-8")


def test_a_document_template_that_contradicts_the_mail_is_rejected(templates_dir):
    """The strongest check in the module: the mail parsed first, so there is a
    right answer. Reading the net 0.98 as the amount would replace a correct
    1.17, because the document wins every field the two share.
    """
    model = StubModel(document_draft_with(amount=r"Общо \(EUR\):\s*([\d.,]+)"))

    path = learn.teach(
        DOCUMENT, "receipts@bolt.eu", kind=learn.DOCUMENT, known=FROM_MAIL, using=model
    )

    assert path is None
    assert (templates_dir / "bolt-eu-document.failed").is_file()


def test_a_document_template_that_adds_nothing_is_rejected(templates_dir):
    """It costs a request and a merge; it has to be worth one."""
    model = StubModel(document_draft_with(invoice_number="", amount_untaxed="", amount_tax=""))

    assert (
        learn.teach(DOCUMENT, "receipts@bolt.eu", kind=learn.DOCUMENT, known=FROM_MAIL, using=model)
        is None
    )


def test_the_two_kinds_are_tried_independently(templates_dir):
    """A taught mail template must not suppress the document one, or the fix
    would never fire for the issuer that motivated it."""
    learn.teach(RECEIPT, "receipts@bolt.eu", using=StubModel(GOOD_DRAFT))

    assert learn.attempted("bolt.eu", learn.MAIL)
    assert not learn.attempted("bolt.eu", learn.DOCUMENT)


def test_a_document_that_is_not_an_invoice_is_not_templated(templates_dir):
    """The gate cannot tell, and this is what it costs when nothing else asks.

    A Bulgarian social-security declaration reads "Общ доход: 6 200.00 EUR" —
    a date and a total, shaped exactly like a receipt. A template was written
    for one, and it filed the taxpayer's own income as an expense.
    """
    model = StubModel(dict(GOOD_DRAFT, is_invoice=False))

    assert learn.teach(RECEIPT, "info@vp-consulting.org", using=model) is None
    assert (templates_dir / "vp-consulting-org.failed").is_file()
    assert "not an invoice" in (templates_dir / "vp-consulting-org.failed").read_text()
