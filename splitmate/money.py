"""Integer-only money helpers.

SplitMate never uses ``float`` for money.  Amounts are stored and passed
around as integer minor units (e.g. 1 BDT = 100 paisa).  This module is the
boundary between the user-facing decimal string and the integer world.

Rules
-----

*  ``parse_amount`` accepts strings like ``"0.1"``, ``"1,250.50"``,
   ``"1250"``, ``".5"``.
*  Scientific notation (``"1e3"``) is **rejected** because it is an
   unexpected surface for an expense form.
*  Negative and empty input are **rejected** with explicit error messages.
*  ``format_amount`` turns a minor-unit integer into a localised string
   using the group's currency symbol.

No function in this module uses ``float`` arithmetic.  Conversions go
through :class:`decimal.Decimal` when needed, and we round half-even to
two places (so 1.005 → 1.00, 1.015 → 1.02).
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Final

#: Maximum number of decimal places we accept in user input.
_MAX_DECIMALS: Final = 2
#: Multiplier to turn major units into minor units.
_MINOR_UNIT: Final = 100


class MoneyError(ValueError):
    """Raised for any invalid money input."""


def parse_amount(text: str) -> int:
    """Parse a user-entered decimal amount into integer minor units.

    Accepted inputs:

    * ``"0.1"``     → 10
    * ``"1,250.50"``→ 125050
    * ``"1250"``    → 125000
    * ``".5"``      → 50

    Rejected inputs (with explicit messages):

    * empty / whitespace
    * negative values
    * scientific notation (``"1e3"``)
    * more than two decimals
    * non-numeric characters
    """

    if text is None:
        raise MoneyError("Amount is required")
    raw = str(text).strip()
    if not raw:
        raise MoneyError("Amount is required")
    if raw.startswith("-"):
        raise MoneyError("Amount must not be negative")
    if "e" in raw.lower():
        raise MoneyError("Scientific notation is not allowed")
    # Strip thousands separators (commas) but keep a leading dot.
    cleaned = raw.replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise MoneyError(f"Invalid amount: {text!r}") from exc
    if value < 0:
        raise MoneyError("Amount must not be negative")
    # Reject more than two decimal places (rounding would hide the issue).
    if -value.as_tuple().exponent > _MAX_DECIMALS:
        raise MoneyError("Amount has too many decimal places (max 2)")
    # Reject absurdly large amounts to fit in our int64 storage with room.
    if value > Decimal("100000000000"):
        raise MoneyError("Amount is too large")
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return int(quantized * _MINOR_UNIT)


def format_amount(amount_minor: int, currency_symbol: str = "৳") -> str:
    """Format an integer minor-unit amount as a string with the currency symbol.

    Examples
    --------

    >>> format_amount(10, "৳")
    '৳0.10'
    >>> format_amount(125050, "৳")
    '৳1,250.50'
    >>> format_amount(0, "$")
    '$0.00'
    """
    if amount_minor is None:
        raise MoneyError("Amount is required")
    if not isinstance(amount_minor, int):
        raise MoneyError("Amount must be an integer (minor units)")
    sign = "-" if amount_minor < 0 else ""
    abs_value = -amount_minor if amount_minor < 0 else amount_minor
    major = abs_value // _MINOR_UNIT
    minor = abs_value % _MINOR_UNIT
    major_str = f"{major:,}"
    return f"{currency_symbol}{sign}{major_str}.{minor:02d}"


def format_amount_plain(amount_minor: int) -> str:
    """Format an integer minor-unit amount without the currency symbol.

    Used inside CSV cells where the symbol is in a header.
    """
    if amount_minor is None:
        raise MoneyError("Amount is required")
    if not isinstance(amount_minor, int):
        raise MoneyError("Amount must be an integer (minor units)")
    sign = "-" if amount_minor < 0 else ""
    abs_value = -amount_minor if amount_minor < 0 else amount_minor
    major = abs_value // _MINOR_UNIT
    minor = abs_value % _MINOR_UNIT
    return f"{sign}{major}.{minor:02d}"


__all__ = ["MoneyError", "parse_amount", "format_amount", "format_amount_plain"]
