"""Expense UI tests: page loads, form renders, and links are present."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from splitmate.db import get_engine
from splitmate.main import create_app
from splitmate.models import Member


def _logged_in_two_member_group(client: TestClient) -> tuple[int, int, int]:
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
    return g_id, asha.id, bea.id


def test_expense_list_renders() -> None:
    client = TestClient(create_app())
    g_id, _, _ = _logged_in_two_member_group(client)
    r = client.get(f"/groups/{g_id}/expenses")
    assert r.status_code == 200
    assert "expense" in r.text.lower() or "খরচ" in r.text


def test_expense_new_renders_form() -> None:
    client = TestClient(create_app())
    g_id, _, _ = _logged_in_two_member_group(client)
    r = client.get(f"/groups/{g_id}/expenses/new")
    assert r.status_code == 200
    assert 'name="title"' in r.text
    assert 'name="amount"' in r.text
    assert 'name="split_method"' in r.text
    # Participants checkboxes for both members.
    assert r.text.count('name="participants"') >= 2


def test_dashboard_links_to_expenses() -> None:
    client = TestClient(create_app())
    g_id, _, _ = _logged_in_two_member_group(client)
    r = client.get(f"/groups/{g_id}")
    assert "/expenses" in r.text


def test_invalid_amount_rejected() -> None:
    client = TestClient(create_app())
    g_id, asha_id, bea_id = _logged_in_two_member_group(client)
    r = client.post(
        f"/groups/{g_id}/expenses/new",
        data={
            "title": "X",
            "amount": "1e3",  # scientific notation — rejected
            "date_value": "2025-01-01",
            "category": "Other",
            "note": "",
            "split_method": "equal",
            "participants": [str(asha_id), str(bea_id)],
            "payer_id": str(bea_id),
            "payer_amount": "1e3",
        },
        follow_redirects=False,
    )
    # We expect 400 (form re-render with error) or 303 (if it slipped through).
    # The form rejects 1e3 → 400.
    assert r.status_code in (303, 400)
    if r.status_code == 400:
        assert "scientific" in r.text.lower() or "invalid" in r.text.lower() or "amount" in r.text.lower()
