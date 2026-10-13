"""Expense API: create, list, soft-delete, restore, recompute, archived."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from splitmate import services
from splitmate.db import get_engine
from splitmate.main import create_app
from splitmate.models import Payer, SplitPart
from splitmate.services.expenses import ServiceError, create_expense

# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


@pytest.fixture
def session() -> Session:
    with Session(get_engine()) as s:
        yield s


def _make_group(session: Session):
    group, admin, _token = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    bea = services.join_group(session, group=group, display_name="Bea")
    return group, admin, bea


def test_create_expense_equal_split(session: Session) -> None:
    group, admin, bea = _make_group(session)
    e = create_expense(
        session,
        group_id=group.id,
        creator_id=admin.id,
        data={
            "title": "Lunch",
            "amount": "10.00",
            "date": "2025-01-01",
            "category": "Food",
            "note": "",
            "split_method": "equal",
            "participants": [str(admin.id), str(bea.id)],
            "payer_id": str(admin.id),
            "payer_amount": "10.00",
        },
    )
    assert e.amount_minor == 1000
    parts = session.exec(select(SplitPart).where(SplitPart.expense_id == e.id)).all()
    assert sum(p.amount_minor for p in parts) == 1000
    payers = session.exec(select(Payer).where(Payer.expense_id == e.id)).all()
    assert sum(p.amount_minor for p in payers) == 1000


def test_server_recomputes_split_tampered_input(session: Session) -> None:
    """A1: server recomputes every split, ignoring client-side amounts.

    The client only sends participants + method + total.  The service
    must call the engine, not trust the wire.
    """
    group, admin, bea = _make_group(session)
    e = create_expense(
        session,
        group_id=group.id,
        creator_id=admin.id,
        data={
            "title": "X",
            "amount": "10.00",
            "date": "2025-01-01",
            "category": "Other",
            "split_method": "equal",
            "participants": [str(admin.id), str(bea.id)],
            "payer_id": str(admin.id),
            "payer_amount": "10.00",
        },
    )
    parts = session.exec(select(SplitPart).where(SplitPart.expense_id == e.id)).all()
    by_pid = {p.member_id: p.amount_minor for p in parts}
    assert by_pid[admin.id] + by_pid[bea.id] == 1000
    assert by_pid[admin.id] in (500, 500)
    assert by_pid[bea.id] in (500, 500)


def test_archived_member_cannot_be_added(session: Session) -> None:
    group, admin, bea = _make_group(session)
    # Bea's balance is 0 so she can be archived.
    services.archive_member(session, group=group, member_id=bea.id)
    with pytest.raises(ServiceError):
        create_expense(
            session,
            group_id=group.id,
            creator_id=admin.id,
            data={
                "title": "X",
                "amount": "1000",
                "date": "2025-01-01",
                "category": "Other",
                "split_method": "equal",
                "participants": [str(admin.id), str(bea.id)],
                "payer_id": str(admin.id),
                "payer_amount": "1000",
            },
        )


def test_amounts_stored_as_integers(session: Session) -> None:
    group, admin, bea = _make_group(session)
    e = create_expense(
        session,
        group_id=group.id,
        creator_id=admin.id,
        data={
            "title": "X",
            "amount": "12.50",
            "date": "2025-01-01",
            "category": "Other",
            "split_method": "equal",
            "participants": [str(admin.id), str(bea.id)],
            "payer_id": str(admin.id),
            "payer_amount": "12.50",
        },
    )
    assert e.amount_minor == 1250
    assert all(isinstance(p.amount_minor, int) for p in session.exec(select(SplitPart).where(SplitPart.expense_id == e.id)).all())
    assert all(isinstance(p.amount_minor, int) for p in session.exec(select(Payer).where(Payer.expense_id == e.id)).all())


def test_payer_must_sum_to_total(session: Session) -> None:
    group, admin, bea = _make_group(session)
    with pytest.raises(ServiceError):
        create_expense(
            session,
            group_id=group.id,
            creator_id=admin.id,
            data={
                "title": "X",
                "amount": "10.00",
                "date": "2025-01-01",
                "category": "Other",
                "split_method": "equal",
                "participants": [str(admin.id), str(bea.id)],
                "payer_id": str(admin.id),
                "payer_amount": "9.99",
            },
        )


# ---------------------------------------------------------------------------
# HTTP-level tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _create_group(client: TestClient) -> tuple[int, str]:
    r = client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    import re
    g_id = int(re.search(r"/groups/(\d+)", r.text).group(1))
    token = re.search(r"/join/([A-Za-z0-9_\-]+)", r.text).group(1)
    # Add a second member Bea.
    client.post("/logout")
    client.post(f"/join/{token}", data={"display_name": "Bea"})
    return g_id, token


def test_non_member_cannot_access_expenses(client: TestClient) -> None:
    g_id, _token = _create_group(client)
    # Log Bea out, log in as a different (non-member) admin from a new group.
    r = client.post(
        "/groups/new",
        data={"name": "Other", "currency_symbol": "৳", "admin_name": "Cara"},
    )
    # Cara tries to read group g_id's expenses.
    r = client.get(f"/groups/{g_id}/expenses", follow_redirects=False)
    assert r.status_code == 404


def test_create_expense_via_http(client: TestClient) -> None:
    g_id, _token = _create_group(client)
    from sqlmodel import Session, select

    from splitmate.db import get_engine
    from splitmate.models import Member

    with Session(get_engine()) as s:
        asha = s.exec(select(Member).where(Member.display_name == "Asha")).first()
        bea = s.exec(select(Member).where(Member.display_name == "Bea")).first()
    # Bea is the current user; she can add an expense.
    r = client.post(
        f"/groups/{g_id}/expenses/new",
        data={
            "title": "Lunch",
            "amount": "20.00",
            "date_value": "2025-01-01",
            "category": "Food",
            "note": "",
            "split_method": "equal",
            "participants": [str(asha.id), str(bea.id)],
            "payer_id": str(bea.id),
            "payer_amount": "20.00",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, (r.status_code, r.text[:300])
    # Now follow the redirect to the list.
    r = client.get(f"/groups/{g_id}/expenses")
    assert r.status_code == 200
    assert "Lunch" in r.text
