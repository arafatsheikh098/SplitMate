"""Errors raised by the split engine."""

from __future__ import annotations


class SplitError(ValueError):
    """Raised when a split cannot be computed.

    The message is safe to surface to a human user; the engine never
    embeds secrets or internal state.
    """
