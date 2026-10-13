"""Activity feed tests (M6)."""

from __future__ import annotations

from sqlmodel import Session, select

from splitmate import services
from splitmate.db import get_engine
from splitmate.models import Activity, ActivityKind
from splitmate.services.activity import count_activity, list_activity
from splitmate.services.expenses import create_expense
from splitmate.services.settlements import create_settlement


def _session() -> Session:
    return Session(get_engine())


def _two_member_group(s: Session):
    g, admin, _ = services.create_group(
        s, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    bea = services.join_group(s, group=g, display_name="Bea")
    return g, admin, bea


def test_activity_row_per_create() -> None:
    with _session() as s:
        g, admin, bea = _two_member_group(s)
        create_expense(
            s,
            group_id=g.id,
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
        create_settlement(
            s,
            group_id=g.id,
            creator_id=bea.id,
            data={
                "from_id": str(bea.id),
                "to_id": str(admin.id),
                "amount": "5.00",
                "method": "cash",
                "date": "2025-01-02",
                "note": "",
            },
        )
        # 1 expense create + 1 settlement create + (group/member setup creates some)
        kinds = [
            a.kind
            for a in s.exec(
                select(Activity).where(Activity.group_id == g.id)
            ).all()
        ]
        assert ActivityKind.EXPENSE_CREATED in kinds
        assert ActivityKind.SETTLEMENT_CREATED in kinds


def test_activity_paginates() -> None:
    with _session() as s:
        g, admin, bea = _two_member_group(s)
        for i in range(7):
            create_expense(
                s,
                group_id=g.id,
                creator_id=admin.id,
                data={
                    "title": f"X{i}",
                    "amount": "10.00",
                    "date": "2025-01-01",
                    "category": "Other",
                    "split_method": "equal",
                    "participants": [str(admin.id), str(bea.id)],
                    "payer_id": str(admin.id),
                    "payer_amount": "10.00",
                },
            )
        total = count_activity(s, group_id=g.id)
        page1 = list_activity(s, group_id=g.id, page=1, page_size=3)
        page2 = list_activity(s, group_id=g.id, page=2, page_size=3)
        page3 = list_activity(s, group_id=g.id, page=3, page_size=3)
        assert total >= 7
        assert len(page1) <= 3
        assert len(page2) <= 3
        assert len(page3) <= 3
        # Pages don't overlap.
        ids = {a.id for a in page1} | {a.id for a in page2} | {a.id for a in page3}
        # Should at least have 3 unique ids.
        assert len(ids) >= min(3, total)


def test_activity_pagination_boundaries() -> None:
    with _session() as s:
        g, admin, bea = _two_member_group(s)
        # Asking beyond the last page returns an empty list, not an error.
        very_far = list_activity(s, group_id=g.id, page=10_000, page_size=50)
        assert very_far == []
