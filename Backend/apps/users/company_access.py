"""
Company Access helpers.

This module is the single source of truth for the company-access check.

Architecture:
    Existing Role + Permission  →  WHAT can the user do?
    UserCompanyAccess           →  FOR WHICH COMPANY can they do it?

    Final access = Existing Permission AND Company Access status == 1

Admins bypass company-access restrictions because they manage all
companies.  This mirrors the way admins bypass permission checks
throughout the rest of the system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # avoid circular imports in type-checker only


def has_company_access(user, company_id: int) -> bool:
    """
    Return True when the user is permitted to perform company-specific
    operations on the given company.

    Rules:
    - Admin users always have access to every company.
    - Non-admin users need a UserCompanyAccess row with status = 1.
    - Non-admin users WITHOUT any row for a company are denied (default-deny).

    This function does NOT check role/permission keys — callers are
    responsible for checking both:

        user.has_app_permission("view_market_data")  AND
        has_company_access(user, company_id)
    """
    # Admins manage all companies — no access restriction.
    if user.is_admin():
        return True

    # Lazy import to avoid circular dependency at module level.
    from .models import UserCompanyAccess

    return UserCompanyAccess.objects.filter(
        user=user,
        company_id=company_id,
        status=1,
    ).exists()


def get_accessible_company_ids(user) -> list[int]:
    """
    Return the list of company IDs this user can access.

    Admins get an empty list with a sentinel so callers know they should
    NOT filter — use `user.is_admin()` to distinguish.

    For non-admins, returns IDs of all companies where status = 1.
    """
    if user.is_admin():
        # Signal: no filtering needed for admins.
        return None  # type: ignore[return-value]  # callers check is_admin() first

    from .models import UserCompanyAccess

    return list(
        UserCompanyAccess.objects.filter(
            user=user,
            status=1,
        ).values_list("company_id", flat=True)
    )


def sync_company_access(user, access_list: list[dict]) -> None:
    """
    Idempotently set company access for a user from a list of dicts:

        [{"company_id": 1, "status": 1}, {"company_id": 2, "status": 0}, ...]

    - Creates rows that don't exist.
    - Updates rows whose status changed.
    - Deletes rows for companies no longer in the list (optional: see note).

    NOTE: rows for companies NOT in `access_list` are LEFT UNCHANGED.
    This makes partial updates safe — sending only changed companies
    does not accidentally revoke access to unmentioned companies.
    Use `set_company_access` to do a full replacement.
    """
    from .models import UserCompanyAccess
    from apps.companies.models import Company

    for item in access_list:
        company_id = item.get("company_id")
        status_val = item.get("status", 0)

        if status_val not in (0, 1):
            continue  # silently skip invalid; serializer should have caught this

        if not Company.objects.filter(pk=company_id, is_active=True).exists():
            continue  # skip non-existent companies

        UserCompanyAccess.objects.update_or_create(
            user=user,
            company_id=company_id,
            defaults={"status": status_val},
        )


def set_company_access(user, access_list: list[dict]) -> None:
    """
    Full replacement: remove all existing access rows for the user, then
    create fresh ones from access_list.

    Used when the admin submits the complete company-access grid.

    access_list format: [{"company_id": 1, "status": 1}, ...]
    """
    from .models import UserCompanyAccess

    # Delete all existing rows for this user.
    UserCompanyAccess.objects.filter(user=user).delete()

    # Re-create.
    sync_company_access(user, access_list)
