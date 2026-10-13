"""Exact split: the user specifies each participant's share directly.

The amounts must already sum to the expense total — the engine does
not rebalance.  This is the only split method that does not need the
largest-remainder helper.
"""

from __future__ import annotations

from .errors import SplitError


def split_exact(
    *,
    amounts: dict[int, int],
    total: int,
) -> dict[int, int]:
    """Return ``amounts`` unchanged after validation.

    Parameters
    ----------
    amounts:
        ``{participant_id: amount_minor}``.  Must be non-empty, every
        amount non-negative, keys unique.
    total:
        Expense total in minor units.  Must equal ``sum(amounts.values())``.
    """
    if not isinstance(total, int):
        raise SplitError("Total must be an integer")
    if total < 0:
        raise SplitError("Total must not be negative")
    if not amounts:
        raise SplitError("No participants")
    for pid, amount in amounts.items():
        if not isinstance(amount, int):
            raise SplitError(f"Amount for participant {pid} must be an integer")
        if amount < 0:
            raise SplitError(f"Amount for participant {pid} must not be negative")
    if len(set(amounts.keys())) != len(amounts):
        raise SplitError("Duplicate participants")
    if sum(amounts.values()) != total:
        raise SplitError(
            f"Exact amounts sum to {sum(amounts.values())}, expected {total}"
        )
    return dict(amounts)


__all__ = ["split_exact"]
