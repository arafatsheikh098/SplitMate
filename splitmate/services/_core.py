"""Service layer: business logic, transactions, and authorisation rules.

Routes stay thin and call into these functions.  Tests that need to
exercise behaviour without HTTP also import from here.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlmodel import Session, select

from ..config import get_settings
from ..models import (
    Activity,
    ActivityKind,
    Expense,
    Group,
    Member,
    Payer,
    RejoinCode,
    Settlement,
    SplitPart,
)
from ..security import (
    RateLimiter,
    generate_token,
    hash_token,
    safe_log,
)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ServiceError(Exception):
    """Raised by service functions when input is invalid or a rule fails."""


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail=message)


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)


def _not_found(message: str = "Not found") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


def _forbidden(message: str = "Forbidden") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail=message)


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"\s+")


def normalise_name(name: str) -> str:
    """Lowercase and collapse whitespace for uniqueness comparison."""
    return _NAME_RE.sub(" ", name.strip()).lower()


def validate_name(name: str) -> str:
    if not name or not name.strip():
        raise ServiceError("name required")
    cleaned = name.strip()
    if len(cleaned) > 60:
        raise ServiceError("name too long")
    return cleaned


# ---------------------------------------------------------------------------
# Group creation
# ---------------------------------------------------------------------------


def create_group(
    session: Session,
    *,
    name: str,
    currency_symbol: str = "৳",
    admin_name: str,
) -> tuple[Group, Member]:
    """Create a group, a hashed invite token, and the creator as admin member.

    The plaintext invite token is returned in the result so the caller can
    hand it to the admin — it is the only time the plaintext is exposed.
    """
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        raise ServiceError("group name required")
    if len(cleaned_name) > 100:
        raise ServiceError("group name too long")

    cleaned_currency = (currency_symbol or "৳").strip()[:8] or "৳"
    admin_display = validate_name(admin_name)
    admin_ci = normalise_name(admin_display)

    token = generate_token()
    group = Group(
        name=cleaned_name,
        currency_symbol=cleaned_currency,
        invite_token_hash=hash_token(token),
    )
    session.add(group)
    session.flush()

    member = Member(
        group_id=group.id,
        display_name=admin_display,
        name_ci=admin_ci,
        is_admin=True,
        is_virtual=False,
    )
    session.add(member)
    session.flush()
    session.add(
        Activity(
            group_id=group.id,
            actor_id=member.id,
            kind=ActivityKind.MEMBER_ADDED,
            summary=f"member {admin_display!r} added (admin)",
        )
    )
    session.commit()
    session.refresh(group)
    session.refresh(member)
    return group, member, token


# ---------------------------------------------------------------------------
# Invite tokens (rotate / revoke)
# ---------------------------------------------------------------------------


def rotate_invite(session: Session, *, group: Group) -> str:
    """Replace the group's invite token.  Returns the new plaintext."""
    token = generate_token()
    group.invite_token_hash = hash_token(token)
    session.add(
        Activity(
            group_id=group.id,
            actor_id=None,
            kind=ActivityKind.INVITE_ROTATED,
            summary="invite link rotated",
        )
    )
    session.add(group)
    session.commit()
    return token


def revoke_invite(session: Session, *, group: Group) -> None:
    """Invalidate the current invite token (no replacement)."""
    group.invite_token_hash = hash_token("revoked-" + generate_token())
    session.add(
        Activity(
            group_id=group.id,
            actor_id=None,
            kind=ActivityKind.INVITE_REVOKED,
            summary="invite link revoked",
        )
    )
    session.add(group)
    session.commit()


def find_group_by_invite(session: Session, token: str) -> Group | None:
    if not token:
        return None
    digest = hash_token(token)
    group = session.exec(select(Group).where(Group.invite_token_hash == digest)).first()
    return group


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


def get_group_or_404(session: Session, group_id: int) -> Group:
    group = session.get(Group, group_id)
    if group is None:
        raise _not_found()
    return group


def get_member_or_none(session: Session, group_id: int, member_id: int) -> Member | None:
    return session.exec(
        select(Member).where(Member.id == member_id, Member.group_id == group_id)
    ).first()


def get_member_or_404(session: Session, group_id: int, member_id: int) -> Member:
    m = get_member_or_none(session, group_id, member_id)
    if m is None:
        raise _not_found()
    return m


def count_members(session: Session, group_id: int) -> int:
    return len(session.exec(select(Member).where(Member.group_id == group_id)).all())


