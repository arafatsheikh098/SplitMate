"""Settlement service: create, list, soft-delete, restore.

A settlement models a real-world payment from one member to another
(cash / bKash / Nagad / bank / other).  Recording it shifts the
recipient's balance up by ``amount_minor`` and the sender's down.
Invalid inputs (zero, negative, self-payment, unknown members) are
rejected.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlmodel import Session, select

from ..models import (
    Activity,
    ActivityKind,
    Member,
    Settlement,
    SettlementMethod,
)
from . import ServiceError


@dataclass(frozen=True)
class SettlementDraft:
    from_id: int
    to_id: int
    amount: int
    method: SettlementMethod
    paid_on: date
    note: str | None


def parse_amount(text: str) -> int:
    from ..money import MoneyError
    from ..money import parse_amount as _parse

    try:
        return _parse(text)
    except MoneyError as exc:
        raise ServiceError(str(exc)) from exc


def parse_date(text: str) -> date:
    if not text:
        raise ServiceError("date required")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ServiceError("invalid date") from exc


def normalise_method(value: str) -> SettlementMethod:
    try:
        return SettlementMethod(value)
    except ValueError as exc:
        raise ServiceError("invalid method") from exc


def clean_note(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 300:
        raise ServiceError("note too long")
    return cleaned


def _parse_int(value: str | int, *, field: str) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ServiceError(f"{field} must be a number") from exc


def validate_draft(
    session: Session,
    *,
    group_id: int,
    data: Mapping[str, object],
) -> SettlementDraft:
    """Parse the form-style mapping into a checked draft."""
    from_id = _parse_int(data.get("from_id", ""), field="from_id")
    to_id = _parse_int(data.get("to_id", ""), field="to_id")
    if from_id == to_id:
        raise ServiceError("cannot pay yourself")
    amount = parse_amount(str(data.get("amount", "")))
    if amount <= 0:
        raise ServiceError("amount must be positive")
    method = normalise_method(str(data.get("method", SettlementMethod.OTHER.value)))
    paid_on = parse_date(str(data.get("date", "")))
    note = clean_note(data.get("note"))

    members = session.exec(
        select(Member).where(Member.group_id == group_id)
    ).all()
    by_id = {m.id: m for m in members}
    for pid in (from_id, to_id):
        if pid not in by_id:
            raise ServiceError("unknown member")
        if by_id[pid].archived:
            raise ServiceError("archived member cannot settle")
    return SettlementDraft(
        from_id=from_id,
        to_id=to_id,
        amount=amount,
        method=method,
        paid_on=paid_on,
        note=note,
    )


def create_settlement(
    session: Session,
    *,
    group_id: int,
    creator_id: int,
    data: Mapping[str, object],
) -> Settlement:
    """Create a settlement from a form mapping."""
    draft = validate_draft(session, group_id=group_id, data=data)
    s = Settlement(
        group_id=group_id,
        creator_id=creator_id,
        from_member_id=draft.from_id,
        to_member_id=draft.to_id,
        amount_minor=draft.amount,
        method=draft.method.value,
        paid_on=draft.paid_on,
        note=draft.note,
    )
    session.add(s)
    session.flush()
    session.add(
        Activity(
            group_id=group_id,
            actor_id=creator_id,
            kind=ActivityKind.SETTLEMENT_CREATED,
            summary=(
                f"settlement {draft.amount} minor from {draft.from_id} "
                f"to {draft.to_id} via {draft.method.value}"
            ),
        )
    )
    session.commit()
    session.refresh(s)
    return s


def list_settlements(
    session: Session,
    *,
    group_id: int,
    include_deleted: bool = False,
    limit: int | None = None,
) -> list[Settlement]:
    stmt = select(Settlement).where(Settlement.group_id == group_id)
    if not include_deleted:
        stmt = stmt.where(Settlement.deleted_at.is_(None))
    stmt = stmt.order_by(Settlement.paid_on.desc(), Settlement.id.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.exec(stmt).all())


def get_settlement_or_none(
    session: Session, group_id: int, settlement_id: int
) -> Settlement | None:
    return session.exec(
        select(Settlement).where(
            Settlement.id == settlement_id,
            Settlement.group_id == group_id,
        )
    ).first()


def get_settlement_or_404(
    session: Session, group_id: int, settlement_id: int
) -> Settlement:
    s = get_settlement_or_none(session, group_id, settlement_id)
    if s is None:
        raise ServiceError("not found")
    return s


def soft_delete_settlement(
    session: Session,
    *,
    group_id: int,
    settlement_id: int,
    actor_id: int | None,
) -> Settlement:
    s = get_settlement_or_404(session, group_id, settlement_id)
    if s.deleted_at is not None:
        return s
    s.deleted_at = datetime.now(UTC)
    session.add(s)
    session.add(
        Activity(
            group_id=group_id,
            actor_id=actor_id,
            kind=ActivityKind.SETTLEMENT_DELETED,
            summary=f"settlement {s.id} deleted",
        )
    )
    session.commit()
    session.refresh(s)
    return s


def restore_settlement(
    session: Session,
    *,
    group_id: int,
    settlement_id: int,
    actor_id: int | None,
) -> Settlement:
    s = get_settlement_or_404(session, group_id, settlement_id)
    if s.deleted_at is None:
        return s
    s.deleted_at = None
    session.add(s)
    session.add(
        Activity(
            group_id=group_id,
            actor_id=actor_id,
            kind=ActivityKind.SETTLEMENT_RESTORED,
            summary=f"settlement {s.id} restored",
        )
    )
    session.commit()
    session.refresh(s)
    return s


__all__ = [
    "SettlementDraft",
    "ServiceError",
    "create_settlement",
    "get_settlement_or_404",
    "get_settlement_or_none",
    "list_settlements",
    "restore_settlement",
    "soft_delete_settlement",
    "validate_draft",
]
