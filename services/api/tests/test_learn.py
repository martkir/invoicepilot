"""Drafting, checking and keeping a template for an untaught issuer.

Nothing here reaches the network: `teach` takes the provider it should use, so
a stub stands in for the model and every check that decides whether a draft is
kept runs for real. That is the part worth testing — a template that matches
and reads the wrong figure is worse than no template, so the tests are mostly
about what gets *rejected*.
"""

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
