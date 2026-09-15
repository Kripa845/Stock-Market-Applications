from rest_framework import permissions


class IsAdminUserRole(permissions.BasePermission):
    """
    Allows access only to users with the 'admin' role or superusers.
    """
    message = "Admin role required to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_admin()
        )


class IsAnalystUserRole(permissions.BasePermission):
    """
    Allows access only to users with the 'analyst' or 'admin' role.
    """
    message = "Analyst or Admin role required to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_analyst()
        )


class IsViewerUserRole(permissions.BasePermission):
    """
    Allows access to any authenticated user (Viewer, Analyst, or Admin).
    """
    message = "Authentication required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
        )


class ReadOnlyOrAdmin(permissions.BasePermission):
    """
    Safe methods (GET, HEAD, OPTIONS) allowed for any authenticated user.
    Mutations (POST, PUT, PATCH, DELETE) require Admin role.
    """
    message = "Admin role required to modify this resource."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_admin()


class ReadOnlyOrAnalyst(permissions.BasePermission):
    """
    Safe methods allowed for any authenticated user.
    Mutations require Analyst or Admin role.
    """
    message = "Analyst or Admin role required to perform this modification."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_analyst()
