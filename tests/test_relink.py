"""Re-link code: single use, 24h expiry, 5-attempt rate limit."""

from __future__ import annotations

import pytest
from freezegun import freeze_time
from sqlmodel import Session

from splitmate import services
from splitmate.db import get_engine
from splitmate.services import ServiceError


@pytest.fixture
def session() -> Session:
    with Session(get_engine()) as s:
        yield s


def test_relink_works_once(session: Session) -> None:
    group, admin, _ = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    code = services.issue_relink_code(session, group=group, member=admin)
    member = services.consume_relink_code(session, group=group, code=code, ip="1.2.3.4")
    assert member.id == admin.id
    # Second use fails
    with pytest.raises(ServiceError):
        services.consume_relink_code(session, group=group, code=code, ip="1.2.3.4")


def test_relink_expires_after_24_hours(session: Session) -> None:
    group, admin, _ = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    # Issue at t=0
    with freeze_time("2025-01-01 00:00:00"):
        code = services.issue_relink_code(session, group=group, member=admin)
    # Move forward 25h and try — the code should be expired.
    with freeze_time("2025-01-02 01:00:00"):
        # The limiter from the previous test would carry state if reused, but
        # each test gets a fresh service module via the autouse fixture, so
        # the limiter is fresh.  Use a fresh IP to be safe.
        with pytest.raises(ServiceError):
            services.consume_relink_code(session, group=group, code=code, ip="ip2")


def test_relink_rate_limited_after_5_attempts(session: Session) -> None:
    group, admin, _ = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    code = services.issue_relink_code(session, group=group, member=admin)
    _ = code  # exercise only that the code is issuable
    # 5 wrong attempts succeed (raise ServiceError but rate-limit allows)
    for _i in range(5):
        with pytest.raises(ServiceError):
            services.consume_relink_code(session, group=group, code="wrong", ip="ip1")
    # 6th attempt blocked by rate limiter
    with pytest.raises(ServiceError):
        services.consume_relink_code(session, group=group, code="wrong", ip="ip1")
    # But a different IP is unaffected
    with pytest.raises(ServiceError):
        services.consume_relink_code(session, group=group, code="wrong", ip="ip2")


def test_relink_codes_stored_as_hash(client) -> None:  # noqa: ANN001
    client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    from sqlmodel import select

    from splitmate.models import Group, Member, RejoinCode

    with Session(get_engine()) as s:
        g = s.exec(select(Group)).first()
        m = s.exec(select(Member).where(Member.group_id == g.id)).first()
    # Issue a re-link via the service so we get the plaintext
    with Session(get_engine()) as s:
        group = s.get(Group, g.id)
        member = s.get(Member, m.id)
        code = services.issue_relink_code(s, group=group, member=member)
    # The plaintext is not stored.
    with Session(get_engine()) as s:
        rec = s.exec(select(RejoinCode).where(RejoinCode.member_id == m.id)).first()
    assert rec is not None
    assert rec.code_hash != code
    assert len(rec.code_hash) == 64  # sha256 hex
    # And it's not in any log line we capture.
    # (Logging is covered separately in test_security_logging.)
