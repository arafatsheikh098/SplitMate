"""Property-based tests for the split engine.

Invariants covered:

* parts sum exactly to the total (every method)
* no negative part
* no part is more than one unit above the ideal real share
* the algorithm is deterministic for the same input
* the engine has no DB / web imports (M3 A5)
"""

from __future__ import annotations

import importlib
import pathlib

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from splitmate.split_engine import (
    split_equal,
    split_exact,
    split_percentage,
    split_shares,
)

# Strategy: 1..30 distinct positive participant ids, ordered.
participants_st = st.lists(
    st.integers(min_value=1, max_value=10_000),
    min_size=1,
    max_size=30,
    unique=True,
)
# Total: 0..1_000_000 minor units (0 to 10 000.00 BDT).
total_st = st.integers(min_value=0, max_value=1_000_000)
expense_id_st = st.integers(min_value=0, max_value=10_000)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(participants=participants_st, total=total_st, expense_id=expense_id_st)
def test_split_equal_sums_and_is_bounded(participants, total, expense_id) -> None:
    parts = split_equal(
        participants=participants, total=total, expense_id=expense_id
    )
    assert sum(parts.values()) == total
    assert set(parts.keys()) == set(participants)
    assert all(v >= 0 for v in parts.values())
    n = len(participants)
    if n > 0:
        ideal = total / n
        assert all(v <= ideal + 1 for v in parts.values())
        assert all(v >= ideal - 1 for v in parts.values())


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(participants=participants_st, expense_id=expense_id_st)
def test_split_equal_is_deterministic(participants, expense_id) -> None:
    n = len(participants)
    # Pick a total that produces a non-zero delta to exercise rotation.
    total = n * 17 + (expense_id % n)
    a = split_equal(participants=participants, total=total, expense_id=expense_id)
    b = split_equal(participants=participants, total=total, expense_id=expense_id)
    assert a == b


# Exact: per-participant amounts summing to the total.
@st.composite
def exact_inputs(draw):
    participants = draw(participants_st)
    n = len(participants)
    total = draw(total_st)
    if n == 1 or total == 0:
        amounts = {pid: (total if i == 0 else 0) for i, pid in enumerate(participants)}
        return participants, amounts, total
    # Draw n-1 random integers in [0, total] and let the last one be
    # whatever makes the total exact.
    raw = draw(
        st.lists(
            st.integers(min_value=0, max_value=total),
            min_size=n - 1,
            max_size=n - 1,
        )
    )
    used = sum(raw)
    # If "used" overshoots, fall back to a uniform distribution that
    # always sums to ``total``: scale the draws down.
    if used > total:
        # Distribute proportionally.
        scaled = [r * total // used for r in raw]
        # Ensure non-negative by cap.
        scaled = [min(s, total) for s in scaled]
        # Adjust the last slot to make the sum exact.
        diff = total - sum(scaled)
        scaled[-1] = max(0, scaled[-1] + diff)
        raw = scaled
        used = sum(raw)
    final = total - used
    amounts_list = [*raw, final]
    assert sum(amounts_list) == total
    assert all(a >= 0 for a in amounts_list)
    amounts = {pid: a for pid, a in zip(participants, amounts_list, strict=True)}
    return participants, amounts, total


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(inputs=exact_inputs())
def test_split_exact_sums(inputs) -> None:
    participants, amounts, total = inputs
    parts = split_exact(amounts=amounts, total=total)
    assert sum(parts.values()) == total
    assert parts == amounts


# Percentage: per-participant basis points summing to 10 000.
@st.composite
def percentage_inputs(draw):
    participants = draw(participants_st)
    n = len(participants)
    if n == 1:
        bps = {participants[0]: 10_000}
    else:
        cuts = sorted(draw(st.lists(st.integers(min_value=0, max_value=10_000),
                                    min_size=n - 1, max_size=n - 1)))
        cuts = [0, *cuts, 10_000]
        bps = {participants[i]: cuts[i + 1] - cuts[i] for i in range(n)}
    total = draw(total_st)
    expense_id = draw(expense_id_st)
    return participants, bps, total, expense_id


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(inputs=percentage_inputs())
def test_split_percentage_sums_and_bounded(inputs) -> None:
    participants, bps, total, expense_id = inputs
    parts = split_percentage(
        participants=participants, basis_points=bps, total=total, expense_id=expense_id
    )
    assert sum(parts.values()) == total
    assert set(parts.keys()) == set(participants)
    assert all(v >= 0 for v in parts.values())
    if total > 0:
        # Every part is within 1 minor unit of its ideal share.
        for pid in participants:
            ideal = bps[pid] * total / 10_000
            assert abs(parts[pid] - ideal) < 1.0 + 1e-9


# Shares: positive integer shares.
@st.composite
def shares_inputs(draw):
    participants = draw(participants_st)
    shares = {pid: draw(st.integers(min_value=1, max_value=1_000)) for pid in participants}
    total = draw(total_st)
    expense_id = draw(expense_id_st)
    return participants, shares, total, expense_id


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(inputs=shares_inputs())
def test_split_shares_sums_and_bounded(inputs) -> None:
    participants, shares, total, expense_id = inputs
    parts = split_shares(
        participants=participants, shares=shares, total=total, expense_id=expense_id
    )
    assert sum(parts.values()) == total
    assert set(parts.keys()) == set(participants)
    assert all(v >= 0 for v in parts.values())
    if total > 0:
        share_total = sum(shares.values())
        for pid in participants:
            ideal = shares[pid] * total / share_total
            assert abs(parts[pid] - ideal) < 1.0 + 1e-9


def test_engine_has_no_db_or_web_imports() -> None:
    """The engine must be pure: no DB or web imports. (M3 A5)"""
    package = importlib.import_module("splitmate.split_engine")
    pkg_path = pathlib.Path(package.__file__).parent
    forbidden = ("db", "web", "fastapi", "sqlmodel", "sqlalchemy", "httpx", "jinja")
    for py in pkg_path.glob("*.py"):
        if py.name == "__init__.py":
            continue
        text = py.read_text(encoding="utf-8")
        for needle in forbidden:
            # Allow the docstring / comments to mention them but not
            # actually import them.
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    assert needle not in stripped, (
                        f"{py.name} imports {needle!r} in: {stripped!r}"
                    )
