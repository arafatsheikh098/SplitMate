"""Shares split tests."""

from __future__ import annotations

import pytest

from splitmate.split_engine import SplitError, split_shares


def test_split_shares_three_ways() -> None:
    parts = split_shares(
        participants=[1, 2, 3], shares={1: 1, 2: 1, 3: 1}, total=1000, expense_id=0
    )
    assert sum(parts.values()) == 1000
    assert sorted(parts.values()) == [333, 333, 334]
    # First in rotated order gets the extra.
    assert parts[1] == 334


def test_split_shares_one_to_two() -> None:
    # 1:2 → 333/666 with no remainder (999 = 3 * 333).
    parts = split_shares(
        participants=[1, 2], shares={1: 1, 2: 2}, total=999, expense_id=0
    )
    assert sum(parts.values()) == 999
    assert parts == {1: 333, 2: 666}


def test_split_shares_one_to_two_with_extra() -> None:
    # 1:2 → ideal 333.66/667.33. With total 1000 (not evenly
    # divisible by 3) the larger share wins the extra unit.
    parts = split_shares(
        participants=[1, 2], shares={1: 1, 2: 2}, total=1000, expense_id=0
    )
    assert sum(parts.values()) == 1000
    assert parts == {1: 333, 2: 667}


def test_split_shares_single_participant() -> None:
    parts = split_shares(participants=[7], shares={7: 5}, total=999)
    assert parts == {7: 999}


def test_split_shares_zero_total() -> None:
    parts = split_shares(participants=[1, 2], shares={1: 1, 2: 2}, total=0)
    assert parts == {1: 0, 2: 0}


def test_split_shares_rejects_zero_share() -> None:
    with pytest.raises(SplitError):
        split_shares(participants=[1, 2], shares={1: 0, 2: 1}, total=100)


def test_split_shares_rejects_negative_share() -> None:
    with pytest.raises(SplitError):
        split_shares(participants=[1, 2], shares={1: -1, 2: 1}, total=100)


def test_split_shares_rejects_empty() -> None:
    with pytest.raises(SplitError):
        split_shares(participants=[], shares={}, total=100)


def test_split_shares_rejects_negative_total() -> None:
    with pytest.raises(SplitError):
        split_shares(participants=[1], shares={1: 1}, total=-1)
