"""Activity feed service.

The activity log is append-only (F7).  Every change to an expense or
settlement — create, edit, delete, restore — writes one row.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from ..models import Activity, Member


def list_activity(
    session: Session,
    *,
    group_id: int,
    page: int = 1,
    page_size: int = 50,
) -> list[Activity]:
    """Return activity rows for the group, newest first.

    ``page`` is 1-based; ``page_size`` is capped at 200 so a runaway
    query can't pull the entire history.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    offset = (page - 1) * page_size
    stmt = (
        select(Activity)
        .where(Activity.group_id == group_id)
        .order_by(Activity.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    return list(session.exec(stmt).all())


def count_activity(session: Session, *, group_id: int) -> int:
    return len(
        session.exec(
            select(Activity).where(Activity.group_id == group_id)
        ).all()
    )


def activity_to_dict(
    activity: Activity, *, members_by_id: dict[int, Member] | None = None
) -> dict[str, Any]:
    actor_name = None
    if activity.actor_id and members_by_id:
        actor = members_by_id.get(activity.actor_id)
        if actor is not None:
            actor_name = actor.display_name
    return {
        "id": activity.id,
        "kind": activity.kind,
        "summary": activity.summary,
        "actor_id": activity.actor_id,
        "actor_name": actor_name,
        "created_at": _iso(activity.created_at),
    }


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        # SQLite returns naive datetimes.
        return value.isoformat() + "Z"
    return value.isoformat()


__all__ = ["activity_to_dict", "count_activity", "list_activity"]
