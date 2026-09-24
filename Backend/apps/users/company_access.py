# Backend/apps/users/company_access.py

from __future__ import annotations

from typing import Iterable

from django.db.models import QuerySet
from rest_framework.exceptions import PermissionDenied


def is_unrestricted_user(user) -> bool:
    """
    Returns True when the user is supposed to have global company access.

    IMPORTANT:
    Do not replace this with:
        user.role == "admin"

    Your project has dynamic roles. This check should follow the
    existing project's admin/superuser behavior.
    """

    if not user or not user.is_authenticated:
        return False

    # Preserve the common existing admin/superuser behavior.
    if getattr(user, "is_superuser", False):
        return True

    # Your existing User model already has is_admin() according
    # to the inspected project architecture.
    is_admin_method = getattr(user, "is_admin", None)

    if callable(is_admin_method):
        return bool(is_admin_method())

    return False


def get_accessible_company_ids(user) -> list[int] | None:
    """
    Return IDs of companies that the user can access.

    Returns:
        None -> unrestricted/global access
        []   -> authenticated user has no company access
        [1,2] -> explicitly accessible companies
    """

    if not user or not user.is_authenticated:
        return []

    if is_unrestricted_user(user):
        return None

    return list(
        user.company_accesses
        .filter(
            status=1,
            company__is_active=True,
        )
        .values_list(
            "company_id",
            flat=True,
        )
    )


def user_can_access_company(user, company_or_id) -> bool:
    """
    Check whether a user can access a particular company.

    company_or_id may be:
        - Company instance
        - integer ID
        - string ID
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

    return user.company_accesses.filter(
        company_id=company_id,
        status=1,
        company__is_active=True,
    ).exists()


def require_company_access(user, company_or_id) -> None:
    """
    Raise HTTP 403 when the user cannot access the company.
    """

    if not user_can_access_company(
        user,
        company_or_id,
    ):
        raise PermissionDenied(
            detail="You do not have access to this company."
        )


def filter_company_queryset(
    queryset: QuerySet,
    user,
    company_field: str = "company_id",
) -> QuerySet:
    """
    Restrict a queryset to companies accessible by the user.

    Examples:

        filter_company_queryset(
            DailyPrice.objects.all(),
            request.user,
        )

    or:

        filter_company_queryset(
            Company.objects.all(),
            request.user,
            "id",
        )
    """

    company_ids = get_accessible_company_ids(user)

    # None means unrestricted.
    if company_ids is None:
        return queryset

    # Empty list intentionally returns no records.
    return queryset.filter(
        **{
            f"{company_field}__in": company_ids
        }
    )


def require_permission(
    user,
    permission_code: str,
) -> None:
    """
    Use the EXISTING dynamic permission architecture.

    Adapt the method name only if your User model uses a different
    permission-checking method.
    """

    checker = getattr(
        user,
        "has_app_permission",
        None,
    )

    if callable(checker):
        allowed = checker(permission_code)
    else:
        checker = getattr(
            user,
            "has_permission",
            None,
        )

        if not callable(checker):
            raise PermissionDenied(
                "Permission checking is not configured."
            )

        allowed = checker(permission_code)

    if not allowed:
        raise PermissionDenied(
            "You do not have the required permission."
        )


def require_permission_and_company(
    user,
    permission_code: str,
    company_or_id,
) -> None:
    """
    Central authorization function.

    BOTH conditions are required:

        dynamic permission
        +
        company access
    """

    require_permission(
        user,
        permission_code,
    )

    require_company_access(
        user,
        company_or_id,
    )


def filter_queryset_by_user_companies(
    queryset: QuerySet,
    user,
    company_field: str = "company_id",
) -> QuerySet:
    """
    Alias with a more descriptive name.

    Useful when reading views.
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
    Specifically for Company.objects queryset.
    """

    company_ids = get_accessible_company_ids(user)

    if company_ids is None:
        return company_queryset

    return company_queryset.filter(
        pk__in=company_ids,
        is_active=True,
    )


def validate_company_ids(
    user,
    company_ids: Iterable[int],
) -> list[int]:
    """
    Validate a collection of company IDs against the user's access.

    Useful for:
        - bulk operations
        - comparison
        - exports
        - reports
        - watchlist
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

    # Remove duplicates while preserving order.
    normalized_ids = list(
        dict.fromkeys(normalized_ids)
    )

    accessible_ids = get_accessible_company_ids(
        user
    )

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


