"""Service-level tests for the idempotency-key dedup (G5 / F3.c).

Same key posted twice must result in one expense.  This covers the
service path; the route layer is separately known to be broken
(see BUG_AUDIT.md B1).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from splitmate import services
from splitmate.db import get_engine
from splitmate.models import Expense, IdempotencyKey
from splitmate.services.expenses import create_expense


@pytest.fixture
def session() -> Session:
    with Session(get_engine()) as s:
        yield s


def _make_group(session: Session):
    group, admin, _ = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    bea = services.join_group(session, group=group, display_name="Bea")
    return group, admin, bea


def _draft(amount: str = "10.00", admin=None) -> dict:
    return {
        "title": "Lunch",
        "amount": amount,
        "date": "2025-01-01",
        "category": "Food",
        "note": "",
        "split_method": "equal",
        "participants": [str(admin.id)],
        "payer_id": str(admin.id),
        "payer_amount": amount,
    }


def test_same_key_twice_returns_same_expense(session: Session) -> None:
    group, admin, _ = _make_group(session)
    e1 = create_expense(
        session,
        group_id=group.id,
        creator_id=admin.id,
        data=_draft(admin=admin),
        idempotency_key="abc-123",
    )
    e2 = create_expense(
        session,
        group_id=group.id,
        creator_id=admin.id,
        data=_draft(admin=admin),
        idempotency_key="abc-123",
    )
    assert e1.id == e2.id
    rows = session.exec(
        select(Expense).where(
            Expense.group_id == group.id, Expense.deleted_at.is_(None)
        )
    ).all()
    assert len(rows) == 1
    keys = session.exec(select(IdempotencyKey)).all()
    assert len(keys) == 1


def test_different_keys_create_two_expenses(session: Session) -> None:
    group, admin, _ = _make_group(session)
    e1 = create_expense(
        session,
        group_id=group.id,
        creator_id=admin.id,
        data=_draft(amount="10.00", admin=admin),
        idempotency_key="key-1",
    )
    e2 = create_expense(
        session,
        group_id=group.id,
        creator_id=admin.id,
        data=_draft(amount="20.00", admin=admin),
        idempotency_key="key-2",
    )
    assert e1.id != e2.id
    rows = session.exec(
        select(Expense).where(
            Expense.group_id == group.id, Expense.deleted_at.is_(None)
        )
    ).all()
    assert len(rows) == 2


def test_no_key_allows_duplicates(session: Session) -> None:
    """Without a key, every call creates a new expense (the key is
    what makes the call idempotent)."""
    group, admin, _ = _make_group(session)
    e1 = create_expense(
        session,
        group_id=group.id,
        creator_id=admin.id,
        data=_draft(admin=admin),
    )
    e2 = create_expense(
        session,
        group_id=group.id,
        creator_id=admin.id,
        data=_draft(admin=admin),
    )
    assert e1.id != e2.id
    keys = session.exec(select(IdempotencyKey)).all()
    assert len(keys) == 0
