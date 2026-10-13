"""Security helpers: token hashing, rate limiting, member session.

Tokens and codes are random ``secrets.token_urlsafe(32)`` strings (≥ 256
bits).  We never store the plaintext — only the SHA-256 hash.  Comparing a
submitted token to a stored hash is a constant-time operation.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict
from typing import Any

LOG = logging.getLogger("splitmate.security")


# ---------------------------------------------------------------------------
# Token hashing
# ---------------------------------------------------------------------------


def generate_token() -> str:
    """Return a fresh invite / re-link token (≥ 256 bits of entropy)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex of ``token``.  Used to store invite / rejoin codes."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    """Constant-time equality of two hex digests."""
    return hmac.compare_digest(a, b)


# ---------------------------------------------------------------------------
# In-memory rate limiter (per process; sufficient for the F1 limits)
# ---------------------------------------------------------------------------


class _Bucket:
    __slots__ = ("hits", "reset_at")

    def __init__(self, reset_at: float) -> None:
        self.hits = 0
        self.reset_at = reset_at


class RateLimiter:
    """Fixed-window in-process rate limiter.

    Used for re-link attempts (5 per 15 minutes per IP and group).  The
    scope key is the request path; for our purposes it's a tuple of
    (route, group_id, ip).
    """

    def __init__(self, max_hits: int, window_seconds: int) -> None:
        self.max_hits = max_hits
        self.window_seconds = window_seconds
        self._buckets: dict[tuple[str, int, str], _Bucket] = defaultdict(self._new_bucket)

    def _new_bucket(self) -> _Bucket:
        return _Bucket(reset_at=time.monotonic() + self.window_seconds)

    def hit(self, key: tuple[str, int, str]) -> bool:
        """Register a hit.  Returns ``True`` if it was allowed."""
        bucket = self._buckets[key]
        now = time.monotonic()
        if now >= bucket.reset_at:
            bucket.hits = 0
            bucket.reset_at = now + self.window_seconds
        if bucket.hits >= self.max_hits:
            return False
        bucket.hits += 1
        return True

    def reset(self, key: tuple[str, int, str]) -> None:
        self._buckets.pop(key, None)


# ---------------------------------------------------------------------------
# Member session helpers (thin wrappers around Starlette's session)
# ---------------------------------------------------------------------------


SESSION_GROUP_KEY = "group_id"
SESSION_MEMBER_KEY = "member_id"


def login_member(request: Any, group_id: int, member_id: int) -> None:
    request.session[SESSION_GROUP_KEY] = group_id
    request.session[SESSION_MEMBER_KEY] = member_id


def logout_member(request: Any) -> None:
    request.session.pop(SESSION_GROUP_KEY, None)
    request.session.pop(SESSION_MEMBER_KEY, None)


def current_member_ids(request: Any) -> tuple[int, int] | None:
    gid = request.session.get(SESSION_GROUP_KEY)
    mid = request.session.get(SESSION_MEMBER_KEY)
    if gid is None or mid is None:
        return None
    return int(gid), int(mid)


# ---------------------------------------------------------------------------
# Logging helpers — never log raw tokens / codes.
# ---------------------------------------------------------------------------


def safe_log(msg: str, **kv: object) -> None:
    LOG.info(msg + " ".join(f"{k}={v!r}" for k, v in kv.items()))


__all__ = [
    "RateLimiter",
    "SESSION_GROUP_KEY",
    "SESSION_MEMBER_KEY",
    "current_member_ids",
    "generate_token",
    "hash_token",
    "login_member",
    "logout_member",
    "safe_log",
    "tokens_equal",
]
