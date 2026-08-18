"""Domain types and ORM tables.

Everything the parser found lives in `data` as JSONB — exactly the payload
invoicepilot/invoice_store.py writes to disk, so a single serialiser feeds both
sinks and there is no field mapping to keep in step. Columns exist only where
the database needs to sort or join on a value.

Every table below is scoped to a workspace, because the dashboard is served on
a public URL with no login: one browser's invoices and mailboxes must not be
another's. `workspace_id` is part of the primary key wherever the rest of the
key is derived from the mail rather than generated here — see Invoice.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for ORM models."""


class Workspace(Base):
    """One browser's world: its mailboxes, its invoices, its links.

    Deliberately empty of anything but an id. There is no login and no profile
    to hold — the id *is* the credential, held in an httpOnly cookie by the
    browser that minted it (invoicepilot/core/identity.py). Nothing else
    identifies the person, which is why there is also no recovery: clearing the
    cookie strands the row, and no second factor can reunite them.

    Rows are created lazily, on the first request that needs an identity rather
    than on every visit, so a crawler sweeping the public URL does not fill the
    table.
    """

    __tablename__ = "workspaces"

    # 32 urlsafe bytes from secrets.token_urlsafe. Sized to be guessed at never
    # rather than to be read out, the same reasoning as the share token.
    id: Mapped[str] = mapped_column(String, primary_key=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover — debugging aid
        return f"<Workspace {self.id!r}>"


class WorkspaceAccount(Base):
    """Which workspace a connected mailbox belongs to.

    The one place mailboxes touch Postgres, and a deliberate exception to the
    rule that they do not (STRUCTURE.md rule 22). That rule exists because
    Unipile is the source of truth for a mailbox and a copy would only give the
    two a way to disagree — which still holds for status, address and
    credentials, none of which are here.

    Ownership is different in kind: Unipile has one tenant and one API key for
    this whole deployment, so every visitor's mailbox lands on the same tenant
    and Unipile cannot say whose it is. The fact exists nowhere else, so it is
    not a mirror of anything.

    A row is written only when the hosted-auth webhook confirms the account,
    and an account with no row is invisible to everyone — attribution fails
    closed, because the alternative is showing one visitor another's mailbox.
    """

    __tablename__ = "workspace_accounts"

    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    # Unipile's account id. Not unique across the table on purpose: nothing
    # stops two people connecting the same address, and each gets their own
    # account on the tenant.
    account_id: Mapped[str] = mapped_column(String, primary_key=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover — debugging aid
        return f"<WorkspaceAccount {self.workspace_id!r} {self.account_id!r}>"


class PendingConnect(Base):
    """A hosted-auth flow in flight, waiting for Unipile to call back.

    The wizard runs in the user's browser and the account appears on the tenant
    afterwards, so nothing about the finished account says which workspace
    asked for it. This row is that link: the nonce travels out in the
    `notify_url` handed to Unipile and comes back on the webhook, which is what
    lets the account be filed against the right workspace.

    The nonce is the whole check, so it is sized like one. Rows are swept once
    they age past the link's own TTL — an unredeemed nonce is a wizard the user
    abandoned.
    """

    __tablename__ = "pending_connects"

    nonce: Mapped[str] = mapped_column(String, primary_key=True)

    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover — debugging aid
        return f"<PendingConnect {self.workspace_id!r}>"


class Invoice(Base):
    __tablename__ = "invoices"

    # Part of the key, not just a filter. `id` below is derived from the mail,
    # so two workspaces that scan the same mailbox — the same person in two
    # browsers, say — arrive at byte-identical ids for the same invoice. Keyed
    # on `id` alone the second scan would silently overwrite the first
    # workspace's row; keyed on the pair they are two rows that never meet.
    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )

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
        # Led by workspace_id because every read is one workspace's page: the
        # index has to narrow to the workspace before it can help with the sort.
        Index("invoices_issued_idx", workspace_id, issued_on.desc().nullslast()),
    )

    def __repr__(self) -> str:  # pragma: no cover — debugging aid
        return f"<Invoice {self.id!r}>"


class MailboxScan(Base):
    """How far one mailbox has been scanned.

    Keyed on the address rather than the Unipile account id: reconnecting a
    mailbox mints a new account, and keying on that would silently reset the
    watermark — the same reasoning that makes invoice_store.mail_token hash the
    sender's Message-ID instead.

    Keyed on the workspace as well, because the address alone is not unique
    across the deployment. Two workspaces holding the same mailbox have scanned
    it to different depths and each has its own invoices to show for it; one
    shared watermark would let the first scan tell the second there was nothing
    left to fetch.

    One row per mailbox per workspace, so there is no index beyond the key.
    """

    __tablename__ = "mailbox_scans"

    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )

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

    # The workspace whose invoices this link covers, and the one thing that
    # must never be resolved from the caller's cookie. A recipient opening the
    # link is not the owner — they have their own empty workspace, or none at
    # all — so every read behind /s/{token} scopes to this column instead. Read
    # it off the caller and every link ever sent resolves to an empty manifest.
    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )

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
