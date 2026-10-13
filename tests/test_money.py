"""Money helper contract: never float, strict about weird inputs."""

from __future__ import annotations

import pytest

from splitmate.money import MoneyError, format_amount, format_amount_plain, parse_amount


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0", 0),
        ("0.0", 0),
        ("0.1", 10),
        ("1", 100),
        ("1.5", 150),
        (".5", 50),
        ("1250", 125000),
        ("1,250", 125000),
        ("1,250.50", 125050),
        (" 12.34 ", 1234),
    ],
)
def test_parse_amount_accepts(text: str, expected: int) -> None:
    assert parse_amount(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "1e3",
        "1E3",
        "-1",
        "-0.5",
        "",
        "   ",
        "abc",
        "1.234",
        "1.2.3",
        None,  # type: ignore[arg-type]
    ],
)
def test_parse_amount_rejects(text: object) -> None:
    with pytest.raises(MoneyError):
        parse_amount(text)  # type: ignore[arg-type]


def test_parse_amount_no_float_internals() -> None:
    # Sanity check: the parser should never need to deal with floats.
    import inspect

    from splitmate import money as money_mod

    src_text = inspect.getsource(money_mod)
    assert "float(" not in src_text, "money module must not use float"


def test_format_amount() -> None:
    assert format_amount(0, "৳") == "৳0.00"
    assert format_amount(10, "৳") == "৳0.10"
    assert format_amount(125050, "৳") == "৳1,250.50"
    assert format_amount(-125050, "৳") == "৳-1,250.50"
    assert format_amount(123456789, "$") == "$1,234,567.89"


def test_format_amount_rejects_non_int() -> None:
    with pytest.raises(MoneyError):
        format_amount(10.5)  # type: ignore[arg-type]


def test_format_amount_plain() -> None:
    assert format_amount_plain(0) == "0.00"
    assert format_amount_plain(125050) == "1250.50"
