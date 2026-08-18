"""Domain types and ORM tables.

Everything the parser found lives in `data` as JSONB — exactly the payload
invoicepilot/invoice_store.py writes to disk, so a single serialiser feeds both
sinks and there is no field mapping to keep in step. Columns exist only where
the database needs to sort or join on a value.
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


class MailboxScan(Base):
    """How far one mailbox has been scanned.

    Keyed on the address rather than the Unipile account id: reconnecting a
    mailbox mints a new account, and keying on that would silently reset the
    watermark — the same reasoning that makes invoice_store.mail_token hash the
    sender's Message-ID instead.

    One row per mailbox, so there is no index beyond the primary key.
    """

    __tablename__ = "mailbox_scans"

    mailbox: Mapped[str] = mapped_column(String, primary_key=True)

    # The date of the newest message actually processed — never now(). A clock
    # reading would step over mail the provider had not finished syncing, and
    # nothing would ever come back for it.
    scanned_through: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover — debugging aid
        return f"<MailboxScan {self.mailbox!r} through {self.scanned_through!r}>"


class Share(Base):
    """One share link: a snapshot of invoice ids, and who sent them.

    Written once and never widened. A scan that finds more invoices tomorrow
    must not change what a link already sent covers, and disconnecting the
    mailbox must not change who it says shared them — which is why the ids and
    both owner fields are frozen here rather than resolved at read time.
    """

    __tablename__ = "shares"

    # 22 urlsafe characters, and the whole access-control model: possession of
    # the URL is permission to read.
    token: Mapped[str] = mapped_column(String, primary_key=True)

    # sha256 of the owner key, which is returned once at creation and kept in
    # the creating browser. It gates the rename and the send, so a recipient
    # cannot rewrite the name they were greeted by or mail as the owner. Never
    # part of a lookup: which invoices a link covers is `invoice_ids` alone.
    owner_key_hash: Mapped[str] = mapped_column(String, nullable=False)

    invoice_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    # Resolved from the connected mailbox at creation. The recipient has no
    # account, so everything they are told about who shared with them has to
    # have travelled inside the link. The name is correctable (PATCH), the
    # address is not — it is the mailbox that will actually send.
    owner_name: Mapped[str] = mapped_column(String, nullable=False)
    owner_email: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # created_at + 7 days. There is no revoke and nothing to clean up: the link
    # stops working because the date has passed, not because a row changed.
    # No index — every read is a primary-key lookup, and nothing scans for
    # expired shares.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover — debugging aid
        return f"<Share {self.token!r}>"
