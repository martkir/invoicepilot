"""Logging setup for both the CLI and the services."""

import logging

from backend.core.config import get_settings

_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    logging.basicConfig(
        level=logging.DEBUG if settings.debug_logs_enabled else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    )

    # invoice2data logs "No template for ..." at ERROR for every document that
    # is not an invoice. Scanning a mailbox, that is the common case rather
    # than a fault, and the scan result reports it — so silence it here.
    if not settings.debug_logs_enabled:
        logging.getLogger("invoice2data").setLevel(logging.CRITICAL)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
