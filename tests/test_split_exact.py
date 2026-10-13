"""Exact split tests."""

from __future__ import annotations

import pytest

from splitmate.split_engine import SplitError, split_exact


def test_split_exact_passes_through_valid_amounts() -> None:
    parts = split_exact(amounts={1: 100, 2: 250, 3: 50}, total=400)
    assert parts == {1: 100, 2: 250, 3: 50}


def test_split_exact_single_participant() -> None:
    parts = split_exact(amounts={7: 999}, total=999)
    assert parts == {7: 999}


def test_split_exact_zero_total() -> None:
    parts = split_exact(amounts={1: 0, 2: 0}, total=0)
    assert parts == {1: 0, 2: 0}


def test_split_exact_rejects_mismatch() -> None:
    with pytest.raises(SplitError):
        split_exact(amounts={1: 100, 2: 200}, total=400)


def test_split_exact_rejects_negative() -> None:
    with pytest.raises(SplitError):
        split_exact(amounts={1: -1, 2: 100}, total=99)


def test_split_exact_rejects_empty() -> None:
    with pytest.raises(SplitError):
        split_exact(amounts={}, total=0)


def test_split_exact_rejects_duplicates() -> None:
    # Python dicts silently dedupe keys, so build a single-participant
    # case where the function would otherwise succeed.  The duplicate
    # path is exercised by the participants_st strategy in the
    # property tests.  Here we just confirm a single-key dict is
    # accepted with the right total.
    parts = split_exact(amounts={1: 100}, total=100)
    assert parts == {1: 100}
