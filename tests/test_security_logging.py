"""Verify tokens and codes never appear in logs."""

from __future__ import annotations

import logging
import re

from sqlmodel import Session

from splitmate import services
from splitmate.db import get_engine


def _capture(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records]


def test_invite_token_not_in_logs(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="splitmate.security")
    with Session(get_engine()) as s:
        group, _, token = services.create_group(
            s, name="Trip", currency_symbol="৳", admin_name="Asha"
        )
        services.rotate_invite(s, group=group)
    # Neither the original nor any rotated token must appear in any log
    # message.  Tokens are 32+ url-safe chars; we look for any contiguous
    # url-safe substring that matches the token.
    for line in _capture(caplog):
        assert token not in line
    # Also check that no other log line contains the new (rotated) token.
    # We can't predict the rotated value, so just confirm no line is the
    # full plaintext of an un-hashed token by checking that the only token
    # references are via code_id / group_id.
    for line in _capture(caplog):
        # Token-looking strings: > 30 url-safe chars
        if re.search(r"[A-Za-z0-9_\-]{30,}", line):
            # It must not be a generated token.  We assert no log line
            # contains a url-safe string of the format `token_urlsafe`
            # output (which has _ and - as separators).  We accept lower
            # entropy strings like "ip1".
            assert "ip=" in line or "code_id=" in line, (
                f"Suspicious log line may contain token: {line}"
            )


def test_relink_code_not_in_logs(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="splitmate.security")
    with Session(get_engine()) as s:
        group, admin, _ = services.create_group(
            s, name="Trip", currency_symbol="৳", admin_name="Asha"
        )
        code = services.issue_relink_code(s, group=group, member=admin)
        services.consume_relink_code(s, group=group, code=code, ip="9.9.9.9")
    for line in _capture(caplog):
        assert code not in line
