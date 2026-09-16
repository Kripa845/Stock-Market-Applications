from rest_framework import permissions


class IsAdminUserRole(permissions.BasePermission):
    message = "Admin role required to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_admin()
        )


class IsAnalystUserRole(permissions.BasePermission):
    message = "Analyst or Admin role required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_analyst()
        )


class IsViewerUserRole(permissions.BasePermission):
    message = "Authentication required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
        )


class HasAppPermission(permissions.BasePermission):
    """
    Permission class for application-level permissions.

    Usage:

        permission_key = "view_news"
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        permission_key = getattr(
            view,
            "permission_key",
            None,
        )

        if not permission_key:
            return False

        return user.has_app_permission(
            permission_key
        )


class HasViewMethodPermissions(permissions.BasePermission):
    """Check permissions selected by the view for the current request."""

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        required = (
            view.get_required_permissions(request)
            if hasattr(view, "get_required_permissions")
            else getattr(view, "permission_key", None)
        )
        if isinstance(required, str):
            required = [required]
        return bool(required) and all(
            user.has_app_permission(key) for key in required
        )


class ReadOnlyOrAdmin(permissions.BasePermission):
    message = "Admin role required to modify this resource."

    def has_permission(self, request, view):
        if not (
            request.user
            and request.user.is_authenticated
        ):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.is_admin()


class ReadOnlyOrAnalyst(permissions.BasePermission):
    message = "Analyst or Admin role required."

    def has_permission(self, request, view):
        if not (
            request.user
            and request.user.is_authenticated
        ):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.is_analyst()
