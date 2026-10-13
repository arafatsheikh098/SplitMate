"""Expense routes: list, new, create, soft-delete, restore."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from .. import services as main_services
from ..db import get_session
from ..i18n import t
from ..models import Category, Expense, Group, Member, Payer, SplitMethod, SplitPart
from ..money import format_amount
from ..services.expenses import (
    create_expense,
    list_expenses,
    restore_expense,
    soft_delete_expense,
)
from ..templates import render
from .deps import get_lang, require_admin, require_member

router = APIRouter()

ServiceError = main_services.ServiceError


def _html(content: str, *, lang: str, title: str = "", status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        render(
            "base.html.j2",
            {"lang": lang},
            block_title=title,
            content=content,
        ),
        status_code=status_code,
    )


@router.get("/groups/{group_id}/expenses")
def expenses_index(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    group, member = group_member
    expenses = list_expenses(session, group_id=group_id)
    members = session.exec(select(Member).where(Member.group_id == group_id)).all()
    body = render(
        "expenses/list.html.j2",
        {
            "lang": lang,
            "group": group,
            "current_member": member,
            "expenses": expenses,
            "members": members,
            "format_amount": format_amount,
            "t": t,
        },
    )
    return _html(body, lang=lang, title=t("expense.list.title", lang=lang))


@router.get("/groups/{group_id}/expenses/new")
def expenses_new(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    group, member = group_member
    members = session.exec(
        select(Member).where(
            Member.group_id == group_id, Member.archived == False  # noqa: E712
        )
    ).all()
    body = render(
        "expenses/new.html.j2",
        {
            "lang": lang,
            "group": group,
            "current_member": member,
            "members": members,
            "categories": [c.value for c in Category],
            "methods": [m.value for m in SplitMethod],
            "today": date.today().isoformat(),
            "errors": {},
            "values": {},
            "t": t,
        },
    )
    return _html(body, lang=lang, title=t("expense.create.title", lang=lang))


@router.post("/groups/{group_id}/expenses/new")
def expenses_create(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    title: str = Form(""),
    amount: str = Form(""),
    date_value: str = Form(""),  # renamed to avoid shadowing builtin
    category: str = Form(Category.OTHER.value),
    note: str = Form(""),
    split_method: str = Form(SplitMethod.EQUAL.value),
    participants: list[str] = Form([]),
    payer_id: str = Form(""),
    payer_amount: str = Form(""),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    group, member = group_member
    data: dict = {
        "title": title,
        "amount": amount,
        "date": date_value,
        "category": category,
        "note": note,
        "split_method": split_method,
        "participants": participants,
    }
    if payer_id and payer_amount:
        data["payer_id"] = payer_id
        data["payer_amount"] = payer_amount
    try:
        create_expense(
            session, group_id=group_id, creator_id=member.id, data=data
        )
    except ServiceError as exc:
        members = session.exec(
            select(Member).where(
                Member.group_id == group_id, Member.archived == False  # noqa: E712
            )
        ).all()
        body = render(
            "expenses/new.html.j2",
            {
                "lang": lang,
                "group": group,
                "current_member": member,
                "members": members,
                "categories": [c.value for c in Category],
                "methods": [m.value for m in SplitMethod],
                "today": date.today().isoformat(),
                "errors": {"form": str(exc)},
                "values": {
                    "title": title,
                    "amount": amount,
                    "date": date_value,
                    "category": category,
                    "note": note,
                    "split_method": split_method,
                    "participants": participants,
                },
                "t": t,
            },
        )
        return _html(
            body,
            lang=lang,
            status_code=status.HTTP_400_BAD_REQUEST,
            title=t("expense.create.title", lang=lang),
        )
    return RedirectResponse(f"/groups/{group_id}/expenses", status_code=303)


@router.post("/groups/{group_id}/expenses/{expense_id}/delete")
def expense_delete(
    group_id: int,
    expense_id: int,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> RedirectResponse:
    group, member = group_member
    expense = session.get(Expense, expense_id)
    if expense is None or expense.group_id != group_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if expense.creator_id != member.id and not member.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    soft_delete_expense(
        session, group_id=group_id, expense_id=expense_id, actor_id=member.id
    )
    return RedirectResponse(f"/groups/{group_id}/expenses", status_code=303)


@router.post("/groups/{group_id}/expenses/{expense_id}/restore")
def expense_restore(
    group_id: int,
    expense_id: int,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_admin),
) -> RedirectResponse:
    group, member = group_member
    restore_expense(
        session, group_id=group_id, expense_id=expense_id, actor_id=member.id
    )
    return RedirectResponse(f"/groups/{group_id}/expenses", status_code=303)


@router.get("/groups/{group_id}/expenses/{expense_id}")
def expense_detail(
    group_id: int,
    expense_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    group, member = group_member
    expense = session.get(Expense, expense_id)
    if expense is None or expense.group_id != group_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    payers = session.exec(select(Payer).where(Payer.expense_id == expense_id)).all()
    parts = session.exec(
        select(SplitPart).where(SplitPart.expense_id == expense_id)
    ).all()
    members = session.exec(select(Member).where(Member.group_id == group_id)).all()
    by_id = {m.id: m for m in members}
    body = render(
        "expenses/detail.html.j2",
        {
            "lang": lang,
            "group": group,
            "current_member": member,
            "expense": expense,
            "payers": payers,
            "parts": parts,
            "members_by_id": by_id,
            "format_amount": format_amount,
            "t": t,
        },
    )
    return _html(body, lang=lang, title=expense.title)


__all__ = ["router"]
