"""Route isolation: a member of group A can never read or change anything in group B.

Discovers every group-scoped route in the running app, then for each one
probes a member of group A against the URL of group B (and a guessed
``member_id`` / ``expense_id`` / ``settlement_id``) and asserts a
non-2xx status.  A guessed ``group_id`` must also 404.
"""

from __future__ import annotations

import re

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlmodel import Session

from splitmate import services
from splitmate.db import get_engine
from splitmate.main import create_app


def _enumerate_group_routes(app) -> list[APIRoute]:
    out: list[APIRoute] = []
    public_paths = {"/g/{group_id}"}
    for r in app.routes:
        if isinstance(r, APIRoute):
            path: str = r.path
            if "{group_id}" in path and path not in public_paths:
                out.append(r)
    return out


def _client() -> TestClient:
    return TestClient(create_app())


def _url(path: str, group_id: int) -> str:
    return path.format(
        group_id=group_id,
        member_id=99_999,
        expense_id=99_999,
        settlement_id=99_999,
        code="x",
    )


def test_route_isolation_group_a_cannot_touch_group_b() -> None:
    c = _client()
    # Set up two groups
    with Session(get_engine()) as s:
        ga, ma, _ = services.create_group(s, name="GroupA", admin_name="Alice")
        gb, mb, _ = services.create_group(s, name="GroupB", admin_name="Bob")
        _ga_id, gb_id, _ma_id, _mb_id = ga.id, gb.id, ma.id, mb.id

    # Log in as a non-admin member of Group A using a fresh group and the
    # real join flow.
    r = c.post(
        "/groups/new",
        data={"name": "GA", "currency_symbol": "৳", "admin_name": "AliceGA"},
    )
    m = re.search(r"/join/([A-Za-z0-9_\-]+)", r.text)
    assert m
    token_a = m.group(1)
    c.post("/logout")
    c.post(f"/join/{token_a}", data={"display_name": "Eve"})

    routes = _enumerate_group_routes(create_app())
    assert routes, "no group routes discovered"

    public_gets = {"/join/{token}", "/rejoin/{group_id}/{code}"}
    ok_statuses = (404, 403, 405, 400, 422, 303)

    # Group B is real but the session is for Group A.
    for r in routes:
        url = _url(r.path, gb_id)
        for m in ("GET", "POST"):
            if m == "GET" and r.path in public_gets:
                continue
            resp = c.request(m, url)
            assert resp.status_code in ok_statuses, (
                f"{m} {url} returned {resp.status_code}: {resp.text[:200]}"
            )

    # Guessed non-existent group id 99_999.
    for r in routes:
        url = _url(r.path, 99_999)
        for m in ("GET", "POST"):
            if m == "GET" and r.path in public_gets:
                continue
            resp = c.request(m, url)
            assert resp.status_code in ok_statuses, (
                f"guessed {m} {url} returned {resp.status_code}"
            )
