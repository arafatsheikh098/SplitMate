"""SQLModel ORM models for SplitMate.

Every entity in SCOPE.md is represented here. Behaviour (F1–F7) lives in
``splitmate.services`` and is wired up in later milestones; this module only
declares schema.
"""

import enum
from datetime import UTC, date, datetime
from typing import Optional

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SplitMethod(str, enum.Enum):
    EQUAL = "equal"
    EXACT = "exact"
    PERCENTAGE = "percentage"
    SHARES = "shares"


class Category(str, enum.Enum):
    FOOD = "Food"
    TRANSPORT = "Transport"
    RENT = "Rent"
    UTILITIES = "Utilities"
    TRIP = "Trip"
    OTHER = "Other"


class SettlementMethod(str, enum.Enum):
    CASH = "cash"
    BKASH = "bKash"
    NAGAD = "Nagad"
    BANK = "bank"
    OTHER = "other"


class ActivityKind(str, enum.Enum):
    EXPENSE_CREATED = "expense_created"
    EXPENSE_EDITED = "expense_edited"
    EXPENSE_DELETED = "expense_deleted"
    EXPENSE_RESTORED = "expense_restored"
    SETTLEMENT_CREATED = "settlement_created"
    SETTLEMENT_EDITED = "settlement_edited"
    SETTLEMENT_DELETED = "settlement_deleted"
    SETTLEMENT_RESTORED = "settlement_restored"
    MEMBER_ADDED = "member_added"
    MEMBER_CLAIMED = "member_claimed"
    MEMBER_ARCHIVED = "member_archived"
    MEMBER_RESTORED = "member_restored"
    INVITE_ROTATED = "invite_rotated"
    INVITE_REVOKED = "invite_revoked"
    RELINK_ISSUED = "relink_issued"
    ADMIN_PROMOTED = "admin_promoted"
    ADMIN_DEMOTED = "admin_demoted"


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------


class Group(SQLModel, table=True):
    __tablename__ = "group"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, index=True)
    currency_symbol: str = Field(max_length=8, default="৳")
    invite_token_hash: str = Field(max_length=128, index=True)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    members: list["Member"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    expenses: list["Expense"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    settlements: list["Settlement"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    activity: list["Activity"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    rejoin_codes: list["RejoinCode"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Member(SQLModel, table=True):
    __tablename__ = "member"
    __table_args__ = (UniqueConstraint("group_id", "name_ci", name="uq_member_group_name"),)

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    display_name: str = Field(max_length=60)
    name_ci: str = Field(max_length=60, index=True)
    is_admin: bool = Field(default=False)
    is_virtual: bool = Field(default=False)
    archived: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    group: Optional["Group"] = Relationship(back_populates="members")


class RejoinCode(SQLModel, table=True):
    """One-time re-link code for a member (F1, F2)."""

    __tablename__ = "rejoin_code"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    member_id: int = Field(foreign_key="member.id", index=True)
    code_hash: str = Field(max_length=128, index=True)
    issued_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    used_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    group: Optional["Group"] = Relationship(back_populates="rejoin_codes")


class Expense(SQLModel, table=True):
    __tablename__ = "expense"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    creator_id: int = Field(foreign_key="member.id")
    title: str = Field(max_length=100)
    amount_minor: int = Field(ge=0)
    occurred_on: date
    category: str = Field(default=Category.OTHER.value)
    note: str | None = Field(default=None, max_length=300)
    split_method: str
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    group: Optional["Group"] = Relationship(back_populates="expenses")
    payers: list["Payer"] = Relationship(
        back_populates="expense",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    parts: list["SplitPart"] = Relationship(
        back_populates="expense",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Payer(SQLModel, table=True):
    __tablename__ = "payer"

    id: int | None = Field(default=None, primary_key=True)
    expense_id: int = Field(foreign_key="expense.id", index=True)
    member_id: int = Field(foreign_key="member.id")
    amount_minor: int = Field(ge=0)

    expense: Optional["Expense"] = Relationship(back_populates="payers")


class SplitPart(SQLModel, table=True):
    """Pre-computed share per participant for an expense.

    The split engine writes these during expense creation / edit.  Balances
    are derived from them on every read.
    """

    __tablename__ = "split_part"

    id: int | None = Field(default=None, primary_key=True)
    expense_id: int = Field(foreign_key="expense.id", index=True)
    member_id: int = Field(foreign_key="member.id")
    amount_minor: int = Field(ge=0)

    expense: Optional["Expense"] = Relationship(back_populates="parts")


class Settlement(SQLModel, table=True):
    __tablename__ = "settlement"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    creator_id: int = Field(foreign_key="member.id")
    from_member_id: int = Field(foreign_key="member.id")
    to_member_id: int = Field(foreign_key="member.id")
    amount_minor: int = Field(ge=0)
    method: str = Field(default=SettlementMethod.OTHER.value)
    paid_on: date
    note: str | None = Field(default=None, max_length=300)
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    group: Optional["Group"] = Relationship(back_populates="settlements")


class Activity(SQLModel, table=True):
    """Append-only history (F7)."""

    __tablename__ = "activity"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    actor_id: int | None = Field(default=None, foreign_key="member.id")
    kind: str
    summary: str = Field(max_length=500)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    group: Optional["Group"] = Relationship(back_populates="activity")


class IdempotencyKey(SQLModel, table=True):
    """Per (group, member, key) deduplication (F3)."""

    __tablename__ = "idempotency_key"
    __table_args__ = (
        UniqueConstraint("group_id", "member_id", "key", name="uq_idem_group_member_key"),
    )

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    member_id: int = Field(foreign_key="member.id")
    key: str = Field(max_length=128, index=True)
    expense_id: int | None = Field(default=None, foreign_key="expense.id")
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


__all__ = [
    "Activity",
    "ActivityKind",
    "Category",
    "Expense",
    "Group",
    "IdempotencyKey",
    "Member",
    "Payer",
    "RejoinCode",
    "Settlement",
    "SettlementMethod",
    "SplitMethod",
    "SplitPart",
]
