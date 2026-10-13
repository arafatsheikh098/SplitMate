"""Settle-up plan worked example: 4 members, 6 expenses."""

from __future__ import annotations

from sqlmodel import Session

from splitmate import services
from splitmate.db import get_engine
from splitmate.services.balances import group_balances
from splitmate.services.expenses import create_expense
from splitmate.services.settle import settle_plan


def test_four_member_six_expenses() -> None:
    with Session(get_engine()) as s:
        g, ms, _ = services.create_group(s, name="Trip", currency_symbol="৳", admin_name="A")
        b = services.join_group(s, group=g, display_name="B")
        c = services.join_group(s, group=g, display_name="C")
        d = services.join_group(s, group=g, display_name="D")
        members = [ms, b, c, d]

        def exp(title: str, amount: str, payer_idx: int, parts: list[int] | None):
            data = {
                "title": title,
                "amount": amount,
                "date": "2025-01-01",
                "category": "Other",
                "split_method": "equal" if parts is None else "equal",
                "participants": [str(m.id) for m in members],
                "payer_id": str(members[payer_idx].id),
                "payer_amount": amount,
            }
            create_expense(
                s,
                group_id=g.id,
                creator_id=members[0].id,
                data=data,
            )

        exp("Hotel", "120.00", 0, None)
        exp("Lunch", "40.00", 1, None)
        exp("Taxi", "20.00", 2, None)
        exp("Dinner", "60.00", 0, None)
        exp("Snacks", "16.00", 3, None)
        exp("Tickets", "80.00", 1, None)

        bals = group_balances(s, group_id=g.id)
        # Sum must be zero.
        assert sum(bals.values()) == 0
        # The plan must bring every balance to zero.
        sim = dict(bals)
        for f, to, amt in settle_plan(bals):
            sim[f] += amt
            sim[to] -= amt
        for v in sim.values():
            assert v == 0, f"residual {v}"
