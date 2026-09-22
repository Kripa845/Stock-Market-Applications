from rest_framework.exceptions import PermissionDenied

from .company_access import has_company_access


def check_company_access(
    user,
    company_id: int,
    permission_name: str,
):
    """
    Check both:

    1. Does the user have the required permission?
    2. Does the user have access to this company?

    Admins bypass both checks according to the
    existing project architecture.
    """

    # Admin bypass
    if user.is_admin():
        return

    # Existing permission system
    if not user.has_app_permission(permission_name):
        raise PermissionDenied(
            f"You do not have permission: {permission_name}"
        )

    # Company restriction
    if not has_company_access(user, company_id):
        raise PermissionDenied(
            "You do not have access to this company."
        )