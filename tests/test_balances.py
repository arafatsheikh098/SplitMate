"""Balance and settle-up tests (M5)."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlmodel import Session

from splitmate import services
from splitmate.db import get_engine
from splitmate.services.balances import group_balances, total_balance
from splitmate.services.expenses import create_expense
from splitmate.services.settle import max_transfers, settle_plan


def _session() -> Session:
    return Session(get_engine())


def _make_group_with_members(s: Session, names: list[str]):
    g, admin, _token = services.create_group(s, name="Trip", currency_symbol="৳", admin_name=names[0])
    members = [admin]
    for n in names[1:]:
        members.append(services.join_group(s, group=g, display_name=n))
    return g, members


def test_balances_sum_to_zero() -> None:
    with _session() as s:
        g, ms = _make_group_with_members(s, ["Asha", "Bea", "Cee"])
        # Asha pays 30.00, splits 3 ways.
        create_expense(
            s,
            group_id=g.id,
            creator_id=ms[0].id,
            data={
                "title": "Lunch",
                "amount": "30.00",
                "date": "2025-01-01",
                "category": "Food",
                "split_method": "equal",
                "participants": [str(m.id) for m in ms],
                "payer_id": str(ms[0].id),
                "payer_amount": "30.00",
            },
        )
        balances = group_balances(s, group_id=g.id)
        assert total_balance(balances) == 0


def test_settle_plan_simple() -> None:
    # 3-way: A is owed 2000, B owes 1000, C owes 1000.
    plan = settle_plan({1: 2000, 2: -1000, 3: -1000})
    assert len(plan) == 2
    # Sum of transfers must equal the total owed.
    assert sum(t[2] for t in plan) == 2000
    # Final balances after applying transfers should all be zero.
    bals = {1: 2000, 2: -1000, 3: -1000}
    for f, to, amt in plan:
        bals[f] += amt
        bals[to] -= amt
    assert all(v == 0 for v in bals.values())


def test_settle_plan_deterministic() -> None:
    a = settle_plan({1: 500, 2: -200, 3: -300})
    b = settle_plan({1: 500, 2: -200, 3: -300})
    assert a == b


def test_settle_plan_handles_zero_balances() -> None:
    # Members with zero balance must never appear in the plan (M5 A4).
    plan = settle_plan({1: 0, 2: 1000, 3: -1000})
    assert plan == [(3, 2, 1000)]


def test_settle_plan_all_zero() -> None:
    plan = settle_plan({1: 0, 2: 0})
    assert plan == []


def test_settle_plan_one_sided() -> None:
    # Single creditor, multiple debtors.
    plan = settle_plan({1: 3000, 2: -1000, 3: -2000})
    assert sum(t[2] for t in plan) == 3000
    bals = {1: 3000, 2: -1000, 3: -2000}
    for f, to, amt in plan:
        bals[f] += amt
        bals[to] -= amt
    assert all(v == 0 for v in bals.values())


def test_max_transfers() -> None:
    assert max_transfers(0) == 0
    assert max_transfers(1) == 0
    assert max_transfers(5) == 4
    assert max_transfers(30) == 29


# Property tests: the plan always brings balances to zero and uses
# at most n-1 transfers (G3 / M5 A1).
@st.composite
def balances_st(draw):
    n = draw(st.integers(min_value=0, max_value=15))
    pids = list(range(1, n + 1))
    # Generate a vector of integers summing to 0.  Use a "random
    # walk" approach: each step adds a signed amount, then normalise.
    raw = [
        draw(st.integers(min_value=-100_000, max_value=100_000)) for _ in pids
    ]
    # Force the last to balance the sum.
    if pids:
        raw[-1] = -sum(raw[:-1])
    return {pid: amt for pid, amt in zip(pids, raw, strict=False)}


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(bals=balances_st())
def test_settle_plan_zeros_balances(bals) -> None:
    plan = settle_plan(bals)
    sim = dict(bals)
    for f, to, amt in plan:
        sim[f] += amt
        sim[to] -= amt
    for v in sim.values():
        assert abs(v) < 1e-9, f"non-zero after plan: {sim}"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(bals=balances_st())
def test_settle_plan_bounded_transfers(bals) -> None:
    n = sum(1 for v in bals.values() if v != 0)
    plan = settle_plan(bals)
    assert len(plan) <= max_transfers(n), (
        f"plan has {len(plan)} transfers for {n} non-zero members"
    )


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(bals=balances_st())
def test_settle_plan_is_deterministic(bals) -> None:
    a = settle_plan(bals)
    b = settle_plan(bals)
    assert a == b
