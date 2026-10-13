"""Percentage split: per-participant share in basis points (0..10000).

The basis points must sum to exactly 10 000.  The total is split
proportionally; the leftover minor units go to the participants with
the largest fractional remainders, in basis points.

A worked example: total = 1000, basis points = [3334, 3333, 3333].
Ideal shares are 333.4, 333.3, 333.3 — floors 333, 333, 333, delta 1.
The first participant (in rotated order) gets the extra unit.
"""

from __future__ import annotations

from .errors import SplitError
from .largest_remainder import distribute_with_remainders

#: Number of basis points in 100%.
_BASIS: int = 10_000


def split_percentage(
    *,
    participants: list[int],
    basis_points: dict[int, int],
    total: int,
    expense_id: int = 0,
) -> dict[int, int]:
    """Split ``total`` by per-participant basis points.

    Parameters
    ----------
    participants:
        Ordered participant ids.  Order is the tie-break.
    basis_points:
        ``{participant_id: basis_points}``.  Each value 0..10_000 and
        the values must sum to exactly 10_000.
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
    for pid in participants:
        if pid not in basis_points:
            raise SplitError(f"Missing basis points for participant {pid}")
        bp = basis_points[pid]
        if not isinstance(bp, int):
            raise SplitError(f"Basis points for {pid} must be an integer")
        if bp < 0 or bp > _BASIS:
            raise SplitError(f"Basis points for {pid} out of range 0..10000")
    if sum(basis_points[pid] for pid in participants) != _BASIS:
        raise SplitError("Basis points must sum to 10000")
    if total == 0:
        return {pid: 0 for pid in participants}

    # Floor share is ``bp * total // 10000``.  Remainder is the lost
    # fractional minor units, in basis points (0..9999).  This
    # preserves the ordering without any float arithmetic: a higher
    # remainder means a higher priority for the extra unit.
    floors: dict[int, int] = {}
    remainders: dict[int, int] = {}
    bp_total: int = 0
    for pid in participants:
        bp = basis_points[pid]
        product = bp * total
        floor, rem_bp = divmod(product, _BASIS)
        floors[pid] = floor
        remainders[pid] = rem_bp
        bp_total += floor
    delta = total - bp_total
    return distribute_with_remainders(
        participants=participants,
        floors=floors,
        remainders=remainders,
        delta=delta,
        expense_id=expense_id,
    )


__all__ = ["split_percentage"]