def join_group(
    session: Session,
    *,
    group: Group,
    display_name: str,
) -> Member:
    """Join ``group`` with a fresh display name (no re-link code involved)."""
    settings = get_settings()
    if count_members(session, group.id) >= settings.max_members_per_group:
        raise ServiceError(f"max members ({settings.max_members_per_group}) reached")
    cleaned = validate_name(display_name)
    ci = normalise_name(cleaned)
    existing = session.exec(
        select(Member).where(Member.group_id == group.id, Member.name_ci == ci)
    ).first()
    if existing is not None:
        raise ServiceError("name taken")
    member = Member(
        group_id=group.id,
        display_name=cleaned,
        name_ci=ci,
        is_admin=False,
        is_virtual=False,
    )
    session.add(member)
    session.flush()
    session.add(
        Activity(
            group_id=group.id,
            actor_id=member.id,
            kind=ActivityKind.MEMBER_ADDED,
            summary=f"member {cleaned!r} joined",
        )
    )
    session.commit()
    session.refresh(member)
    return member


def add_virtual_member(
    session: Session,
    *,
    group: Group,
    display_name: str,
    actor_id: int | None = None,
) -> Member:
    settings = get_settings()
    if count_members(session, group.id) >= settings.max_members_per_group:
        raise ServiceError(f"max members ({settings.max_members_per_group}) reached")
    cleaned = validate_name(display_name)
    ci = normalise_name(cleaned)
    existing = session.exec(
        select(Member).where(Member.group_id == group.id, Member.name_ci == ci)
    ).first()
    if existing is not None:
        raise ServiceError("name taken")
    member = Member(
        group_id=group.id,
        display_name=cleaned,
        name_ci=ci,
        is_admin=False,
        is_virtual=True,
    )
    session.add(member)
    session.flush()
    session.add(
        Activity(
            group_id=group.id,
            actor_id=actor_id,
            kind=ActivityKind.MEMBER_ADDED,
            summary=f"virtual member {cleaned!r} added",
        )
    )
    session.commit()
    session.refresh(member)
    return member


def claim_virtual_member(
    session: Session,
    *,
    group: Group,
    member_id: int,
) -> Member:
    member = get_member_or_404(session, group.id, member_id)
    if not member.is_virtual:
        raise ServiceError("member is not virtual")
    member.is_virtual = False
    session.add(member)
    session.add(
        Activity(
            group_id=group.id,
            actor_id=member.id,
            kind=ActivityKind.MEMBER_CLAIMED,
            summary=f"member {member.display_name!r} claimed",
        )
    )
    session.commit()
    session.refresh(member)
    return member


def archive_member(
    session: Session,
    *,
    group: Group,
    member_id: int,
) -> Member:
    member = get_member_or_404(session, group.id, member_id)
    balance = compute_member_balance(session, group_id=group.id, member_id=member.id)
    if balance != 0:
        raise ServiceError("non-zero balance")
    member.archived = True
    session.add(member)
    session.add(
        Activity(
            group_id=group.id,
            actor_id=None,
            kind=ActivityKind.MEMBER_ARCHIVED,
            summary=f"member {member.display_name!r} archived",
        )
    )
    session.commit()
    session.refresh(member)
    return member


def restore_member(
    session: Session,
    *,
    group: Group,
    member_id: int,
) -> Member:
    member = get_member_or_404(session, group.id, member_id)
    member.archived = False
    session.add(member)
    session.add(
        Activity(
            group_id=group.id,
            actor_id=None,
            kind=ActivityKind.MEMBER_RESTORED,
            summary=f"member {member.display_name!r} restored",
        )
    )
    session.commit()
    session.refresh(member)
    return member


def promote(session: Session, *, group: Group, member_id: int) -> Member:
    member = get_member_or_404(session, group.id, member_id)
    if member.is_admin:
        return member
    member.is_admin = True
    session.add(member)
    session.add(
        Activity(
            group_id=group.id,
            actor_id=None,
            kind=ActivityKind.ADMIN_PROMOTED,
            summary=f"{member.display_name!r} promoted to admin",
        )
    )
    session.commit()
    session.refresh(member)
    return member


def demote(session: Session, *, group: Group, member_id: int) -> Member:
    member = get_member_or_404(session, group.id, member_id)
    if not member.is_admin:
        return member
    admins = session.exec(
        select(Member).where(Member.group_id == group.id, Member.is_admin == True)  # noqa: E712
    ).all()
    if len(admins) <= 1:
        raise ServiceError("last admin")
    member.is_admin = False
    session.add(member)
    session.add(
        Activity(
            group_id=group.id,
            actor_id=None,
            kind=ActivityKind.ADMIN_DEMOTED,
            summary=f"{member.display_name!r} demoted",
        )
    )
    session.commit()
    session.refresh(member)
    return member


# ---------------------------------------------------------------------------
# Re-link codes
# ---------------------------------------------------------------------------


