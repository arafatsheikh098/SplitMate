"""Plain-text summary builder for sharing a group over chat / email.

Produces a stable, copy-pasteable summary in the chosen language
(M7 A1).  The format is intentionally simple: text, no markdown, no
HTML — anything that handles WhatsApp, SMS or email can render it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlmodel import Session, select

from ..i18n import t as _t
from ..models import Expense, Member, Settlement, SplitPart
from .balances import group_balances
from .settle import settle_plan


@dataclass(frozen=True)
class SummarySection:
    title: str
    lines: tuple[str, ...]


def _expense_lines(
    session: Session,
    *,
    group_id: int,
    members: dict[int, Member],
    currency: str,
) -> tuple[str, ...]:
    expenses = session.exec(
        select(Expense)
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .order_by(Expense.occurred_on.asc(), Expense.id.asc())
    ).all()
    if not expenses:
        return ()
    out: list[str] = []
    for e in expenses:
        parts = session.exec(
            select(SplitPart).where(SplitPart.expense_id == e.id)
        ).all()
        participants = ", ".join(
            members[p.member_id].display_name for p in parts if p.member_id in members
        )
        amount = f"{e.amount_minor / 100:.2f} {currency}"
        out.append(
            f"• {e.occurred_on.isoformat()}  {e.title} — {amount}"
            f"\n    split: {participants}"
        )
    return tuple(out)


def _settlement_lines(
    session: Session,
    *,
    group_id: int,
    members: dict[int, Member],
    currency: str,
) -> tuple[str, ...]:
    rows = session.exec(
        select(Settlement)
        .where(Settlement.group_id == group_id, Settlement.deleted_at.is_(None))
        .order_by(Settlement.paid_on.asc(), Settlement.id.asc())
    ).all()
    if not rows:
        return ()
    out: list[str] = []
    for s in rows:
        from_name = members.get(s.from_member_id)
        to_name = members.get(s.to_member_id)
        amount = f"{s.amount_minor / 100:.2f} {currency}"
        out.append(
            f"• {s.paid_on.isoformat()}  {from_name.display_name if from_name else s.from_member_id}"
            f" → {to_name.display_name if to_name else s.to_member_id}  {amount}"
            f" ({s.method})"
        )
    return tuple(out)


def _balance_lines(
    balances: dict[int, int],
    members: dict[int, Member],
    currency: str,
    lang: str,
) -> tuple[str, ...]:
    out: list[str] = []
    for mid in sorted(balances):
        bal = balances[mid]
        if bal == 0:
            continue
        name = members[mid].display_name if mid in members else str(mid)
        amount = f"{abs(bal) / 100:.2f} {currency}"
        if bal > 0:
            out.append(_t("balance.owed", lang=lang, name=name, amount=amount))
        else:
            out.append(_t("balance.owes", lang=lang, name=name, amount=amount))
    if not out:
        out.append(_t("balance.settled", lang=lang))
    return tuple(out)


def _plan_lines(
    plan: Iterable[tuple[int, int, int]],
    members: dict[int, Member],
    currency: str,
) -> tuple[str, ...]:
    out: list[str] = []
    for from_id, to_id, amount in plan:
        from_name = members[from_id].display_name if from_id in members else str(from_id)
        to_name = members[to_id].display_name if to_id in members else str(to_id)
        out.append(
            f"• {from_name} → {to_name}: {amount / 100:.2f} {currency}"
        )
    if not out:
        out.append("—")
    return tuple(out)


def build_summary(
    session: Session,
    *,
    group_id: int,
    lang: str = "en",
) -> tuple[SummarySection, ...]:
    """Return ordered summary sections for the group."""
    from sqlmodel import select as _sel

    from ..models import Group

    group = session.get(Group, group_id)
    if group is None:
        return ()
    members_rows = session.exec(
        _sel(Member).where(Member.group_id == group_id)
    ).all()
    members = {m.id: m for m in members_rows}
    balances = group_balances(session, group_id=group_id)
    plan = settle_plan(balances)
    return (
        SummarySection(
            title=group.name,
            lines=tuple(f"• {m.display_name}" for m in members_rows),
        ),
        SummarySection(
            title=_t("expense.list.title", lang=lang),
            lines=_expense_lines(
                session,
                group_id=group_id,
                members=members,
                currency=group.currency_symbol,
            ),
        ),
        SummarySection(
            title=_t("settle.title", lang=lang),
            lines=_settlement_lines(
                session,
                group_id=group_id,
                members=members,
                currency=group.currency_symbol,
            ),
        ),
        SummarySection(
            title=_t("balance.title", lang=lang),
            lines=_balance_lines(balances, members, group.currency_symbol, lang),
        ),
        SummarySection(
            title=_t("settle.plan", lang=lang),
            lines=_plan_lines(plan, members, group.currency_symbol),
        ),
    )


def render_summary(sections: Iterable[SummarySection]) -> str:
    """Render sections to a plain-text block."""
    parts: list[str] = []
    for s in sections:
        parts.append(f"# {s.title}")
        if s.lines:
            parts.extend(s.lines)
        else:
            parts.append("—")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


__all__ = ["SummarySection", "build_summary", "render_summary"]
