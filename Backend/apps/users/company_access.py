from __future__ import annotations

from typing import Iterable

from django.db import transaction
from django.db.models import QuerySet
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as APIValidationError

from .models import UserCompanyAccess


def is_unrestricted_user(user) -> bool:
    """
    Determine whether the user has global company access.

    In this project, admin users are unrestricted at the
    company-access layer. They are still subject to the
    existing role/application permissions where applicable.
    """

    if not user or not user.is_authenticated:
        return False

    is_admin_method = getattr(user, "is_admin", None)

    if callable(is_admin_method):
        return bool(is_admin_method())

    return bool(getattr(user, "is_superuser", False))


def get_accessible_company_ids(user) -> list[int] | None:
    """
    Return the company IDs the user is allowed to access.

    Returns:
        None
            User has unrestricted/global company access.

        []
            Authenticated user has no company access.

        [1, 2, 3]
            User has access to these companies.
    """

    if not user or not user.is_authenticated:
        return []

    if is_unrestricted_user(user):
        return None

    return list(
        UserCompanyAccess.objects.filter(
            user=user,
            status=1,
            company__is_active=True,
        ).values_list(
            "company_id",
            flat=True,
        )
    )


def has_company_access(user, company_or_id) -> bool:
    """
    Backwards-compatible helper used by existing code.

    Accepts either:
        - Company instance
        - company ID
    """

    if not user or not user.is_authenticated:
        return False

    if is_unrestricted_user(user):
        return True

    company_id = getattr(
        company_or_id,
        "pk",
        company_or_id,
    )

    if company_id is None:
        return False

    return UserCompanyAccess.objects.filter(
        user=user,
        company_id=company_id,
        status=1,
        company__is_active=True,
    ).exists()


def user_can_access_company(user, company_or_id) -> bool:
    """
    Preferred descriptive alias for has_company_access().
    """

    return has_company_access(
        user,
        company_or_id,
    )


def require_company_access(user, company_or_id) -> None:
    """
    Raise HTTP 403 if the user cannot access the company.
    """

    if not has_company_access(
        user,
        company_or_id,
    ):
        raise PermissionDenied(
            "You do not have access to this company."
        )


def require_company_id_access(
    user,
    company_id,
) -> None:
    """
    Validate access using a company ID.
    """

    require_company_access(
        user,
        company_id,
    )


def filter_company_queryset(
    queryset: QuerySet,
    user,
    company_field: str = "company_id",
) -> QuerySet:
    """
    Restrict a queryset to companies accessible
    by the authenticated user.

    Example:

        filter_company_queryset(
            DailyPrice.objects.all(),
            request.user,
        )

    For Company.objects querysets use:

        filter_company_queryset(
            Company.objects.all(),
            request.user,
            "id",
        )
    """

    company_ids = get_accessible_company_ids(user)

    # None means unrestricted/global access.
    if company_ids is None:
        return queryset

    # Empty list intentionally returns no records.
    return queryset.filter(
        **{
            f"{company_field}__in": company_ids,
        }
    )


def filter_queryset_by_user_companies(
    queryset: QuerySet,
    user,
    company_field: str = "company_id",
) -> QuerySet:
    """
    Descriptive alias for filter_company_queryset().
    """

    return filter_company_queryset(
        queryset,
        user,
        company_field,
    )


def accessible_company_queryset(
    company_queryset: QuerySet,
    user,
) -> QuerySet:
    """
    Restrict a Company queryset to companies accessible
    by the authenticated user.
    """

    company_ids = get_accessible_company_ids(user)

    if company_ids is None:
        return company_queryset.filter(
            is_active=True
        )

    return company_queryset.filter(
        pk__in=company_ids,
        is_active=True,
    )


def require_permission(
    user,
    permission_code: str,
) -> None:
    """
    Reuse the project's existing RBAC permission system.
    """

    if not user or not user.is_authenticated:
        raise PermissionDenied(
            "Authentication required."
        )

    if not user.has_app_permission(
        permission_code
    ):
        raise PermissionDenied(
            "You do not have the required permission."
        )


def require_permission_and_company(
    user,
    permission_code: str,
    company_or_id,
) -> None:
    """
    Central authorization rule:

        ROLE PERMISSION
        AND
        COMPANY ACCESS
    """

    require_permission(
        user,
        permission_code,
    )

    require_company_access(
        user,
        company_or_id,
    )


def validate_company_ids(
    user,
    company_ids: Iterable[int],
) -> list[int]:
    """
    Validate multiple company IDs against the user's
    company access.

    Used by:
        - exports
        - comparisons
        - bulk operations
        - reports
    """

    normalized_ids = []

    for company_id in company_ids:
        try:
            normalized_ids.append(
                int(company_id)
            )
        except (
            TypeError,
            ValueError,
        ):
            raise PermissionDenied(
                "Invalid company ID."
            )

    normalized_ids = list(
        dict.fromkeys(
            normalized_ids
        )
    )

    accessible_ids = get_accessible_company_ids(
        user
    )

    # Admin/global user.
    if accessible_ids is None:
        return normalized_ids

    accessible_set = set(
        accessible_ids
    )

    unauthorized = [
        company_id
        for company_id in normalized_ids
        if company_id not in accessible_set
    ]

    if unauthorized:
        raise PermissionDenied(
            "You do not have access to one or more requested companies."
        )

    return normalized_ids


@transaction.atomic
def set_company_access(
    user,
    company_access,
):
    """
    Replace the complete company-access configuration
    for one user.

    Example:

        [
            {
                "company_id": 1,
                "status": 1,
            },
            {
                "company_id": 2,
                "status": 0,
            },
        ]
    """

    submitted_company_ids = set()
    normalized_access = []

    for item in company_access:
        company_id = int(
            item["company_id"]
        )

        status = int(
            item["status"]
        )

        if status not in (0, 1):
            raise PermissionDenied(
                "Company access status must be 0 or 1."
            )

        submitted_company_ids.add(
            company_id
        )

        normalized_access.append((company_id, status))

    from apps.companies.models import Company
    existing_company_ids = set(
        Company.objects.filter(
            pk__in=submitted_company_ids,
            is_active=True,
        ).values_list("pk", flat=True)
    )
    if existing_company_ids != submitted_company_ids:
        raise APIValidationError(
            {"company_access": "Every company must exist and be active."}
        )

    for company_id, status in normalized_access:
        UserCompanyAccess.objects.update_or_create(
            user=user,
            company_id=company_id,
            defaults={
                "status": status,
            },
        )

    UserCompanyAccess.objects.filter(
        user=user
    ).exclude(
        company_id__in=submitted_company_ids
    ).delete()
