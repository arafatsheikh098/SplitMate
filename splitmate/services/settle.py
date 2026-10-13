"""Settle-up plan: greedy minimum-transfer algorithm.

Given a ``{member_id: net_minor}`` balance mapping, produce a list of
``(from_id, to_id, amount_minor)`` transfers that bring every
balance to zero.  The algorithm matches the largest creditor with the
largest debtor repeatedly, transferring ``min(|debt|, credit)`` each
step.  In the worst case it produces ``n - 1`` transfers; for
realistic friend-group data it usually does far better.

The result is deterministic for a given input: ties are broken by
member id so the same group produces the same plan across runs (M5
A2 / F5 / G3).
"""

from __future__ import annotations

from collections.abc import Mapping


def settle_plan(balances: Mapping[int, int]) -> list[tuple[int, int, int]]:
    """Compute transfers that bring every balance to zero.

    Returns a list of ``(from_id, to_id, amount_minor)`` triples in
    the order they should be executed.  A positive balance means the
    member is owed money; a negative balance means they owe.  The
    list is empty when every balance is already zero.
    """
    # Take a snapshot so we can mutate the local copy.
    pos: dict[int, int] = {pid: bal for pid, bal in balances.items() if bal > 0}
    neg: dict[int, int] = {pid: -bal for pid, bal in balances.items() if bal < 0}
    if not pos and not neg:
        return []

    plan: list[tuple[int, int, int]] = []
    while pos and neg:
        # Largest creditor: the member with the biggest positive
        # balance.  Ties broken by member id.
        cred_id = max(pos.keys(), key=lambda pid: (pos[pid], -pid))
        cred_amt = pos[cred_id]
        # Largest debtor: the member with the biggest debt.
        debt_id = max(neg.keys(), key=lambda pid: (neg[pid], -pid))
        debt_amt = neg[debt_id]
        amount = min(cred_amt, debt_amt)
        plan.append((debt_id, cred_id, amount))
        cred_amt -= amount
        debt_amt -= amount
        if cred_amt == 0:
            pos.pop(cred_id)
        else:
            pos[cred_id] = cred_amt
        if debt_amt == 0:
            neg.pop(debt_id)
        else:
            neg[debt_id] = debt_amt
    return plan


def max_transfers(n: int) -> int:
    """Upper bound on the number of transfers for *n* non-zero members."""
    return max(0, n - 1)


__all__ = ["max_transfers", "settle_plan"]
