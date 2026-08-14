"""Domain types and ORM tables.

One table. Everything the parser found lives in `data` as JSONB — exactly the
payload backend/invoice_store.py writes to disk, so a single serialiser feeds
both sinks and there is no field mapping to keep in step. Columns exist only
where the database needs to sort or join on a value.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for ORM models."""


class Invoice(Base):
    __tablename__ = "invoices"

    # invoice_store.folder_name(): "<date>__<issuer>__<amount><currency>__<id>".
    # Deterministic, so re-scanning the same mail updates a row rather than
    # adding one — the same guarantee the on-disk folder naming gives.
    id: Mapped[str] = mapped_column(String, primary_key=True)

    # The invoice's own date, promoted out of `data` because it is the
    # dashboard's default sort. Nullable: invoice2data does not always find a
    # date, which is why the store has an "undated" case.
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # When the row was filed, as distinct from when the invoice was issued.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # NULLS LAST keeps undated invoices off the top of the dashboard.
        Index("invoices_issued_idx", issued_on.desc().nullslast()),
    )

    def __repr__(self) -> str:  # pragma: no cover — debugging aid
        return f"<Invoice {self.id!r}>"
