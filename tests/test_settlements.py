"""Settlement service tests."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from splitmate import services
from splitmate.db import get_engine
from splitmate.services.balances import group_balances
from splitmate.services.expenses import create_expense
from splitmate.services.settle import settle_plan
from splitmate.services.settlements import (
    ServiceError,
    create_settlement,
    list_settlements,
    soft_delete_settlement,
)


def _session() -> Session:
    return Session(get_engine())


def _two_member_group(s: Session):
    g, admin, _ = services.create_group(s, name="Trip", currency_symbol="৳", admin_name="Asha")
    bea = services.join_group(s, group=g, display_name="Bea")
    return g, admin, bea


def test_settlement_changes_balance() -> None:
    with _session() as s:
        g, admin, bea = _two_member_group(s)
        # Asha pays 20.00 split between Asha and Bea.
        create_expense(
            s,
            group_id=g.id,
            creator_id=admin.id,
            data={
                "title": "Lunch",
                "amount": "20.00",
                "date": "2025-01-01",
                "category": "Food",
                "split_method": "equal",
                "participants": [str(admin.id), str(bea.id)],
                "payer_id": str(admin.id),
                "payer_amount": "20.00",
            },
        )
        # Bea owes 10.00, Asha is owed 10.00.
        bals_before = group_balances(s, group_id=g.id)
        assert bals_before[admin.id] == 1000
        assert bals_before[bea.id] == -1000
        # Bea pays Asha 10.00.
        create_settlement(
            s,
            group_id=g.id,
            creator_id=bea.id,
            data={
                "from_id": str(bea.id),
                "to_id": str(admin.id),
                "amount": "10.00",
                "method": "cash",
                "date": "2025-01-02",
                "note": "",
            },
        )
        bals_after = group_balances(s, group_id=g.id)
        assert bals_after[admin.id] == 0
        assert bals_after[bea.id] == 0


def test_settlement_rejects_self_payment() -> None:
    with _session() as s:
        g, admin, bea = _two_member_group(s)
        with pytest.raises(ServiceError):
            create_settlement(
                s,
                group_id=g.id,
                creator_id=admin.id,
                data={
                    "from_id": str(admin.id),
                    "to_id": str(admin.id),
                    "amount": "10.00",
                    "method": "cash",
                    "date": "2025-01-02",
                    "note": "",
                },
            )


def test_settlement_rejects_zero_amount() -> None:
    with _session() as s:
        g, admin, bea = _two_member_group(s)
        with pytest.raises(ServiceError):
            create_settlement(
                s,
                group_id=g.id,
                creator_id=admin.id,
                data={
                    "from_id": str(admin.id),
                    "to_id": str(bea.id),
                    "amount": "0",
                    "method": "cash",
                    "date": "2025-01-02",
                    "note": "",
                },
            )


def test_settlement_rejects_negative_amount() -> None:
    with _session() as s:
        g, admin, bea = _two_member_group(s)
        with pytest.raises(ServiceError):
            create_settlement(
                s,
                group_id=g.id,
                creator_id=admin.id,
                data={
                    "from_id": str(admin.id),
                    "to_id": str(bea.id),
                    "amount": "-1",
                    "method": "cash",
                    "date": "2025-01-02",
                    "note": "",
                },
            )


def test_settlement_rejects_unknown_member() -> None:
    with _session() as s:
        g, admin, bea = _two_member_group(s)
        with pytest.raises(ServiceError):
            create_settlement(
                s,
                group_id=g.id,
                creator_id=admin.id,
                data={
                    "from_id": "99999",
                    "to_id": str(bea.id),
                    "amount": "10.00",
                    "method": "cash",
                    "date": "2025-01-02",
                    "note": "",
                },
            )


def test_settlement_soft_delete_excludes_from_balance() -> None:
    with _session() as s:
        g, admin, bea = _two_member_group(s)
        create_expense(
            s,
            group_id=g.id,
            creator_id=admin.id,
            data={
                "title": "Lunch",
                "amount": "20.00",
                "date": "2025-01-01",
                "category": "Food",
                "split_method": "equal",
                "participants": [str(admin.id), str(bea.id)],
                "payer_id": str(admin.id),
                "payer_amount": "20.00",
            },
        )
        settlement = create_settlement(
            s,
            group_id=g.id,
            creator_id=bea.id,
            data={
                "from_id": str(bea.id),
                "to_id": str(admin.id),
                "amount": "10.00",
                "method": "cash",
                "date": "2025-01-02",
                "note": "",
            },
        )
        soft_delete_settlement(
            s,
            group_id=g.id,
            settlement_id=settlement.id,
            actor_id=admin.id,
        )
        # The settlement is excluded; the original imbalance returns.
        bals = group_balances(s, group_id=g.id)
        assert bals[admin.id] == 1000
        assert bals[bea.id] == -1000
        # list_settlements by default excludes soft-deleted.
        assert list_settlements(s, group_id=g.id) == []
        # Including them shows the soft-deleted row.
        assert len(list_settlements(s, group_id=g.id, include_deleted=True)) == 1


def test_plan_zeroes_after_applying() -> None:
    """Applying the plan to the ledger (via settlements) should zero
    every balance (M5 A3)."""
    with _session() as s:
        g, ms, _ = services.create_group(
            s, name="Trip", currency_symbol="৳", admin_name="A"
        )
        b = services.join_group(s, group=g, display_name="B")
        c = services.join_group(s, group=g, display_name="C")
        members = [ms, b, c]
        for i, payer in enumerate(members):
            create_expense(
                s,
                group_id=g.id,
                creator_id=payer.id,
                data={
                    "title": f"E{i}",
                    "amount": "30.00",
                    "date": "2025-01-01",
                    "category": "Other",
                    "split_method": "equal",
                    "participants": [str(m.id) for m in members],
                    "payer_id": str(payer.id),
                    "payer_amount": "30.00",
                },
            )
        bals = group_balances(s, group_id=g.id)
        plan = settle_plan(bals)
        for f, to, amt in plan:
            amount_str = f"{amt // 100}.{amt % 100:02d}"
            create_settlement(
                s,
                group_id=g.id,
                creator_id=f,
                data={
                    "from_id": str(f),
                    "to_id": str(to),
                    "amount": amount_str,
                    "method": "cash",
                    "date": "2025-01-02",
                    "note": "",
                },
            )
        # After all settlements, every balance must be zero.
        for v in group_balances(s, group_id=g.id).values():
            assert v == 0
