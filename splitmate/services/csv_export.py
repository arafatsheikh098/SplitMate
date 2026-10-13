"""CSV export for expenses and settlements.

Two formats are produced:

* ``expenses.csv`` — one row per expense with title, amount, date,
  category, note, payer names, and the per-participant split.
* ``settlements.csv`` — one row per settlement with from/to member
  names, amount, method, date and note.

CSV cells are neutralised against formula injection: any cell that
starts with one of ``=``, ``+``, ``-``, ``@`` or a tab is prefixed
with a single quote so spreadsheet apps treat it as a literal
(M7 A2).
"""

from __future__ import annotations

import csv
import io

from sqlmodel import Session, select

from ..models import Expense, Member, Payer, Settlement, SplitPart

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _neutralise(value: object) -> str:
    """Return ``value`` rendered as a CSV-safe string.

    Strings starting with a formula prefix (``=``, ``+``, ``-``, ``@``,
    tab, CR) are prefixed with a single quote so spreadsheet apps
    treat them as literal text.
    """
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in _FORMULA_PREFIXES:
        return "'" + s
    return s


def _member_lookup(session: Session, group_id: int) -> dict[int, str]:
    rows = session.exec(
        select(Member).where(Member.group_id == group_id)
    ).all()
    return {m.id: m.display_name for m in rows}


def expenses_csv(session: Session, *, group_id: int) -> str:
    """Return a CSV string with one row per expense (including deleted)."""
    members = _member_lookup(session, group_id)
    expenses = session.exec(
        select(Expense)
        .where(Expense.group_id == group_id)
        .order_by(Expense.occurred_on.asc(), Expense.id.asc())
    ).all()
    expenses = [e for e in expenses if e.deleted_at is None]
    parts_by_expense: dict[int, list[SplitPart]] = {}
    payers_by_expense: dict[int, list[Payer]] = {}
    for e in expenses:
        parts_by_expense[e.id] = list(
            session.exec(
                select(SplitPart).where(SplitPart.expense_id == e.id)
            ).all()
        )
        payers_by_expense[e.id] = list(
            session.exec(select(Payer).where(Payer.expense_id == e.id)).all()
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "date",
            "title",
            "category",
            "amount",
            "currency",
            "split_method",
            "payer",
            "note",
            "deleted",
            "split_breakdown",
        ]
    )
    for e in expenses:
        payer_names = ", ".join(
            sorted({members.get(p.member_id, str(p.member_id)) for p in payers_by_expense[e.id]})
        )
        breakdown = "; ".join(
            f"{members.get(p.member_id, str(p.member_id))}={p.amount_minor / 100:.2f}"
            for p in sorted(parts_by_expense[e.id], key=lambda p: p.member_id)
        )
        writer.writerow(
            [
                e.occurred_on.isoformat(),
                _neutralise(e.title),
                _neutralise(e.category),
                f"{e.amount_minor / 100:.2f}",
                _neutralise(e.group.currency_symbol if e.group else ""),
                _neutralise(e.split_method),
                _neutralise(payer_names),
                _neutralise(e.note or ""),
                "no",
                _neutralise(breakdown),
            ]
        )
    return buf.getvalue()


def settlements_csv(session: Session, *, group_id: int) -> str:
    members = _member_lookup(session, group_id)
    settlements = session.exec(
        select(Settlement)
        .where(Settlement.group_id == group_id)
        .order_by(Settlement.paid_on.asc(), Settlement.id.asc())
    ).all()
    settlements = [s for s in settlements if s.deleted_at is None]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "date",
            "from",
            "to",
            "amount",
            "currency",
            "method",
            "note",
        ]
    )
    for s in settlements:
        writer.writerow(
            [
                s.paid_on.isoformat(),
                _neutralise(members.get(s.from_member_id, str(s.from_member_id))),
                _neutralise(members.get(s.to_member_id, str(s.to_member_id))),
                f"{s.amount_minor / 100:.2f}",
                _neutralise(s.group.currency_symbol if s.group else ""),
                _neutralise(s.method),
                _neutralise(s.note or ""),
            ]
        )
    return buf.getvalue()


def csv_response_body(csv_text: str) -> bytes:
    """Encode ``csv_text`` as UTF-8 with a BOM for Excel-friendly viewing."""
    return "\ufeff".encode() + csv_text.encode()


__all__ = [
    "csv_response_body",
    "expenses_csv",
    "settlements_csv",
]
