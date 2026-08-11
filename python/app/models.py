"""Domain types and ORM tables.

Placeholder — the concrete tables depend on whether this shares the Rust
binary's Postgres schema or gets its own database.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for ORM models."""
