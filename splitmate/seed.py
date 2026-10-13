"""Demo seed: a 4-person trip with 12 expenses and 2 settlements.

Running this twice in a row is a no-op (M7 A6): if the demo group
already exists, the function returns its id without creating anything
new.  This is the canonical "fresh-clone demo" path.

Usage::

    python -m splitmate.seed            # idempotent
    python -m splitmate.seed --reset    # delete the demo and reseed
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from sqlmodel import Session, select

from . import services
from .db import get_engine, get_session
from .models import Group
from .services.expenses import create_expense
from .services.settlements import create_settlement

DEMO_GROUP_NAME = "Demo Trip"
DEMO_ADMIN = "Asha"
DEMO_MEMBERS = ("Asha", "Bea", "Cami", "Dee")


def _find_demo_group(session: Session) -> Group | None:
    return session.exec(
        select(Group).where(Group.name == DEMO_GROUP_NAME)
    ).first()


def seed(*, reset: bool = False) -> int:
    """Create the demo group if missing.  Returns the group id.

    When ``reset`` is true, deletes the existing demo group first.
    """
    engine = get_engine()
    with Session(engine) as session:
        existing = _find_demo_group(session)
        if existing is not None:
            if not reset:
                return existing.id
            # Reset path: hard-delete child rows explicitly.  We
            # delete in the order required by the foreign keys: the
            # deepest children first (``split_part``, ``payer`` hang
            # off ``expense``), then ``expense``, then top-level
            # group-scoped rows, then ``member``, finally ``group``.
            from sqlmodel import delete

            from .models import (
                Activity,
                Expense,
                IdempotencyKey,
                Member,
                Payer,
                RejoinCode,
                Settlement,
                SplitPart,
            )

            gid = existing.id

            # 1. Find all expense ids in this group, so we can drop
            #    children that hang off Expense without a direct
            #    group_id column.
            expense_ids = list(
                session.exec(
                    select(Expense.id).where(Expense.group_id == gid)
                ).all()
            )
            if expense_ids:
                session.exec(
                    delete(SplitPart).where(SplitPart.expense_id.in_(expense_ids))
                )
                session.exec(
                    delete(Payer).where(Payer.expense_id.in_(expense_ids))
                )
                session.exec(
                    delete(IdempotencyKey).where(
                        IdempotencyKey.expense_id.in_(expense_ids)
                    )
                )
                session.exec(delete(Expense).where(Expense.group_id == gid))
            session.exec(delete(Activity).where(Activity.group_id == gid))
            session.exec(delete(Settlement).where(Settlement.group_id == gid))
            session.exec(delete(RejoinCode).where(RejoinCode.group_id == gid))
            session.exec(delete(Member).where(Member.group_id == gid))
            # ``Group`` doesn't have a group_id column; delete it by id.
            group_to_drop = session.get(Group, gid)
            if group_to_drop is not None:
                session.delete(group_to_drop)
            session.commit()

        group, admin, _ = services.create_group(
            session,
            name=DEMO_GROUP_NAME,
            currency_symbol="৳",
            admin_name=DEMO_ADMIN,
        )
        members = {admin.display_name: admin}
        for name in DEMO_MEMBERS[1:]:
            members[name] = services.join_group(
                session, group=group, display_name=name
            )

        def add_expense(
            title: str,
            amount: str,
            payer: str,
            participants: tuple[str, ...],
            d: date,
        ) -> None:
            data = {
                "title": title,
                "amount": amount,
                "date": d.isoformat(),
                "category": "Other",
                "split_method": "equal",
                "participants": [str(members[n].id) for n in participants],
                "payer_id": str(members[payer].id),
                "payer_amount": amount,
            }
            create_expense(
                session,
                group_id=group.id,
                creator_id=admin.id,
                data=data,
            )

        # 12 expenses spread across the trip.
        add_expense("Hotel night 1", "120.00", "Asha",
                    DEMO_MEMBERS, date(2025, 6, 1))
        add_expense("Hotel night 2", "120.00", "Bea",
                    DEMO_MEMBERS, date(2025, 6, 2))
        add_expense("Lunch Day 1", "40.00", "Cami",
                    DEMO_MEMBERS, date(2025, 6, 1))
        add_expense("Dinner Day 1", "60.00", "Asha",
                    DEMO_MEMBERS, date(2025, 6, 1))
        add_expense("Taxi to station", "20.00", "Dee",
                    DEMO_MEMBERS, date(2025, 6, 2))
        add_expense("Train tickets", "80.00", "Bea",
                    DEMO_MEMBERS, date(2025, 6, 2))
        add_expense("Snacks", "16.00", "Cami",
                    DEMO_MEMBERS, date(2025, 6, 2))
        add_expense("Souvenirs", "32.00", "Asha",
                    DEMO_MEMBERS, date(2025, 6, 3))
        add_expense("Lunch Day 3", "44.00", "Dee",
                    DEMO_MEMBERS, date(2025, 6, 3))
        add_expense("Boat tour", "100.00", "Bea",
                    DEMO_MEMBERS, date(2025, 6, 3))
        add_expense("Dinner Day 3", "72.00", "Cami",
                    DEMO_MEMBERS, date(2025, 6, 3))
        add_expense("Coffee morning", "12.00", "Asha",
                    DEMO_MEMBERS, date(2025, 6, 4))

        # Two partial settlements, leaving a non-zero balance to demo.
        create_settlement(
            session,
            group_id=group.id,
            creator_id=admin.id,
            data={
                "from_id": str(members["Bea"].id),
                "to_id": str(members["Asha"].id),
                "amount": "50.00",
                "method": "cash",
                "date": "2025-06-04",
                "note": "first half",
            },
        )
        create_settlement(
            session,
            group_id=group.id,
            creator_id=admin.id,
            data={
                "from_id": str(members["Cami"].id),
                "to_id": str(members["Asha"].id),
                "amount": "30.00",
                "method": "bKash",
                "date": "2025-06-04",
                "note": "snacks share",
            },
        )
        return group.id


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Seed the demo group.")
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete the existing demo group before reseeding.",
    )
    args = parser.parse_args(argv)
    # Initialise the engine and create the schema if needed.
    next(get_session()).close()
    gid = seed(reset=args.reset)
    print(f"demo group id: {gid}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
