"""Service layer: business logic, transactions, authorisation rules.

Routes stay thin and call into these functions.  Tests that need to
exercise behaviour without HTTP also import from here.

The package exposes two entry points:

* The flat ``splitmate.services`` API for backwards compatibility
  (re-exports from ``_core``).
* The per-domain submodules (``expenses``, future ``balances``,
  ``settlements``, ...) imported explicitly.
"""

from ._core import (
    ServiceError,
    add_virtual_member,
    archive_member,
    claim_virtual_member,
    compute_member_balance,
    consume_relink_code,
    create_group,
    demote,
    find_group_by_invite,
    get_group_or_404,
    get_member_or_404,
    get_member_or_none,
    issue_relink_code,
    join_group,
    normalise_name,
    promote,
    relink_limiter,
    restore_member,
    revoke_invite,
    rotate_invite,
    validate_name,
)

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
