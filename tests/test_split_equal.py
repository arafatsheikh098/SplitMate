"""Equal split tests."""

from __future__ import annotations

import pytest

from splitmate.split_engine import SplitError, split_equal


def test_split_equal_three_ways_one_paisa_extra() -> None:
    # 1000 minor units = 10.00 in BDT. 3 participants. 333/333/334.
    parts = split_equal(participants=[1, 2, 3], total=1000, expense_id=0)
    assert sorted(parts.values()) == [333, 333, 334]
    assert sum(parts.values()) == 1000


def test_split_equal_extra_unit_rotates_with_expense_id() -> None:
    # With 1000 split among 3, expense_id=0 puts the extra on participant 1
    p0 = split_equal(participants=[1, 2, 3], total=1000, expense_id=0)
    p1 = split_equal(participants=[1, 2, 3], total=1000, expense_id=1)
    p2 = split_equal(participants=[1, 2, 3], total=1000, expense_id=2)
    # The first rotator should be the only one getting 334 in each case.
    for res, expected_top in ((p0, 1), (p1, 2), (p2, 3)):
        assert max(res.values()) == 334
        top = next(pid for pid, v in res.items() if v == 334)
        assert top == expected_top


def test_split_equal_single_participant() -> None:
    parts = split_equal(participants=[42], total=9999, expense_id=7)
    assert parts == {42: 9999}


def test_split_equal_zero_total() -> None:
    parts = split_equal(participants=[1, 2, 3], total=0)
    assert parts == {1: 0, 2: 0, 3: 0}


def test_split_equal_rejects_empty() -> None:
    with pytest.raises(SplitError):
        split_equal(participants=[], total=100)


def test_split_equal_rejects_negative() -> None:
    with pytest.raises(SplitError):
        split_equal(participants=[1, 2], total=-1)


def test_split_equal_rejects_duplicates() -> None:
    with pytest.raises(SplitError):
        split_equal(participants=[1, 1], total=100)


def test_split_equal_many_participants() -> None:
    # 30 participants, total 1000 → floor=33, delta=1000-30*33=10
    parts = split_equal(participants=list(range(1, 31)), total=1000)
    assert sum(parts.values()) == 1000
    assert all(v >= 33 for v in parts.values())
    assert all(v <= 34 for v in parts.values())
    assert sum(1 for v in parts.values() if v == 34) == 10
