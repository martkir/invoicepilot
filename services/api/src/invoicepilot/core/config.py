"""Environment-backed settings, shared by the CLI and the services."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# core/config.py -> core -> invoicepilot -> src -> services/api.
#
# The one place that is allowed to look outside the package. Everything else
# resolves paths downward from its own module or reads them off Settings, so a
# module keeps working whether it is imported from a checkout or a wheel.
SERVICE_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVICE_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str | None = None

    # Where invoice_store writes the extracted documents. A setting rather than
    # a path computed from __file__, because an installed package sits in
    # site-packages and has no repository above it to walk up to. The container
    # sets DATA_DIR outright; a host run gets the checkout's own directory.
    data_dir: Path = SERVICE_ROOT / ".data"

    google_gmail_client_id: str | None = None
    google_gmail_client_secret: str | None = None
    # Must byte-match a redirect URI authorized on the OAuth client. Loopback
    # only — the OAuth callback is served locally.
    google_gmail_redirect_uri: str = "http://localhost:57553"

    aurinko_client_id: str | None = None
    aurinko_client_secret: str | None = None
    # Verifies inbound webhook signatures; not part of the OAuth exchange.
    aurinko_signing_secret: str | None = None
    # Must be registered under the app's authorized return URLs in the Aurinko
    # portal. Loopback only — the callback is served locally.
    aurinko_return_url: str = "http://localhost:57553"

    unipile_api_key: str | None = None
    # Per-tenant host from the Unipile dashboard, e.g. "api8.unipile.com:13845".
    # Doubles as the `api_url` the hosted wizard is told to call back into.
    unipile_dsn: str | None = None
    # Public https URL Unipile POSTs the account_id to once the user finishes.
    # Optional — without it the link still works, the result just isn't reported.
    unipile_notify_url: str | None = None

    # Lets a scan teach itself an issuer nobody has written a template for —
    # see invoicepilot/learn.py. Optional, and only one of the ways in: the SDK
    # also resolves ANTHROPIC_AUTH_TOKEN, an `ant auth login` OAuth profile and
    # workload identity federation on its own, so this stays None on a
    # deployment that uses one of those. None of them is a supported
    # deployment rather than a broken one.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5"
    # Last resort, and a borrowed one: the OAuth token Claude Code keeps for
    # itself. Read-only and never refreshed — see learn.claude_code_token for
    # why that matters. Mount it read-only to use it from a container.
    claude_credentials_file: Path = Path.home() / ".claude" / ".credentials.json"

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Origin a share link is handed out under. It is what the recipient's
    # browser resolves and what the mail's button points at, so it must be the
    # public address of the *frontend* — not api_host/api_port, which is where
    # this process happens to bind. The default is the Vite dev server, so a
    # local run produces a link that opens.
    public_base_url: str = "http://localhost:5173"

    debug_logs_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
