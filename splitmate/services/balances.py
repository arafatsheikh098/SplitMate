"""Group-level balance helpers.

Balances are always recomputed from the ledger on every read (F4):
no cached values, no chance of drift.  This module is the canonical
read path; the M5 settle-up plan and the settlement flow both go
through :func:`group_balances`.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlmodel import Session, select

from ..models import Member
from ._core import compute_member_balance


def group_balances(session: Session, *, group_id: int) -> dict[int, int]:
    """Return ``{member_id: net_minor}`` for every (non-archived) member.

    The sum of all values is always exactly zero (F4 / G3).
    """
    members = session.exec(
        select(Member).where(
            Member.group_id == group_id, Member.archived == False  # noqa: E712
        )
    ).all()
    return {m.id: compute_member_balance(session, group_id=group_id, member_id=m.id) for m in members}


def total_balance(balances: dict[int, int]) -> int:
    return sum(balances.values())


def non_zero_members(balances: dict[int, int]) -> Iterable[int]:
    """Members with a non-zero balance (M5 A4)."""
    return [pid for pid, bal in balances.items() if bal != 0]


__all__ = ["group_balances", "non_zero_members", "total_balance"]
