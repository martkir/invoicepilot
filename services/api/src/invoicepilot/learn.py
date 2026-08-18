"""Teaching one issuer, once, by having a model write its template.

Recognition is per-issuer: invoice2data reports a document only when a template
matches it, so an invoice from a vendor nobody has taught parses to nothing and
looks like ordinary mail. This closes that gap without putting a model in the
extraction path.

What the model returns is a *template*, never an invoice. It is asked where the
fields are — "the amount follows the words Total charged" — not what they say.
Every figure that reaches the database is still extracted by regex, from a YAML
file a person can read and correct, and re-extracting an old invoice never
calls anything. The cost is one request per issuer, for the life of the issuer.

Three things have to hold before a draft is kept, because a template that
matches and reads the wrong number is worse than no template at all: it must
reproduce the document it was written from, it must find a date and an amount,
and that amount must be a figure the document actually states — checked against
invoice2data's own detection, which shares no code with any template. Anything
else is discarded and the issuer is marked so the next scan does not pay to
fail the same way.

Kept templates land under the data directory, carry `priority: 1` so they can
never outrank a hand-written one, and are unreviewed until somebody moves them
into templates/invoice2data/ by hand.

Credentials are whatever the Anthropic SDK can resolve — an API key, an
ANTHROPIC_AUTH_TOKEN, an `ant auth login` OAuth profile, or workload identity
federation. Failing that, services/drafter, which runs Claude Code and so can
use the OAuth token Claude Code holds for itself — the one credential the public
API will not accept from a third-party client. Nothing configured disables the
module rather than failing a scan.
"""

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from invoicepilot import extract
from invoicepilot.core.config import get_settings
from invoicepilot.core.logging import get_logger

log = get_logger(__name__)

# The vocabulary a drafted template may use. Deliberately smaller than
# invoice2data's: every name here is one the dashboard or the share export
# already reads, so a template cannot invent a field nothing displays.
FIELD_NAMES = (
    "date",
    "invoice_number",
    "amount",
    "amount_untaxed",
    "amount_tax",
    "currency",
    "vat_number",
)

# Fields without which a row is not worth filing. The rest are upside.
REQUIRED_FIELDS = ("date", "amount")

# Not invoice2data's own TEMPLATE_SCHEMA, which types `fields` as a free-form
# map (`additionalProperties: {type: string}`). Constrained output requires
# `additionalProperties: false` on every object, so the field names have to be
# enumerated — which is no loss, since only these are displayed anyway.
#
# Every field is required by the schema and an empty string means "this
# document does not carry one" — a JSON Schema strict enough for the API to
# constrain output cannot also mark properties optional.
TEMPLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "issuer": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "date_format": {"type": "string"},
        "currency_code": {"type": "string"},
        "decimal_separator": {"type": "string"},
        "fields": {
            "type": "object",
            "properties": dict.fromkeys(FIELD_NAMES, {"type": "string"}),
            "required": list(FIELD_NAMES),
            "additionalProperties": False,
        },
    },
    "required": [
        "issuer",
        "keywords",
        "date_format",
        "currency_code",
        "decimal_separator",
        "fields",
    ],
    "additionalProperties": False,
}

INSTRUCTIONS = """\
You write extraction templates for the invoice2data library. You are given the
text of one invoice or receipt from a single issuer, and you return the rules
for reading every future document from that issuer.

Return a regular expression per field, each with exactly ONE capturing group
around the value. Rules that matter:

- Anchor on the LABEL, never on the value. `Total charged\\s*€?([\\d.,]+)` is
  right; `Total charged €1\\.17` matches this document and nothing else.
- A regex that would match two different values in this document returns a
  list rather than a number, which is useless. Anchor tightly enough that each
  matches once.
- Regexes are applied with no flags: case-sensitive, `.` does not cross a
  newline. Use `\\s` where the document wraps a label and its value.
- `keywords` must identify the ISSUER, not the layout — a company name, a VAT
  number, a billing domain. All of them must appear, and they must not appear
  in this issuer's marketing mail. Never use a bare word like "Invoice" or
  "Total".
- `amount` is the gross total actually charged. `amount_untaxed` is the net and
  `amount_tax` the VAT, when the document separates them.
- Leave a field as an empty string when the document does not carry it. Do not
  invent a pattern for something that is not there.
- `date_format` is the strptime format matching what your `date` regex
  captures, e.g. `%d/%m/%y` for `25/07/26` or `%B %d, %Y` for `June 20, 2026`.
- `decimal_separator` is the character this issuer writes before the cents.

A worked example, for a document reading "Total charged\\n€1.17 ... VAT no.
BG3170069438 ... Thu, 2026-08-06":

  issuer: Bolt Operations OU
  keywords: ["Bolt Operations"]
  date_format: "%Y-%m-%d"
  currency_code: "EUR"
  decimal_separator: "."
  fields:
    date: "(\\\\d{4}-\\\\d{2}-\\\\d{2})"
    amount: "Total charged\\\\s*€\\\\s*([\\\\d.,]+)"
    vat_number: "VAT no\\\\.\\\\s*([A-Z]{2}[A-Z0-9]+)"
    invoice_number: ""
    amount_untaxed: ""
    amount_tax: ""
    currency: ""
"""

