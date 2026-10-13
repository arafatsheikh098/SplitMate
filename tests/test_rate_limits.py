"""Rate-limit behaviour (M7 A7).

The re-link code is the only endpoint with a per-IP+group rate
limit (5 attempts per 15 minutes, F1).  This module exercises both
the *pass* path and the *block* path end-to-end via the service
layer, which is the unit-of-behaviour the HTTP layer delegates to.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from splitmate import services
from splitmate.db import get_engine
from splitmate.models import Group, Member
from splitmate.services import ServiceError


def _create_group_and_member(client: TestClient) -> tuple[int, int]:
    r = client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    g_id = int(re.search(r"/groups/(\d+)", r.text).group(1))
    invite = re.search(r"/join/([A-Za-z0-9_\-]+)", r.text).group(1)
    client.post(f"/join/{invite}", data={"display_name": "Bea"})
    with Session(get_engine()) as s:
        bea = s.exec(
            select(Member).where(
                Member.group_id == g_id, Member.display_name == "Bea"
            )
        ).first()
    assert bea is not None
    return g_id, bea.id


def test_relink_rate_limit_blocks_sixth_attempt_on_same_ip() -> None:
    g_id, member_id = None, None
    # Use a fresh client so we have a clean rate-limit bucket for one group.
    with TestClient(__import__("splitmate.main", fromlist=["create_app"]).create_app()) as client:
        g_id, member_id = _create_group_and_member(client)
    with Session(get_engine()) as s:
        group = s.get(Group, g_id)
        # 5 wrong attempts are allowed.
        for _i in range(5):
            with pytest.raises(ServiceError):
                services.consume_relink_code(
                    s, group=group, code="nope", ip="10.0.0.1"
                )
        # 6th attempt is rate-limited.
        with pytest.raises(ServiceError) as exc:
            services.consume_relink_code(
                s, group=group, code="nope", ip="10.0.0.1"
            )
        assert (
            "Too many" in str(exc.value)
            or "too many" in str(exc.value).lower()
            or "rate" in str(exc.value).lower()
        )


def test_relink_rate_limit_is_per_ip() -> None:
    g_id, member_id = None, None
    with TestClient(__import__("splitmate.main", fromlist=["create_app"]).create_app()) as client:
        g_id, member_id = _create_group_and_member(client)
    with Session(get_engine()) as s:
        group = s.get(Group, g_id)
        # 5 wrong attempts from "10.0.0.1" — allowed.
        for _i in range(5):
            with pytest.raises(ServiceError):
                services.consume_relink_code(
                    s, group=group, code="nope", ip="10.0.0.1"
                )
        # "10.0.0.2" still allowed.
        with pytest.raises(ServiceError):
            services.consume_relink_code(
                s, group=group, code="nope", ip="10.0.0.2"
            )


def test_relink_rate_limit_resets_via_relink_limiter() -> None:
    """Calling ``relink_limiter().reset(...)`` clears the bucket."""
    g_id, member_id = None, None
    with TestClient(__import__("splitmate.main", fromlist=["create_app"]).create_app()) as client:
        g_id, member_id = _create_group_and_member(client)
    with Session(get_engine()) as s:
        group = s.get(Group, g_id)
        for _i in range(5):
            with pytest.raises(ServiceError):
                services.consume_relink_code(
                    s, group=group, code="nope", ip="10.0.0.99"
                )
        # Reset and try again — should be allowed.
        services.relink_limiter().reset(("rejoin", g_id, "10.0.0.99"))
        with pytest.raises(ServiceError):
            services.consume_relink_code(
                s, group=group, code="nope", ip="10.0.0.99"
            )
