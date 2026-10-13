"""initial schema

Revision ID: 0001_init
Revises:
Create Date: 2025-01-01 00:00:00.000000

Creates every table declared in ``splitmate.models``.  The migration is
hand-written so it produces the same schema on SQLite (used for tests and
local dev) and PostgreSQL (used in production).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "group",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("currency_symbol", sa.String(length=8), nullable=False, server_default="৳"),
        sa.Column("invite_token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_group_name", "group", ["name"])
    op.create_index("ix_group_invite_token_hash", "group", ["invite_token_hash"])

    op.create_table(
        "member",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("group.id"), nullable=False),
        sa.Column("display_name", sa.String(length=60), nullable=False),
        sa.Column("name_ci", sa.String(length=60), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("group_id", "name_ci", name="uq_member_group_name"),
    )
    op.create_index("ix_member_group_id", "member", ["group_id"])
    op.create_index("ix_member_name_ci", "member", ["name_ci"])

    op.create_table(
        "rejoin_code",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("group.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("member.id"), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_rejoin_code_group_id", "rejoin_code", ["group_id"])
    op.create_index("ix_rejoin_code_member_id", "rejoin_code", ["member_id"])
    op.create_index("ix_rejoin_code_code_hash", "rejoin_code", ["code_hash"])

    op.create_table(
        "expense",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("group.id"), nullable=False),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("member.id"), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("split_method", sa.String(length=20), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_expense_group_id", "expense", ["group_id"])

    op.create_table(
        "payer",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expense_id", sa.Integer(), sa.ForeignKey("expense.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("member.id"), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
    )
    op.create_index("ix_payer_expense_id", "payer", ["expense_id"])

    op.create_table(
        "split_part",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expense_id", sa.Integer(), sa.ForeignKey("expense.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("member.id"), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
    )
    op.create_index("ix_split_part_expense_id", "split_part", ["expense_id"])

    op.create_table(
        "settlement",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("group.id"), nullable=False),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("member.id"), nullable=False),
        sa.Column("from_member_id", sa.Integer(), sa.ForeignKey("member.id"), nullable=False),
        sa.Column("to_member_id", sa.Integer(), sa.ForeignKey("member.id"), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_settlement_group_id", "settlement", ["group_id"])

    op.create_table(
        "activity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("group.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("member.id"), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_activity_group_id", "activity", ["group_id"])

    op.create_table(
        "idempotency_key",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("group.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("member.id"), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("expense_id", sa.Integer(), sa.ForeignKey("expense.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("group_id", "member_id", "key", name="uq_idem_group_member_key"),
    )
    op.create_index("ix_idempotency_key_group_id", "idempotency_key", ["group_id"])
    op.create_index("ix_idempotency_key_key", "idempotency_key", ["key"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_key_key", table_name="idempotency_key")
    op.drop_index("ix_idempotency_key_group_id", table_name="idempotency_key")
    op.drop_table("idempotency_key")

    op.drop_index("ix_activity_group_id", table_name="activity")
    op.drop_table("activity")

    op.drop_index("ix_settlement_group_id", table_name="settlement")
    op.drop_table("settlement")

    op.drop_index("ix_split_part_expense_id", table_name="split_part")
    op.drop_table("split_part")

    op.drop_index("ix_payer_expense_id", table_name="payer")
    op.drop_table("payer")

    op.drop_index("ix_expense_group_id", table_name="expense")
    op.drop_table("expense")

    op.drop_index("ix_rejoin_code_code_hash", table_name="rejoin_code")
    op.drop_index("ix_rejoin_code_member_id", table_name="rejoin_code")
    op.drop_index("ix_rejoin_code_group_id", table_name="rejoin_code")
    op.drop_table("rejoin_code")

    op.drop_index("ix_member_name_ci", table_name="member")
    op.drop_index("ix_member_group_id", table_name="member")
    op.drop_table("member")

    op.drop_index("ix_group_invite_token_hash", table_name="group")
    op.drop_index("ix_group_name", table_name="group")
    op.drop_table("group")