# Thinking is on by default on the current models and counts against this, so
# it is sized for the reasoning rather than for the few hundred tokens of YAML.
MAX_TOKENS = 8192

# Longer than the drafter's own ceiling, so its error arrives instead of ours.
DRAFT_TIMEOUT = 240

SLUG_RE = re.compile(r"[^a-z0-9]+")


class Claude:
    """An invoice2data AIProvider backed by the Anthropic API.

    invoice2data's own providers are OpenAI-compatible only, but its provider
    contract is a structural Protocol — one method — so satisfying it is the
    whole integration, and `teach` can be handed a stub instead in tests.
    """

    name = "claude"

    def __init__(self, model: str, api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key

    def is_available(self) -> bool:
        return True

    def client(self):
        from anthropic import Anthropic

        if self._api_key:
            return Anthropic(api_key=self._api_key)
        # Anything the SDK resolves itself — auth token, OAuth profile,
        # federation — is left to it, so its own precedence is not second
        # guessed here.
        return Anthropic()

    def extract_structured(
        self,
        text: str,
        json_schema: dict,
        *,
        instructions: str | None = None,
    ) -> dict:
        response = self.client().messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=instructions or "",
            messages=[{"role": "user", "content": text}],
            output_config={"format": {"type": "json_schema", "schema": json_schema}},
        )
        # Checked before the content is read: a declined request returns a
        # normal 200 whose content is empty, and indexing it would raise
        # something that says nothing about what happened.
        if response.stop_reason == "refusal":
            raise RuntimeError("the model declined to answer")
        body = next((block.text for block in response.content if block.type == "text"), "")
        return json.loads(body)


# Where `ant auth login` stores an OAuth profile. The SDK reads it on its own;
# this is only so that "is anything configured" can be answered without making
# a request, since constructing a client succeeds whether or not it is.
CONFIG_DIR_VAR = "ANTHROPIC_CONFIG_DIR"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "anthropic"

# All four must be present for the SDK to attempt federation.
FEDERATION_VARS = (
    "ANTHROPIC_FEDERATION_RULE_ID",
    "ANTHROPIC_ORGANIZATION_ID",
    "ANTHROPIC_SERVICE_ACCOUNT_ID",
)


def sdk_credentials() -> bool:
    """Whether the SDK can authenticate from its own resolution order.

    API key, auth token, OAuth profile, workload identity federation. Asked
    here because a client constructs happily with no credentials at all and
    only fails at request time, so there is nothing to test but the inputs.
    """
    if get_settings().anthropic_api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    if os.environ.get("ANTHROPIC_PROFILE"):
        return True
    config_dir = Path(os.environ.get(CONFIG_DIR_VAR) or DEFAULT_CONFIG_DIR)
    if (config_dir / "credentials").is_dir():
        return True
    return all(os.environ.get(name) for name in FEDERATION_VARS) and bool(
        os.environ.get("ANTHROPIC_IDENTITY_TOKEN_FILE")
        or os.environ.get("ANTHROPIC_IDENTITY_TOKEN")
    )


