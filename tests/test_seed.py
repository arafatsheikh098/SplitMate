"""Seed module tests (M7 A6)."""

from __future__ import annotations

from splitmate.seed import seed


def test_seed_runs_once_then_idempotent(session) -> None:
    first = seed()
    second = seed()
    assert first == second
    # No new rows: the demo group is the only one in the database.
    from sqlmodel import select

    from splitmate.models import Expense, Group, Settlement

    groups = session.exec(select(Group)).all()
    assert len(groups) == 1
    expenses = session.exec(select(Expense)).all()
    assert len(expenses) == 12
    settlements = session.exec(select(Settlement)).all()
    assert len(settlements) == 2


def test_seed_reset_clears_and_recreates(session) -> None:
    seed()
    gid = seed(reset=True)
    from sqlmodel import select

    from splitmate.models import Expense, Group, Settlement

    groups = session.exec(select(Group)).all()
    assert len(groups) == 1
    assert groups[0].id == gid
    assert len(session.exec(select(Expense)).all()) == 12
    assert len(session.exec(select(Settlement)).all()) == 2


def test_seed_member_balances_balance_to_zero(session) -> None:
    from splitmate.services.balances import group_balances

    g_id = seed()
    bals = group_balances(session, group_id=g_id)
    assert sum(bals.values()) == 0


def test_seed_creates_one_admin_and_three_members(session) -> None:
    from sqlmodel import select

    from splitmate.models import Member

    g_id = seed()
    members = session.exec(
        select(Member).where(Member.group_id == g_id)
    ).all()
    assert len(members) == 4
    admins = [m for m in members if m.is_admin]
    assert len(admins) == 1
