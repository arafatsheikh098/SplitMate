"""Largest-remainder allocation.

Given per-participant *floor* shares and *fractional remainders*, give
one extra unit to each of the ``delta`` participants with the largest
remainders.  Ties are broken by participant order, and the start of
the allocation rotates with ``expense_id mod n`` so the extra paisa
does not always land on the same person across many expenses.
"""

from __future__ import annotations

from .errors import SplitError


def distribute_with_remainders(
    *,
    participants: list[int],
    floors: dict[int, int],
    remainders: dict[int, int],
    delta: int,
    expense_id: int = 0,
) -> dict[int, int]:
    """Allocate ``delta`` extra units to the largest fractional remainders.

    Parameters
    ----------
    participants:
        Ordered list of participant ids.  This order is the canonical
        tie-break: when two participants have the same remainder the
        one earlier in this list (after rotation) wins.
    floors:
        Floor share per participant, must be non-negative.
    remainders:
        Fractional remainder per participant.  The unit is up to the
        caller (basis points for percentage, share-units for shares,
        etc.).  Larger means the participant's ideal share is further
        above the floor.
    delta:
        Number of extra minor units to distribute.  Must be
        non-negative and at most ``len(participants)``.
    expense_id:
        Rotates the start of the allocation so the extra unit does
        not always land on the same participant across many expenses.
        ``start = expense_id mod n``.

    Returns
    -------
    dict
        ``{participant_id: floor + extra}`` summing to ``floor_total + delta``.
    """
    if not participants:
        raise SplitError("No participants")
    for pid in participants:
        if pid not in floors or pid not in remainders:
            raise SplitError(f"Missing data for participant {pid}")
        if floors[pid] < 0 or remainders[pid] < 0:
            raise SplitError("Negative floor or remainder")
    if delta < 0:
        raise SplitError("Negative delta")
    n = len(participants)
    if delta > n:
        raise SplitError("Delta larger than number of participants")

    # Rotation: the first slot of the rotated list is the highest
    # priority among ties.
    start = expense_id % n
    rotated = participants[start:] + participants[:start]
    position = {pid: i for i, pid in enumerate(rotated)}

    # Largest remainder first; tie-break by rotated position
    # (smaller index wins).
    order = sorted(
        participants,
        key=lambda pid: (-remainders[pid], position[pid]),
    )

    result: dict[int, int] = {pid: floors[pid] for pid in participants}
    for pid in order[:delta]:
        result[pid] += 1
    return result


__all__ = ["distribute_with_remainders"]