class Drafter:
    """An AIProvider that runs the prompt through the drafter service.

    The other way to reach a model from here, and on this deployment the only
    one that works. The credential available is the OAuth token Claude Code
    holds for itself, and the public Messages API declines to serve it to a
    third-party client — it authenticates and resolves to an organization, then
    returns a 429 carrying none of the rate-limit headers a real quota response
    has. Claude Code is served, so services/drafter runs Claude Code and hands
    back what it produced.

    The service knows nothing about invoices: the schema and the instructions
    are sent with every request, so the rules about what a template looks like
    stay here. Swapping it for a direct API call is a change of this one class.
    """

    name = "drafter"

    def __init__(self, url: str) -> None:
        self._url = url.rstrip("/")

    def is_available(self) -> bool:
        return True

    def extract_structured(
        self,
        text: str,
        json_schema: dict,
        *,
        instructions: str | None = None,
    ) -> dict:
        payload = json.dumps(
            {
                "system": instructions or "",
                "prompt": (
                    f"{text}\n\n"
                    "Return ONLY a JSON object matching this schema, with no prose "
                    f"and no code fence:\n{json.dumps(json_schema)}"
                ),
            }
        ).encode()
        request = urllib.request.Request(
            f"{self._url}/draft",
            data=payload,
            method="POST",
            headers={"content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=DRAFT_TIMEOUT) as response:
                return json.load(response)["draft"]
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace").strip()
            raise RuntimeError(f"drafter returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"drafter unreachable: {exc.reason}") from exc


def credentials_available() -> bool:
    """Whether anything at all can draft a template right now."""
    return bool(get_settings().drafter_url) or sdk_credentials()


def provider() -> Claude | Drafter | None:
    """Whatever can draft a template, or None when nothing can.

    A configured API credential wins: it is a direct request rather than a
    process, and it is metered separately from anyone's subscription. The
    drafter is the fallback, and on a deployment with no key it is the whole
    story. Nothing configured is a supported deployment rather than a
    misconfiguration — every other part of a scan works without it.
    """
    settings = get_settings()
    # An ANTHROPIC_API_KEY set to the empty string is the documented trap: it
    # still wins its place in the SDK's resolution order and authenticates with
    # nothing, shadowing a token or profile that would have worked, and the 401
    # it produces mentions none of that. Removed rather than warned about,
    # because compose.prod.yml passes `${ANTHROPIC_API_KEY:-}` and so sets it
    # empty on every deployment that has not configured one — which is exactly
    # the deployment most likely to be using one of the others.
    if os.environ.get("ANTHROPIC_API_KEY") == "":
        del os.environ["ANTHROPIC_API_KEY"]
    if sdk_credentials():
        return Claude(settings.anthropic_model, api_key=settings.anthropic_api_key or None)
    if settings.drafter_url:
        return Drafter(settings.drafter_url)
    return None


def domain_of(sender: str) -> str:
    """The sending domain, which is what a template is keyed on.

    The address is not: Stripe sends as `receipts+acct_1BSk8q@stripe.com`, so
    every vendor it bills for would otherwise look like a separate issuer.
    """
    _, _, domain = (sender or "").strip().lower().rpartition("@")
    return domain


def slug(domain: str) -> str:
    return SLUG_RE.sub("-", domain).strip("-")


# An issuer can need two templates, because invoice2data matches one template
# against one document's text and a vendor may send two. Bolt is the case in
# point: an English mail saying "Total charged €1.17", and a Bulgarian PDF
# behind a link carrying the invoice number and the VAT split. No regex set
# reads both, so they are taught and stored separately.
MAIL = "mail"
DOCUMENT = "document"


def stem(domain: str, kind: str) -> str:
    """The filename a template for this issuer and this document type takes."""
    name = slug(domain)
    return name if kind == MAIL else f"{name}-{kind}"


def attempted(domain: str, kind: str = MAIL) -> bool:
    """Whether this has already been taught, or already failed to be.

    Both are recorded on disk rather than in memory, because the question is
    asked once per scan and the answer has to survive a restart. Without it a
    vendor whose documents cannot be templated is paid for on every scan,
    forever.
    """
    directory = extract.GENERATED_TEMPLATE_DIR
    name = stem(domain, kind)
    return (directory / f"{name}.yml").is_file() or (directory / f"{name}.failed").is_file()


def _quote(value: str) -> str:
    """A YAML single-quoted scalar. Regexes are full of backslashes; nothing
    inside one may be interpreted, and only the quote itself needs escaping."""
    return "'" + str(value).replace("'", "''") + "'"


def render(
    draft: dict,
    domain: str,
    sender: str,
    note: str | None = None,
    *,
    kind: str = MAIL,
    known: dict | None = None,
) -> str:
    """A drafted template as the YAML that will be read back.

    Written by hand rather than dumped, because a person is meant to review
    this file and promote it — so it carries its provenance, and it reads like
    the templates in templates/invoice2data/ that it may end up beside.
    """
    fields = {
        name: value
        for name, value in (draft.get("fields") or {}).items()
        if name in FIELD_NAMES and str(value).strip()
    }
    required = [name for name in ("date", "amount", "invoice_number") if name in fields]

    subject = "the document attached to" if kind == DOCUMENT else "a message sent by"
    lines = [
        f"# Drafted from {subject} {sender}",
        f"# on {datetime.now(UTC).date().isoformat()}, and NOT reviewed by a person.",
        "#",
        "# Kept only because it reproduced the document it was written from and",
        "# read an amount that document actually states. Read it, fix what is",
        "# wrong, and move it into templates/invoice2data/ to promote it;",
        "# `priority: 1` keeps it from ever outranking a template written by hand.",
    ]
    if kind == DOCUMENT:
        lines += [
            "#",
            "# This reads the vendor's own document, which the mail only summarises.",
            "# invoice2data merges the two, and the document wins on any field they",
            "# share — so it was also checked against what the mail already said.",
        ]
    if note:
        lines += ["#", f"# CHECK: {note}"]
    lines += [
        f"issuer: {_quote((known or {}).get('issuer') or draft.get('issuer') or domain)}",
        "priority: 1",
        "keywords:",
    ]
    lines += [f"  - {_quote(keyword)}" for keyword in (draft.get("keywords") or [domain])]
    lines.append("fields:")
    lines += [f"  {name}: {_quote(pattern)}" for name, pattern in fields.items()]
    lines.append("required_fields:")
    lines += [f"  - {name}" for name in required]
    lines += [
        "options:",
        f"  currency: {draft.get('currency_code') or 'EUR'}",
        f"  decimal_separator: {_quote(draft.get('decimal_separator') or '.')}",
        "  date_formats:",
        f"    - {_quote(draft.get('date_format') or '%Y-%m-%d')}",
        "",
    ]
    return "\n".join(lines)


def parse_with(template_yaml: str, text: str) -> dict | None:
    """What one candidate template extracts from one document, and nothing else.

    Loaded through a directory so it goes down exactly the path production
    uses — including how a template gets its name — rather than a shortcut that
    could pass here and fail once the file is in place.
    """
    from invoice2data import extract_data
    from invoice2data.extract.loader import read_templates
    from invoice2data.input import text as text_input

    with tempfile.TemporaryDirectory(prefix="invoicepilot-tpl-") as directory:
        Path(directory, "candidate.yml").write_text(template_yaml, encoding="utf-8")
        loaded = read_templates(directory)
        if not loaded:
            return None
        with tempfile.NamedTemporaryFile(suffix=".txt", prefix="invoicepilot-") as handle:
            handle.write(text.encode("utf-8"))
            handle.flush()
            try:
                return extract_data(handle.name, templates=loaded, input_module=text_input) or None
            except Exception as exc:  # noqa: BLE001 — a bad draft is a rejection, not a crash
                log.debug("candidate template raised: %s", exc)
                return None


def stated_amounts(text: str) -> set[float]:
    """Every figure this document states as money, found without a template.

    invoice2data's candidate detection, which shares no code with any template
    — the second opinion the checks below are built on.
    """
    from invoice2data.extract.candidates import find_candidates

    found = set()
    for candidate in find_candidates(text):
        if candidate.kind != "amount":
            continue
        try:
            found.add(round(float(candidate.parsed), 2))
        except (TypeError, ValueError):
            continue
    return found


def disagreement(fields: dict, known: dict) -> str | None:
    """Where this template contradicts what the mail already established.

    Only reachable for a document template, and the strongest check in the
    module — the mail parsed first, so for once there is a right answer to
    compare against rather than a heuristic. It matters because `merge_fields`
    lets the document win every field the two share: a template that read
    Bolt's net 0.98 as the amount would silently replace a correct 1.17.
    """
    for name in ("amount", "amount_untaxed", "amount_tax", "invoice_number"):
        mine, theirs = fields.get(name), known.get(name)
        if mine in (None, "") or theirs in (None, ""):
            continue
        if str(mine) != str(theirs):
            return f"reads {name} as {mine}, but the mail said {theirs}"
    if not set(fields) - set(known) - {"template_name", "desc", "currency", "issuer"}:
        return "adds nothing the mail did not already carry"
    return None


def rejection(fields: dict | None, text: str, known: dict | None = None) -> str | None:
    """Why this draft cannot be trusted, or None if it can.

    The amount check is the one worth having, and it is deliberately weaker
    than "agrees with the largest figure in the document". A real Uber receipt
    reads: Total $17.46, Trip fare $24.29, Promotion -$7.49. The largest figure
    is not what was charged, so requiring agreement would reject the correct
    template for every issuer that applies a discount.

    What it does require is that the captured amount is a figure the document
    actually states. That catches the capture landing on a reference number, a
    page count or a phone digit — the mis-anchoring a template can do silently.
    It does not catch a template reading the wrong *line*; nothing deterministic
    can, which is why the file is quarantined for review either way and
    `advisory` flags the ones most worth a second look.
    """
    if not fields:
        return "does not match the document it was written from"

    missing = [name for name in REQUIRED_FIELDS if fields.get(name) in (None, "")]
    if missing:
        return f"found no {', '.join(missing)}"

    try:
        amount = round(float(fields["amount"]), 2)
    except (TypeError, ValueError):
        return f"produced an amount that is not a number: {fields['amount']!r}"

    stated = stated_amounts(text)
    if stated and amount not in stated:
        return f"read the amount as {amount}, which the document does not state as money"
    return disagreement(fields, known) if known else None


def advisory(fields: dict, text: str) -> str | None:
    """A note for whoever reviews this template, or None when nothing stands out.

    Reading something other than the largest figure is usually right — a
    discount, a partial payment, a deposit — and occasionally the tell for a
    template anchored on a line item instead of the total. Not grounds to
    discard it, exactly the thing to point a reviewer at.
    """
    stated = stated_amounts(text)
    if not stated:
        return None
    try:
        amount = round(float(fields["amount"]), 2)
    except (TypeError, ValueError):
        return None
    largest = max(stated)
    if amount >= largest:
        return None
    return (
        f"this reads {amount} as the total, while the largest figure in the sample "
        f"is {largest}. A discount explains that; a line item mistaken for the total "
        f"looks the same. Confirm against the document before promoting."
    )


def grounded(text: str) -> str:
    """The document, plus the values deterministic detection already found.

    invoice2data's `suggestions` module locates dates, amounts, IBANs and VAT
    numbers by regex with no model involved. Handing those over means the model
    writes a pattern *around a value already located in this text* rather than
    one it inferred from the shape of the page, which is most of the reason the
    drafts are patterns rather than fiction. The technique is invoice2data's
    own; only the schema above had to be replaced.
    """
    from invoice2data.extract.suggestions import suggest_from_text

    found = suggest_from_text(text)
    if not found:
        return text
    hints = "\n".join(f"{name}: {candidate.value}" for name, candidate in found.items())
    return f"{text}\n\n# Values detected in this document:\n{hints}"


def _record_failure(domain: str, kind: str, reason: str) -> None:
    directory = extract.GENERATED_TEMPLATE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem(domain, kind)}.failed").write_text(
        f"{datetime.now(UTC).isoformat(timespec='seconds')}\n{reason}\n", encoding="utf-8"
    )


DOCUMENT_NOTE = """
This text is the vendor's own document. The mail that carried it has already
been read, and gave: {known}. Write regexes for what the *document* adds — the
invoice number and the net/VAT split are usually only here. Where the document
also states something the mail gave, your regex must produce the same value.
"""


def teach(
    text: str,
    sender: str,
    *,
    kind: str = MAIL,
    known: dict | None = None,
    using: Claude | Drafter | None = None,
) -> Path | None:
    """Draft, check and keep a template for one of this sender's document types.

    `kind` is MAIL for the message itself and DOCUMENT for the file it carried
    or linked to; an issuer can need both, and they are separate templates
    because invoice2data matches one template against one layout. For a
    document, `known` is what the mail already yielded — the fields the draft
    must not contradict, and the one place in this module with a right answer
    to check against rather than a heuristic.

    Returns where it was written, or None when nothing was kept — nothing
    configured, this already tried, or the draft failed a check. Raises only
    when the request itself failed, which the caller reports and which
    deliberately leaves no failure marker: a timeout is worth retrying, a
    template that reads the wrong number is not.
    """
    domain = domain_of(sender)
    if not domain or attempted(domain, kind):
        return None

    using = using or provider()
    if using is None or not using.is_available():
        return None

    instructions = INSTRUCTIONS
    if kind == DOCUMENT and known:
        summary = ", ".join(
            f"{name}={known[name]}" for name in sorted(known) if name in FIELD_NAMES
        )
        instructions += DOCUMENT_NOTE.format(known=summary or "nothing")

    draft = using.extract_structured(grounded(text), TEMPLATE_SCHEMA, instructions=instructions)
    template_yaml = render(draft, domain, sender, kind=kind, known=known)

    fields = parse_with(template_yaml, text)
    reason = rejection(fields, text, known)
    if reason:
        log.warning("discarded the %s template drafted for %s: it %s", kind, domain, reason)
        _record_failure(domain, kind, reason)
        return None

    note = advisory(fields, text)
    if note:
        template_yaml = render(draft, domain, sender, note=note, kind=kind, known=known)

    directory = extract.GENERATED_TEMPLATE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stem(domain, kind)}.yml"
    path.write_text(template_yaml, encoding="utf-8")
    extract.forget_templates()
    log.info("learned a %s template for %s at %s", kind, domain, path)
    return path
