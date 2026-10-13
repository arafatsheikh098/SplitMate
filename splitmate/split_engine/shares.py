"""Shares split: per-participant integer shares, summed proportionally.

``share_total = sum(shares)``.  Each participant's ideal share is
``total * share / share_total``.  The floor and remainder are computed
in *share* units, then re-mapped to minor units via
``distribute_with_remainders``.

Worked example: total = 1000, shares = [1, 1, 1] for 3 participants.
Ideal shares are 333.333… ; floors 333, 333, 333, delta 1.  Shares
[1, 2] give ideal 333.33 and 666.66, floors 333 and 666, sum 999, delta 1.
The participant with share 2 wins the extra unit (larger remainder).
"""

from __future__ import annotations

from .errors import SplitError
from .largest_remainder import distribute_with_remainders


def split_shares(
    *,
    participants: list[int],
    shares: dict[int, int],
    total: int,
    expense_id: int = 0,
) -> dict[int, int]:
    """Split ``total`` proportionally to integer ``shares``.

    Parameters
    ----------
    participants:
        Ordered participant ids.
    shares:
        ``{participant_id: share}``.  Each value must be a positive
        integer; the sum must be positive.
    total:
        Expense total in minor units.
    """
    if not isinstance(total, int):
        raise SplitError("Total must be an integer")
    if total < 0:
        raise SplitError("Total must not be negative")
    if not participants:
        raise SplitError("No participants")
    if len(set(participants)) != len(participants):
        raise SplitError("Duplicate participants")
    share_total = 0
    for pid in participants:
        if pid not in shares:
            raise SplitError(f"Missing share for participant {pid}")
        s = shares[pid]
        if not isinstance(s, int):
            raise SplitError(f"Share for {pid} must be an integer")
        if s <= 0:
            raise SplitError(f"Share for {pid} must be positive")
        share_total += s
    if share_total <= 0:
        raise SplitError("Sum of shares must be positive")
    if total == 0:
        return {pid: 0 for pid in participants}

    # Compute floor and remainder in minor units.  Remainder is the
    # number of share-units * share_total that were lost to floor
    # division, mapped to a comparable scale by multiplying by
    # ``share_total`` (or equivalently, by tracking the share
    # * product mod share_total).
    floors: dict[int, int] = {}
    remainders: dict[int, int] = {}
    floor_total = 0
    for pid in participants:
        s = shares[pid]
        product = s * total
        floor, rem = divmod(product, share_total)
        floors[pid] = floor
        # Re-scale remainder to a comparable integer.  The
        # ``distribute_with_remainders`` helper only cares about
        # ordering, so multiplying by any positive constant preserves
        # the order.  Multiply by 1 to keep it simple — but be aware
        # that two participants with different shares could produce
        # the same remainder (e.g. shares [1, 1, 2] against total 2 →
        # remainders all 0).  In that case the rotation tie-break
        # picks the rotated-first.
        remainders[pid] = rem
        floor_total += floor
    delta = total - floor_total
    return distribute_with_remainders(
        participants=participants,
        floors=floors,
        remainders=remainders,
        delta=delta,
        expense_id=expense_id,
    )


__all__ = ["split_shares"]
