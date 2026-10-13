"""Equal split: divide the total evenly among participants.

``total = n * floor + delta`` with ``0 <= delta < n``.  Every
participant gets ``floor``; the ``delta`` largest-priority participants
get one extra unit each.  The priority is rotated by ``expense_id`` so
the extra paisa does not always land on the same person.
"""

from __future__ import annotations

from .errors import SplitError
from .largest_remainder import distribute_with_remainders


def split_equal(
    *,
    participants: list[int],
    total: int,
    expense_id: int = 0,
) -> dict[int, int]:
    """Split ``total`` evenly across ``participants``.

    Raises :class:`SplitError` on empty participants, negative total,
    or non-integer total.
    """
    if not isinstance(total, int):
        raise SplitError("Total must be an integer")
    if total < 0:
        raise SplitError("Total must not be negative")
    if not participants:
        raise SplitError("No participants")
    if len(set(participants)) != len(participants):
        raise SplitError("Duplicate participants")

    n = len(participants)
    floor, delta = divmod(total, n)
    floors = {pid: floor for pid in participants}
    # All remainders are 0 because every share is an integer multiple
    # of 1; the "largest" remainders in ties are the rotated first
    # ones.  We pass a constant 0 remainder — the tie-break is purely
    # by rotation.
    remainders = {pid: 0 for pid in participants}
    return distribute_with_remainders(
        participants=participants,
        floors=floors,
        remainders=remainders,
        delta=delta,
        expense_id=expense_id,
    )


__all__ = ["split_equal"]
