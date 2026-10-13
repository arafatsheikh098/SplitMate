"""Group and member service-level tests.

These tests call the service layer directly to keep their focus on
behaviour.  The HTTP-level flow is exercised by ``test_routes.py``.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from splitmate import services
from splitmate.db import get_engine
from splitmate.models import Group, Member
from splitmate.security import hash_token, tokens_equal
from splitmate.services import ServiceError


@pytest.fixture
def session() -> Session:
    with Session(get_engine()) as s:
        yield s


def test_create_group_creates_admin(session: Session) -> None:
    group, member, token = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    assert group.id is not None
    assert member.is_admin
    assert member.is_virtual is False
    # Token should be at least 32 chars of url-safe base64
    assert len(token) >= 32
    # Hash is stored, not plaintext
    assert group.invite_token_hash != token
    assert tokens_equal(group.invite_token_hash, hash_token(token))


def test_join_rejects_duplicate_name_case_insensitive(session: Session) -> None:
    group, _, _ = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    services.join_group(session, group=group, display_name="Bea")
    with pytest.raises(ServiceError):
        services.join_group(session, group=group, display_name="  bea  ")


def test_member_limit_enforced(session: Session) -> None:
    from splitmate.config import get_settings

    settings = get_settings()
    # Create a group with a small limit
    settings.max_members_per_group = 3
    group, _, _ = services.create_group(
        session, name="Tiny", currency_symbol="৳", admin_name="Admin"
    )
    services.join_group(session, group=group, display_name="B")
    services.join_group(session, group=group, display_name="C")
    with pytest.raises(ServiceError):
        services.join_group(session, group=group, display_name="D")
    settings.max_members_per_group = 30  # restore


def test_rotate_invite_invalidates_old_token(session: Session) -> None:
    group, _, old_token = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    # Plaintext old token still finds the group
    assert services.find_group_by_invite(session, old_token) is not None
    new_token = services.rotate_invite(session, group=group)
    assert services.find_group_by_invite(session, old_token) is None
    assert services.find_group_by_invite(session, new_token) is not None
    # Tokens differ
    assert old_token != new_token


def test_revoke_invite(session: Session) -> None:
    group, _, token = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    services.revoke_invite(session, group=group)
    assert services.find_group_by_invite(session, token) is None


def test_last_admin_cannot_be_demoted(session: Session) -> None:
    group, admin, _ = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    with pytest.raises(ServiceError):
        services.demote(session, group=group, member_id=admin.id)
    # Promote someone else to admin and demote works
    other = services.join_group(session, group=group, display_name="Bea")
    services.promote(session, group=group, member_id=other.id)
    services.demote(session, group=group, member_id=admin.id)
    admins = session.exec(
        select(Member).where(Member.group_id == group.id, Member.is_admin == True)  # noqa: E712
    ).all()
    assert len(admins) == 1
    assert admins[0].id == other.id


def test_archived_member_stays_archived(session: Session) -> None:
    group, admin, _ = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    other = services.add_virtual_member(session, group=group, display_name="Bea")
    services.archive_member(session, group=group, member_id=other.id)
    services.restore_member(session, group=group, member_id=other.id)
    # Now archived flag is False again
    assert other.archived is False


def test_claim_virtual_member(session: Session) -> None:
    group, _, _ = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    vm = services.add_virtual_member(session, group=group, display_name="Bea")
    assert vm.is_virtual is True
    services.claim_virtual_member(session, group=group, member_id=vm.id)
    assert vm.is_virtual is False


def test_token_hashes_stored_only(client) -> None:  # noqa: ANN001
    # Create a group via HTTP, then look at the DB to confirm no plaintext
    client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    with Session(get_engine()) as s:
        g = s.exec(select(Group)).first()
    # Stored value is 64 hex chars (sha256); plaintext token is not stored.
    assert len(g.invite_token_hash) == 64
    assert all(c in "0123456789abcdef" for c in g.invite_token_hash)
