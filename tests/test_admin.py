"""Admin-only routes reject non-admin members."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from splitmate.db import get_engine
from splitmate.models import Member


def _login_via_join(client: TestClient, token: str, name: str) -> None:
    client.post("/logout")
    r = client.post(f"/join/{token}", data={"display_name": name}, follow_redirects=False)
    assert r.status_code == 303, (r.status_code, r.text[:200])


def test_non_admin_cannot_rotate_invite(client: TestClient) -> None:
    # Admin creates group
    r = client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    m = re.search(r"/groups/(\d+)", r.text)
    assert m
    g_id = int(m.group(1))
    token = re.search(r"/join/([A-Za-z0-9_\-]+)", r.text).group(1)
    # A second member joins
    _login_via_join(client, token, "Bea")
    # Bea tries to rotate: 403
    r = client.post(f"/groups/{g_id}/invite/rotate", follow_redirects=False)
    assert r.status_code == 403


def test_non_admin_cannot_promote_or_demote(client: TestClient) -> None:
    r = client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    g_id = int(re.search(r"/groups/(\d+)", r.text).group(1))
    token = re.search(r"/join/([A-Za-z0-9_\-]+)", r.text).group(1)
    _login_via_join(client, token, "Bea")
    # Bea tries to demote Asha (admin)
    r = client.post(f"/groups/{g_id}/members/1/demote")
    assert r.status_code == 403


def test_admin_can_promote_and_demote(client: TestClient) -> None:
    r = client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    g_id = int(re.search(r"/groups/(\d+)", r.text).group(1))
    # Admin adds virtual member
    client.post(f"/groups/{g_id}/members/virtual", data={"display_name": "Cara"})
    # Find Cara's id
    with Session(get_engine()) as s:
        cara = s.exec(select(Member).where(Member.display_name == "Cara")).first()
    assert cara is not None
    # Promote
    r = client.post(f"/groups/{g_id}/members/{cara.id}/promote", follow_redirects=False)
    assert r.status_code == 303
    # Demote
    r = client.post(f"/groups/{g_id}/members/{cara.id}/demote", follow_redirects=False)
    assert r.status_code == 303
