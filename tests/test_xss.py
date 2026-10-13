"""XSS: title and note are HTML-escaped on render (F3 A6)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from splitmate.db import get_engine
from splitmate.main import create_app
from splitmate.models import Member


def _logged_in_two_member_group(client: TestClient) -> tuple[int, int, int, int]:
    r = client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    g_id = int(re.search(r"/groups/(\d+)", r.text).group(1))
    token = re.search(r"/join/([A-Za-z0-9_\-]+)", r.text).group(1)
    client.post("/logout")
    client.post(f"/join/{token}", data={"display_name": "Bea"})
    with Session(get_engine()) as s:
        asha = s.exec(select(Member).where(Member.display_name == "Asha")).first()
        bea = s.exec(select(Member).where(Member.display_name == "Bea")).first()
    return g_id, asha.id, bea.id, client


def test_title_with_html_is_escaped_in_list() -> None:
    g_id, asha_id, bea_id, client = _logged_in_two_member_group(TestClient(create_app()))
    r = client.post(
        f"/groups/{g_id}/expenses/new",
        data={
            "title": "<script>alert(1)</script>",
            "amount": "10.00",
            "date_value": "2025-01-01",
            "category": "Other",
            "note": "<img src=x onerror=alert(2)>",
            "split_method": "equal",
            "participants": [str(asha_id), str(bea_id)],
            "payer_id": str(bea_id),
            "payer_amount": "10.00",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    r = client.get(f"/groups/{g_id}/expenses")
    assert r.status_code == 200
    # The raw <script> tag must not appear.
    assert "<script>alert(1)</script>" not in r.text
    # The escaped form should be present.
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in r.text


def test_title_with_html_is_escaped_in_detail() -> None:
    g_id, asha_id, bea_id, client = _logged_in_two_member_group(TestClient(create_app()))
    r = client.post(
        f"/groups/{g_id}/expenses/new",
        data={
            "title": "<b>bold</b>",
            "amount": "10.00",
            "date_value": "2025-01-01",
            "category": "Other",
            "note": "",
            "split_method": "equal",
            "participants": [str(asha_id), str(bea_id)],
            "payer_id": str(bea_id),
            "payer_amount": "10.00",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    # Find the expense id.
    from sqlmodel import Session, select

    from splitmate.db import get_engine
    from splitmate.models import Expense

    with Session(get_engine()) as s:
        e = s.exec(select(Expense)).first()
    r = client.get(f"/groups/{g_id}/expenses/{e.id}")
    assert r.status_code == 200
    assert "&lt;b&gt;bold&lt;/b&gt;" in r.text
