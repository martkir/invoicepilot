"""Environment-backed settings, shared by the CLI and the services."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/core/config.py -> backend/core -> backend -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str | None = None

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
