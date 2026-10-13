"""Shared dependencies used by every group-scoped route."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Path, Request, status
from sqlmodel import Session

from .. import services
from ..db import get_session
from ..models import Group, Member
from ..security import current_member_ids


def get_lang(request: Request) -> str:
    cookie = request.cookies.get("lang")
    if cookie in ("en", "bn"):
        return cookie
    from ..config import get_settings

    return get_settings().default_language


def require_member(
    request: Request,
    group_id: int = Path(..., alias="group_id"),
    session: Session = Depends(get_session),
) -> tuple[Group, Member]:
    """Verify the request's session belongs to a member of the URL's group.

    Both the URL ``group_id`` and the session's group must match.  A
    member of group A trying to reach a URL like ``/groups/B/...`` gets
    404 because they are not a member of group B.
    """
    ids = current_member_ids(request)
    if ids is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no session")
    session_group_id, member_id = ids
    if session_group_id != group_id:
        # The session is for a different group; pretend the resource
        # does not exist.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    member = services.get_member_or_none(session, group_id, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    group = services.get_group_or_404(session, group_id)
    return group, member


def require_admin(
    group_member: tuple[Group, Member] = Depends(require_member),
) -> tuple[Group, Member]:
    group, member = group_member
    if not member.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin required")
    return group, member


__all__ = ["get_lang", "require_admin", "require_member"]
