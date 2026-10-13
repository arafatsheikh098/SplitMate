"""Split engine: pure, deterministic expense-splitting logic.

The engine takes integer minor-unit amounts plus participant metadata and
returns a mapping ``{participant: owed_minor}`` whose values sum to the
total.  It is a pure function: no database, no HTTP, no I/O.  This makes
it trivial to property-test and to reuse server- and client-side.

Public API
----------

* :func:`split_equal`
* :func:`split_exact`
* :func:`split_percentage`
* :func:`split_shares`

All four return :class:`SplitResult`, a small dataclass.

The remainder allocation is the *largest-remainder method* with a
deterministic tie-break: ties are broken by participant order, and the
start index is rotated by ``expense_id mod n`` so the extra paisa does
not always land on the same person when many expenses share the same
participants.
"""

from .equal import split_equal
from .errors import SplitError
from .exact import split_exact
from .percentage import split_percentage
from .shares import split_shares

SplitResult = dict[int, int]
"""Per-participant owed amount in minor units: ``{participant_id: minor}``."""

__all__ = [
    "SplitError",
    "SplitResult",
    "split_equal",
    "split_exact",
    "split_percentage",
    "split_shares",
]
