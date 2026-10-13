"""CSV export routes (M7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlmodel import Session

from ..db import get_session
from ..models import Group, Member
from ..services.csv_export import (
    csv_response_body,
    expenses_csv,
    settlements_csv,
)
from .deps import get_lang, require_member
from .share import _safe_filename

router = APIRouter()


def _csv_response(
    *,
    group: Group,
    csv_text: str,
    filename: str,
) -> Response:
    return Response(
        content=csv_response_body(csv_text),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{_safe_filename(group.name)}-{filename}"'
            )
        },
    )


@router.get("/groups/{group_id}/expenses.csv")
def export_expenses(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> Response:
    _ = get_lang(request)
    group, _ = group_member
    return _csv_response(
        group=group,
        csv_text=expenses_csv(session, group_id=group_id),
        filename="expenses.csv",
    )


@router.get("/groups/{group_id}/settlements.csv")
def export_settlements(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> Response:
    _ = get_lang(request)
    group, _ = group_member
    return _csv_response(
        group=group,
        csv_text=settlements_csv(session, group_id=group_id),
        filename="settlements.csv",
    )


__all__ = ["router"]
