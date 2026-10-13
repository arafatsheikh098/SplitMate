"""Idempotency keys (F3).

A client may include a key in the form / JSON of an expense create.
The same key posted twice (even concurrently) must result in **one**
expense, with the second call returning the original expense id.

The dedup is enforced by the ``idempotency_key`` table's unique
constraint on ``(group_id, member_id, key)``.  On Postgres the second
``INSERT`` raises ``IntegrityError`` and we re-read the row.  On
SQLite, the same logic works (the unique constraint is enforced too).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..models import Expense, IdempotencyKey


def reserve_key(
    session: Session,
    *,
    group_id: int,
    member_id: int,
    key: str,
    expense_id: int | None = None,
) -> IdempotencyKey | None:
    """Try to insert ``(group_id, member_id, key)``.

    Returns the freshly created row, or ``None`` if a row already
    exists (the caller should then look up the existing expense id
    via :func:`lookup_expense`).
    """
    if not key:
        return None
    row = IdempotencyKey(
        group_id=group_id,
        member_id=member_id,
        key=key,
        expense_id=expense_id,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return None
    return row


def lookup_expense(
    session: Session,
    *,
    group_id: int,
    member_id: int,
    key: str,
) -> Expense | None:
    """Return the expense associated with this idempotency key, if any."""
    if not key:
        return None
    row = session.exec(
        select(IdempotencyKey).where(
            IdempotencyKey.group_id == group_id,
            IdempotencyKey.member_id == member_id,
            IdempotencyKey.key == key,
        )
    ).first()
    if row is None or row.expense_id is None:
        return None
    return session.get(Expense, row.expense_id)


def attach_expense(
    session: Session,
    *,
    key: str,
    group_id: int,
    member_id: int,
    expense_id: int,
) -> None:
    """Backfill ``expense_id`` on an existing idempotency row (used after
    we discover a key on a *second* attempt and have just created the
    expense for it).
    """
    if not key:
        return
    row = session.exec(
        select(IdempotencyKey).where(
            IdempotencyKey.group_id == group_id,
            IdempotencyKey.member_id == member_id,
            IdempotencyKey.key == key,
        )
    ).first()
    if row is None:
        return
    row.expense_id = expense_id
    session.add(row)
    session.flush()


__all__ = ["attach_expense", "lookup_expense", "reserve_key"]
