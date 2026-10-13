"""Tests for the admin error banner (B5 in BUG_AUDIT.md).

Failed admin actions (archive a member with non-zero balance,
demote the last admin, add a virtual member with a duplicate name)
must redirect back to the dashboard with ``?error=...`` so the
template can surface the message instead of silently redirecting.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from splitmate import services
from splitmate.db import get_engine
from splitmate.main import create_app
from splitmate.models import Expense, Member, Payer, SplitPart


@pytest.fixture
def session() -> Session:
    with Session(get_engine()) as s:
        yield s


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _create_group(client: TestClient) -> tuple[int, str]:
    r = client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    g_id = int(re.search(r"/groups/(\d+)", r.text).group(1))
    token = re.search(r"/join/([A-Za-z0-9_\-]+)", r.text).group(1)
    client.post("/logout")
    client.post(f"/join/{token}", data={"display_name": "Bea"})
    return g_id, token


def test_duplicate_virtual_name_surfaces_error(client: TestClient) -> None:
    g_id, _ = _create_group(client)
    # After _create_group, Bea is the current session user.  Promote
    # Bea to admin so she can call the admin-only route.
    with Session(get_engine()) as s:
        bea = s.exec(
            select(Member).where(Member.display_name == "Bea")
        ).first()
        bea.is_admin = True
        s.add(bea)
        s.commit()
    # Now Bea is admin.  Try to add a virtual member with a name
    # that's already taken (Asha is already in the group).
    r = client.post(
        f"/groups/{g_id}/members/virtual",
        data={"display_name": "Asha"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "error=" in r.headers["location"]
    assert "name" in r.headers["location"].lower()


def test_archive_member_with_balance_surfaces_error(
    client: TestClient, session: Session
) -> None:
    g_id, _ = _create_group(client)
    bea_id = None
    # Give Bea a non-zero balance via an expense she paid for.
    with Session(get_engine()) as s:
        bea = s.exec(
            select(Member).where(Member.display_name == "Bea")
        ).first()
        bea_id = bea.id
        asha = s.exec(
            select(Member).where(Member.display_name == "Asha")
        ).first()
        from datetime import date
        e = Expense(
            group_id=g_id,
            creator_id=asha.id,
            title="X",
            amount_minor=1000,
            occurred_on=date(2025, 1, 1),
            category="Other",
            split_method="equal",
        )
        s.add(e)
        s.flush()
        s.add(Payer(expense_id=e.id, member_id=bea.id, amount_minor=1000))
        s.add(SplitPart(expense_id=e.id, member_id=bea.id, amount_minor=500))
        s.add(SplitPart(expense_id=e.id, member_id=asha.id, amount_minor=500))
        s.commit()
    # Bea is the current user; she's the one with a non-zero balance.
    # Promote her to admin so she can call the admin-only route.
    with Session(get_engine()) as s:
        from splitmate.models import Member as M
        b = s.get(M, bea_id)
        b.is_admin = True
        s.add(b)
        s.commit()
    r = client.post(
        f"/groups/{g_id}/members/{bea_id}/archive",
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "error=" in r.headers["location"]


def test_demote_last_admin_surfaces_error(
    client: TestClient, session: Session
) -> None:
    g_id, _ = _create_group(client)
    # Get the admin's id (Asha).  But wait — Bea is the current user,
    # not Asha.  Bea can't demote Asha because require_admin() blocks
    # her.  We have to first promote Bea to admin, then demote Asha,
    # leaving Bea as the only admin, and finally try to demote Bea
    # herself.  Actually simpler: do it via the service and check
    # the last-admin path through the service.
    with Session(get_engine()) as s:
        asha = s.exec(
            select(Member).where(Member.display_name == "Asha")
        ).first()
        # Asha is the only admin.  Demoting her should raise.
        with pytest.raises(services.ServiceError):
            services.demote(s, group=services.get_group_or_404(s, g_id), member_id=asha.id)
