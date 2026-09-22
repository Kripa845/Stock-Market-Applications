from __future__ import annotations

from django.db import transaction


def has_company_access(user, company_id: int) -> bool:
    """
    Check whether a user has access to a specific company.

    Admins can access every company.
    Non-admin users need an active UserCompanyAccess record.
    """

    if user.is_admin():
        return True

    from .models import UserCompanyAccess

    return UserCompanyAccess.objects.filter(
        user=user,
        company_id=company_id,
        status=1,
    ).exists()


def get_accessible_company_ids(user) -> list[int] | None:
    """
    Return the company IDs accessible to the user.

    Admin:
        None = no company filtering required.

    Non-admin:
        List of active company IDs.
    """

    if user.is_admin():
        return None

    from .models import UserCompanyAccess

    return list(
        UserCompanyAccess.objects.filter(
            user=user,
            status=1,
        ).values_list(
            "company_id",
            flat=True,
        )
    )


def sync_company_access(
    user,
    access_list: list[dict],
) -> None:
    """
    Create or update company access records.

    Example:
        [
            {"company_id": 1, "status": 1},
            {"company_id": 2, "status": 1},
            {"company_id": 3, "status": 0},
        ]
    """

    from .models import UserCompanyAccess
    from apps.companies.models import Company

    for item in access_list:
        company_id = item.get("company_id")
        status_val = item.get("status", 0)

        if status_val not in (0, 1):
            continue

        if not Company.objects.filter(
            pk=company_id,
            is_active=True,
        ).exists():
            continue

        UserCompanyAccess.objects.update_or_create(
            user=user,
            company_id=company_id,
            defaults={
                "status": status_val,
            },
        )


@transaction.atomic
def set_company_access(
    user,
    access_list: list[dict],
) -> None:
    """
    Completely replace a user's company access.

    Existing records are deleted first,
    then the submitted access list is created.
    """

    from .models import UserCompanyAccess

    UserCompanyAccess.objects.filter(
        user=user
    ).delete()

    sync_company_access(
        user,
        access_list,
    )