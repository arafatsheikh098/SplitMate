"""Basic HTTP flow for groups, join, and rejoin."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient


def _post_create(client: TestClient, name: str, admin: str = "Asha") -> str:
    r = client.post(
        "/groups/new",
        data={"name": name, "currency_symbol": "৳", "admin_name": admin},
    )
    m = re.search(r"/join/([A-Za-z0-9_\-]+)", r.text)
    assert m
    return m.group(1)


def test_create_then_logout_then_login_via_join(client: TestClient) -> None:
    token = _post_create(client, "Trip")
    client.post("/logout")
    r = client.post(f"/join/{token}", data={"display_name": "Bea"}, follow_redirects=False)
    assert r.status_code == 303
    r2 = client.get("/")
    # Bea sees the group's dashboard link
    assert "Trip" in r2.text or "/groups/" in r2.text


def test_invite_rotate_makes_old_link_404(client: TestClient) -> None:
    import re

    r = client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    g_id = int(re.search(r"/groups/(\d+)", r.text).group(1))
    old = re.search(r"/join/([A-Za-z0-9_\-]+)", r.text).group(1)
    # Rotate the invite: the old token must stop working.
    r3 = client.post(f"/groups/{g_id}/invite/rotate", follow_redirects=False)
    new_token = re.search(r"/join/([A-Za-z0-9_\-]+)", r3.text).group(1)
    assert new_token != old
    r4 = client.get(f"/join/{old}")
    assert r4.status_code == 404
    # And the new one works
    r5 = client.get(f"/join/{new_token}")
    assert r5.status_code == 200


def test_join_invalid_token_404(client: TestClient) -> None:
    r = client.get("/join/not-a-real-token")
    assert r.status_code == 404


def test_join_blank_name_400(client: TestClient) -> None:
    token = _post_create(client, "Trip")
    client.post("/logout")
    r = client.post(f"/join/{token}", data={"display_name": "   "})
    assert r.status_code == 400