_relink_limiter = RateLimiter(
    max_hits=get_settings().relink_max_attempts,
    window_seconds=get_settings().relink_window_seconds,
)


def relink_limiter() -> RateLimiter:
    return _relink_limiter


def issue_relink_code(
    session: Session,
    *,
    group: Group,
    member: Member,
) -> str:
    """Return a new one-time re-link code.  Only the plaintext is returned."""
    settings = get_settings()
    code = generate_token()
    now = datetime.now(UTC)
    rec = RejoinCode(
        group_id=group.id,
        member_id=member.id,
        code_hash=hash_token(code),
        issued_at=now,
        expires_at=now + timedelta(seconds=settings.relink_code_ttl_seconds),
    )
    session.add(rec)
    session.add(
        Activity(
            group_id=group.id,
            actor_id=member.id,
            kind=ActivityKind.RELINK_ISSUED,
            summary="re-link code issued",
        )
    )
    session.commit()
    safe_log("rejoin_code_issued", group_id=group.id, member_id=member.id, code_id=rec.id)
    return code


def consume_relink_code(
    session: Session,
    *,
    group: Group,
    code: str,
    ip: str,
) -> Member:
    """Validate a re-link code, mark it used, and return the matching member.

    Rate-limited to 5 attempts per 15 minutes per (group, ip).
    """
    settings = get_settings()  # noqa: F841 — kept for future use
    if not code:
        raise ServiceError("code required")
    key = ("relink", group.id, ip)
    if not _relink_limiter.hit(key):
        safe_log("relink_rate_limited", group_id=group.id, ip=ip)
        raise ServiceError("too many attempts")
    digest = hash_token(code)
    rec = session.exec(
        select(RejoinCode)
        .where(RejoinCode.group_id == group.id, RejoinCode.code_hash == digest)
        .order_by(RejoinCode.id.desc())
    ).first()
    now = datetime.now(UTC)
    # Some dialects (notably SQLite) drop tz info on the way back; compare
    # in a tz-naive way to be portable.
    expires_at = rec.expires_at if rec else None
    if rec is not None and expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if rec is None or rec.used_at is not None or expires_at < now:
        safe_log("relink_invalid", group_id=group.id, ip=ip)
        raise ServiceError("invalid code")
    member = get_member_or_404(session, group.id, rec.member_id)
    rec.used_at = now
    session.add(rec)
    session.commit()
    safe_log("relink_used", group_id=group.id, member_id=member.id)
    return member


# ---------------------------------------------------------------------------
# Balances (lightweight — full balance/settle in M5)
# ---------------------------------------------------------------------------


def compute_member_balance(session: Session, *, group_id: int, member_id: int) -> int:
    """Net balance in minor units: paid − owed (expenses) + received − sent (settlements).

    Returns an integer that can be negative (the member owes) or positive
    (the member is owed).  Excludes soft-deleted expenses / settlements.
    """
    # Payer side
    paid_rows = session.exec(
        select(Payer.amount_minor)
        .join(Expense, Expense.id == Payer.expense_id)
        .where(
            Expense.group_id == group_id,
            Expense.deleted_at.is_(None),
            Payer.member_id == member_id,
        )
    ).all()
    paid = sum(paid_rows)

    # Owe side (split parts)
    owed_rows = session.exec(
        select(SplitPart.amount_minor)
        .join(Expense, Expense.id == SplitPart.expense_id)
        .where(
            Expense.group_id == group_id,
            Expense.deleted_at.is_(None),
            SplitPart.member_id == member_id,
        )
    ).all()
    owed = sum(owed_rows)

    # Settlements — sent and received
    sent = sum(
        r
        for r in session.exec(
            select(Settlement.amount_minor).where(
                Settlement.group_id == group_id,
                Settlement.deleted_at.is_(None),
                Settlement.from_member_id == member_id,
            )
        ).all()
    )
    received = sum(
        r
        for r in session.exec(
            select(Settlement.amount_minor).where(
                Settlement.group_id == group_id,
                Settlement.deleted_at.is_(None),
                Settlement.to_member_id == member_id,
            )
        ).all()
    )
    return int(paid - owed - sent + received)


__all__ = [
    "ServiceError",
    "add_virtual_member",
    "archive_member",
    "claim_virtual_member",
    "compute_member_balance",
    "consume_relink_code",
    "create_group",
    "demote",
    "find_group_by_invite",
    "get_group_or_404",
    "get_member_or_404",
    "get_member_or_none",
    "issue_relink_code",
    "join_group",
    "normalise_name",
    "promote",
    "relink_limiter",
    "restore_member",
    "revoke_invite",
    "rotate_invite",
    "validate_name",
]