from django.db import transaction

from .models import UserCompanyAccess


@transaction.atomic
def set_company_access(user, company_access):
    """
    Replace all company access records for a user.

    company_access should contain items like:
        [
            {"company_id": 2, "status": 1},
            {"company_id": 7, "status": 1},
            {"company_id": 9, "status": 0},
        ]

    Existing records are updated or created.
    Companies not included in the submitted list are removed.
    """

    submitted_company_ids = set()

    for item in company_access:
        company_id = int(item["company_id"])
        status = int(item["status"])

        submitted_company_ids.add(company_id)

        UserCompanyAccess.objects.update_or_create(
            user=user,
            company_id=company_id,
            defaults={
                "status": status,
            },
        )

    # Remove old company-access records that were
    # not included in the new submission.
    UserCompanyAccess.objects.filter(
        user=user
    ).exclude(
        company_id__in=submitted_company_ids
    ).delete()
    
    
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import NotFound


def is_unrestricted_user(user):
    """
    Preserve the existing project's global-access behavior.

    IMPORTANT:
    Do not automatically assume every admin is unrestricted.
    Adjust this only if your existing RBAC implementation already
    treats a particular user as having global access.
    """
    return getattr(user, "is_superuser", False)


def get_accessible_company_ids(user):
    """
    Return IDs of companies the authenticated user can access.
    """

    if not user or not user.is_authenticated:
        return []

    if is_unrestricted_user(user):
        from apps.companies.models import Company

        return Company.objects.values_list("id", flat=True)

    return (
        user.company_access
        .filter(is_active=True)
        .values_list("company_id", flat=True)
    )


def user_can_access_company(user, company):
    """
    Check whether a user has active access to a company.
    """

    if not user or not user.is_authenticated:
        return False

    if is_unrestricted_user(user):
        return True

    return user.company_access.filter(
        company_id=company.id,
        is_active=True,
    ).exists()


def require_company_access(user, company):
    """
    Raise 403 when the user cannot access the company.
    """

    if not user_can_access_company(user, company):
        raise PermissionDenied(
            "You do not have access to this company."
        )

    return True


def require_company_id_access(user, company_id):
    """
    Check access directly from a company ID.
    """

    if is_unrestricted_user(user):
        return True

    if not user.company_access.filter(
        company_id=company_id,
        is_active=True,
    ).exists():
        raise PermissionDenied(
            "You do not have access to this company."
        )

    return True


def filter_company_queryset(queryset, user, field_name="company_id"):
    """
    Restrict an existing queryset to companies accessible
    to the authenticated user.
    """

    allowed_ids = get_accessible_company_ids(user)

    return queryset.filter(
        **{
            f"{field_name}__in": allowed_ids,
        }
    )


def require_permission(user, permission_code):
    """
    Reuse your EXISTING dynamic permission implementation here.

    Replace the body with the exact permission helper already used
    by your project.
    """

    if not user.is_authenticated:
        raise PermissionDenied(
            "Authentication required."
        )

    if not user.has_app_permission(permission_code):
        raise PermissionDenied(
            f"Missing permission: {permission_code}"
        )

    return True


def require_permission_and_company(
    user,
    permission_code,
    company_id,
):
    """
    Every company-scoped operation should use this pattern.
    """

    require_permission(
        user,
        permission_code,
    )

    require_company_id_access(
        user,
        company_id,
    )

    return True



from django.db import transaction

from .models import UserCompanyAccess


@transaction.atomic
def set_company_access(user, company_access):
    """
    Replace all company access records for a user.

    company_access should contain items like:
        [
            {"company_id": 2, "status": 1},
            {"company_id": 7, "status": 1},
            {"company_id": 9, "status": 0},
        ]

    Existing records are updated or created.
    Companies not included in the submitted list are removed.
    """

    submitted_company_ids = set()

    for item in company_access:
        company_id = int(item["company_id"])
        status = int(item["status"])

        submitted_company_ids.add(company_id)

        UserCompanyAccess.objects.update_or_create(
            user=user,
            company_id=company_id,
            defaults={
                "status": status,
            },
        )

    # Remove old company-access records that were
    # not included in the new submission.
    UserCompanyAccess.objects.filter(
        user=user
    ).exclude(
        company_id__in=submitted_company_ids
    ).delete()