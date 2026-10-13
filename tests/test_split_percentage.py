"""Percentage split tests."""

from __future__ import annotations

import pytest

from splitmate.split_engine import SplitError, split_percentage


def test_split_percentage_thirds() -> None:
    # 1000 split as 3334/3333/3333 basis points.
    parts = split_percentage(
        participants=[1, 2, 3],
        basis_points={1: 3334, 2: 3333, 3: 3333},
        total=1000,
        expense_id=0,
    )
    assert sum(parts.values()) == 1000
    # 3334 bp > 3333 bp so participant 1 gets 334, others 333.
    assert parts == {1: 334, 2: 333, 3: 333}


def test_split_percentage_one_hundred_percent_one_participant() -> None:
    parts = split_percentage(
        participants=[7], basis_points={7: 10_000}, total=9999
    )
    assert parts == {7: 9999}


def test_split_percentage_fifty_fifty() -> None:
    parts = split_percentage(
        participants=[1, 2], basis_points={1: 5000, 2: 5000}, total=999
    )
    assert sum(parts.values()) == 999
    # 999 / 2 = 499.5 → floors 499, 499, delta 1, rotation puts it on participant 1.
    assert parts == {1: 500, 2: 499}


def test_split_percentage_rejects_mismatch() -> None:
    with pytest.raises(SplitError):
        split_percentage(
            participants=[1, 2],
            basis_points={1: 5000, 2: 4000},
            total=100,
        )


def test_split_percentage_rejects_out_of_range() -> None:
    with pytest.raises(SplitError):
        split_percentage(
            participants=[1, 2],
            basis_points={1: 12_000, 2: -1},
            total=100,
        )


def test_split_percentage_rejects_empty() -> None:
    with pytest.raises(SplitError):
        split_percentage(participants=[], basis_points={}, total=100)


def test_split_percentage_rejects_negative_total() -> None:
    with pytest.raises(SplitError):
        split_percentage(
            participants=[1, 2], basis_points={1: 5000, 2: 5000}, total=-1
        )
