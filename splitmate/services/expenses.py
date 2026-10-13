"""Expense service: creation, listing, soft-delete, restore.

Design notes
------------

* The client only sends **integer minor units** for amounts; floats
  are never accepted (F3 + A3).
* The server **recomputes every split** from the chosen method and
  participants; per-participant amounts are *not* trusted from the
  client (M4 A1).
* Every change writes an :class:`Activity` row (F7).
* Limits enforced: 5 000 expenses per group, archived members cannot
  be added.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlmodel import Session, select

from ..models import (
    Activity,
    ActivityKind,
    Category,
    Expense,
    Member,
    Payer,
    SplitMethod,
    SplitPart,
)

# Note: ``..services`` would resolve to ``splitmate.services`` which
# is *this package*.  We need the *original* ``splitmate.services``
# module, which used to live at ``splitmate/services.py`` and now
# lives at ``splitmate/services/_core.py`` and is re-exported from
# the package ``__init__``.
from . import ServiceError

# Re-export so ``from splitmate.services.expenses import ServiceError`` keeps
# working for callers who do not want to import the package ``errors`` module
# directly.
__all__ = [
    "ExpenseDraft",
    "ServiceError",
    "clean_note",
    "clean_title",
    "create_expense",
    "expense_to_dict",
    "get_expense_or_404",
    "list_expenses",
    "normalise_category",
    "normalise_method",
    "parse_amount",
    "parse_date",
    "restore_expense",
    "soft_delete_expense",
    "validate_draft",
]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


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


def normalise_method(value: str) -> SplitMethod:
    try:
        return SplitMethod(value)
    except ValueError as exc:
        raise ServiceError("invalid split method") from exc


def normalise_category(value: str) -> Category:
    try:
        return Category(value)
    except ValueError:
        return Category.OTHER


def clean_title(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ServiceError("title required")
    if len(cleaned) > 100:
        raise ServiceError("title too long")
    return cleaned


def clean_note(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 300:
        raise ServiceError("note too long")
    return cleaned


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExpenseDraft:
    title: str
    amount: int
    occurred_on: date
    category: Category
    note: str | None
    method: SplitMethod
    participants: list[int]
    payers: dict[int, int]


def validate_draft(
    session: Session,
    *,
    group_id: int,
    data: Mapping[str, Any],
) -> ExpenseDraft:
    """Parse and validate a form-style ``data`` mapping.

    Recognised keys:

    * ``title`` — string, 1..100 chars
    * ``amount`` — decimal string, parsed via :func:`parse_amount`
    * ``date`` — ISO date ``YYYY-MM-DD``
    * ``category`` — one of :class:`Category` values
    * ``note`` — optional, up to 300 chars
    * ``split_method`` — one of :class:`SplitMethod` values
    * ``participants`` — list[int] (or comma-separated string)
    * ``payer_amounts`` — mapping of ``member_id`` to decimal amount
      string.  For the simple one-payer form, ``payer_amount`` plus
      ``payer_id`` is also accepted.
    """
    title = clean_title(str(data.get("title", "")))
    amount = parse_amount(str(data.get("amount", "0")))
    if amount <= 0:
        raise ServiceError("amount must be positive")
    occurred_on = parse_date(str(data.get("date", "")))
    category = normalise_category(str(data.get("category", Category.OTHER.value)))
    note = clean_note(data.get("note"))
    method = normalise_method(str(data.get("split_method", SplitMethod.EQUAL.value)))

    participants = _coerce_int_list(data.get("participants"))
    if not participants:
        raise ServiceError("at least one participant required")
    payers = _coerce_payers(data, total=amount)
    if not payers:
        raise ServiceError("at least one payer required")
    if sum(payers.values()) != amount:
        raise ServiceError("payer amounts must sum to total")

    _check_active_members(session, group_id=group_id, member_ids=participants)
    _check_active_members(session, group_id=group_id, member_ids=list(payers))

    return ExpenseDraft(
        title=title,
        amount=amount,
        occurred_on=occurred_on,
        category=category,
        note=note,
        method=method,
        participants=participants,
        payers=payers,
    )


def _coerce_int_list(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        return [int(p) for p in parts]
    if isinstance(value, int):
        return [value]
    if isinstance(value, Iterable):
        out: list[int] = []
        for v in value:
            if v is None or v == "":
                continue
            out.append(int(v))
        return out
    return []


def _coerce_payers(data: Mapping[str, Any], *, total: int) -> dict[int, int]:
    """Read payers from the form mapping.

    Accepts ``payer_amounts`` as a mapping, or a single ``payer_id``
    plus ``payer_amount`` for the simple one-payer case.
    """
    raw = data.get("payer_amounts")
    out: dict[int, int] = {}
    if isinstance(raw, Mapping):
        for k, v in raw.items():
            try:
                pid = int(k)
            except (TypeError, ValueError):
                continue
            try:
                amount = parse_amount(str(v))
            except ServiceError:
                continue
            if amount > 0:
                out[pid] = amount
    elif raw is not None:
        # Sequence of ``"pid:amount"`` strings.
        for entry in raw:
            if not isinstance(entry, str):
                continue
            pid_s, _, amount_s = entry.partition(":")
            try:
                pid = int(pid_s)
                amount = parse_amount(amount_s)
            except (ValueError, ServiceError):
                continue
            if amount > 0:
                out[pid] = amount

    if not out and "payer_id" in data and "payer_amount" in data:
        try:
            pid = int(data["payer_id"])
            amount = parse_amount(str(data["payer_amount"]))
        except (ValueError, ServiceError):
            return {}
        if amount > 0:
            out[pid] = amount
    return out


def _check_active_members(
    session: Session, *, group_id: int, member_ids: Iterable[int]
) -> None:
    ids = list(member_ids)
    if not ids:
        return
    rows = session.exec(
        select(Member).where(Member.group_id == group_id, Member.id.in_(ids))
    ).all()
    by_id = {m.id: m for m in rows}
    for pid in ids:
        if pid not in by_id:
            raise ServiceError("unknown member")
        if by_id[pid].archived:
            raise ServiceError("archived member cannot be used")


# ---------------------------------------------------------------------------
# Limit + counts
# ---------------------------------------------------------------------------


def _max_expenses() -> int:
    from ..config import get_settings

    return get_settings().max_expenses_per_group


def _check_group_expense_limit(session: Session, group_id: int) -> None:
    n = len(
        session.exec(
            select(Expense).where(
                Expense.group_id == group_id, Expense.deleted_at.is_(None)
            )
        ).all()
    )
    if n >= _max_expenses():
        raise ServiceError(f"max expenses ({_max_expenses()}) reached")


# ---------------------------------------------------------------------------
# Compute split
# ---------------------------------------------------------------------------


def _compute_split(
    *,
    method: SplitMethod,
    total: int,
    participants: list[int],
    overrides: Mapping[int, int] | None = None,
) -> dict[int, int]:
    """Run the split engine, optionally using per-method overrides."""
    from ..split_engine import (
        SplitError,
        split_equal,
        split_exact,
        split_percentage,
        split_shares,
    )

    try:
        if method is SplitMethod.EQUAL:
            return split_equal(participants=participants, total=total)
        if method is SplitMethod.EXACT:
            amounts = dict(overrides or {})
            missing = [pid for pid in participants if pid not in amounts]
            if missing:
                raise ServiceError("missing exact amount for participant")
            return split_exact(amounts=amounts, total=total)
        if method is SplitMethod.PERCENTAGE:
            bps = dict(overrides or {})
            missing = [pid for pid in participants if pid not in bps]
            if missing:
                raise ServiceError("missing percentage for participant")
            return split_percentage(
                participants=participants, basis_points=bps, total=total
            )
        if method is SplitMethod.SHARES:
            shares = dict(overrides or {})
            missing = [pid for pid in participants if pid not in shares]
            if missing:
                raise ServiceError("missing share for participant")
            return split_shares(participants=participants, shares=shares, total=total)
    except SplitError as exc:
        raise ServiceError(str(exc)) from exc
    raise ServiceError("invalid split method")  # pragma: no cover


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def create_expense(
    session: Session,
    *,
    group_id: int,
    creator_id: int,
    data: Mapping[str, Any],
    split_overrides: Mapping[int, int] | None = None,
    idempotency_key: str | None = None,
) -> Expense:
    """Validate ``data`` and create the expense + payers + split parts.

    If ``idempotency_key`` is provided and matches an earlier call
    from the same ``(group, member)``, the original expense is
    returned without creating a duplicate (F3 / M6 A4).
    """
    if idempotency_key:
        from .idempotency import lookup_expense, reserve_key

        existing = lookup_expense(
            session,
            group_id=group_id,
            member_id=creator_id,
            key=idempotency_key,
        )
        if existing is not None:
            return existing

    _check_group_expense_limit(session, group_id)
    draft = validate_draft(session, group_id=group_id, data=data)
    split_amounts = _compute_split(
        method=draft.method,
        total=draft.amount,
        participants=draft.participants,
        overrides=split_overrides,
    )
    expense = Expense(
        group_id=group_id,
        creator_id=creator_id,
        title=draft.title,
        amount_minor=draft.amount,
        occurred_on=draft.occurred_on,
        category=draft.category.value,
        note=draft.note,
        split_method=draft.method.value,
    )
    session.add(expense)
    session.flush()
    for pid, amt in draft.payers.items():
        session.add(Payer(expense_id=expense.id, member_id=pid, amount_minor=amt))
    for pid, amt in split_amounts.items():
        session.add(
            SplitPart(expense_id=expense.id, member_id=pid, amount_minor=amt)
        )
    session.add(
        Activity(
            group_id=group_id,
            actor_id=creator_id,
            kind=ActivityKind.EXPENSE_CREATED,
            summary=(
                f"expense {draft.title!r} created "
                f"({draft.method.value}, {draft.amount} minor)"
            ),
        )
    )
    if idempotency_key:
        from .idempotency import lookup_expense, reserve_key

        reserved = reserve_key(
            session,
            group_id=group_id,
            member_id=creator_id,
            key=idempotency_key,
            expense_id=expense.id,
        )
        if reserved is None:
            # Concurrent duplicate: another transaction already reserved
            # the same key.  The reserve_key helper rolled back our
            # transaction (including the expense and its payers), so
            # we look up the original expense and return it instead of
            # committing an empty transaction.
            existing = lookup_expense(
                session,
                group_id=group_id,
                member_id=creator_id,
                key=idempotency_key,
            )
            if existing is not None:
                return existing
    session.commit()
    session.refresh(expense)
    return expense


def list_expenses(
    session: Session,
    *,
    group_id: int,
    include_deleted: bool = False,
    limit: int | None = None,
) -> list[Expense]:
    stmt = select(Expense).where(Expense.group_id == group_id)
    if not include_deleted:
        stmt = stmt.where(Expense.deleted_at.is_(None))
    stmt = stmt.order_by(Expense.occurred_on.desc(), Expense.id.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.exec(stmt).all())


def get_expense_or_404(
    session: Session, group_id: int, expense_id: int
) -> Expense:
    e = session.exec(
        select(Expense).where(
            Expense.id == expense_id, Expense.group_id == group_id
        )
    ).first()
    if e is None:
        raise ServiceError("not found")
    return e


def soft_delete_expense(
    session: Session,
    *,
    group_id: int,
    expense_id: int,
    actor_id: int | None,
) -> Expense:
    expense = get_expense_or_404(session, group_id, expense_id)
    if expense.deleted_at is not None:
        return expense
    expense.deleted_at = datetime.now(UTC)
    session.add(expense)
    session.add(
        Activity(
            group_id=group_id,
            actor_id=actor_id,
            kind=ActivityKind.EXPENSE_DELETED,
            summary=f"expense {expense.title!r} deleted",
        )
    )
    session.commit()
    session.refresh(expense)
    return expense


def restore_expense(
    session: Session,
    *,
    group_id: int,
    expense_id: int,
    actor_id: int | None,
) -> Expense:
    expense = get_expense_or_404(session, group_id, expense_id)
    if expense.deleted_at is None:
        return expense
    if _count_active_expenses(session, group_id) >= _max_expenses():
        raise ServiceError("group at expense limit; cannot restore")
    expense.deleted_at = None
    session.add(expense)
    session.add(
        Activity(
            group_id=group_id,
            actor_id=actor_id,
            kind=ActivityKind.EXPENSE_RESTORED,
            summary=f"expense {expense.title!r} restored",
        )
    )
    session.commit()
    session.refresh(expense)
    return expense


def _count_active_expenses(session: Session, group_id: int) -> int:
    return len(
        session.exec(
            select(Expense).where(
                Expense.group_id == group_id, Expense.deleted_at.is_(None)
            )
        ).all()
    )


def expense_to_dict(expense: Expense) -> dict[str, Any]:
    return {
        "id": expense.id,
        "title": expense.title,
        "amount_minor": expense.amount_minor,
        "occurred_on": expense.occurred_on.isoformat(),
        "category": expense.category,
        "note": expense.note,
        "split_method": expense.split_method,
        "deleted_at": expense.deleted_at.isoformat() if expense.deleted_at else None,
    }


__all__ = [
    "ExpenseDraft",
    "ServiceError",
    "clean_note",
    "clean_title",
    "create_expense",
    "expense_to_dict",
    "get_expense_or_404",
    "list_expenses",
    "normalise_category",
    "normalise_method",
    "parse_amount",
    "parse_date",
    "restore_expense",
    "soft_delete_expense",
    "validate_draft",
]
