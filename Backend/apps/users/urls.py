from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)

from .views import (
    AdminUserDetailAPIView,
    AdminUserListCreateAPIView,
    AnalystListAPIView,
    CustomRoleDetailAPIView,
    CustomRoleListCreateAPIView,
    CustomTokenObtainPairView,
    MeAPIView,
    MePermissionsAPIView,
    RegisterAPIView,
    RolePermissionDetailAPIView,
    RolePermissionDefinitionsAPIView,
    RolePermissionsAPIView,
    RoleStatisticsAPIView,
)


urlpatterns = [
    # Authentication
    path(
        "register/",
        RegisterAPIView.as_view(),
        name="register",
    ),

    path(
        "login/",
        CustomTokenObtainPairView.as_view(),
        name="login",
    ),

    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),

    path(
        "me/",
        MeAPIView.as_view(),
        name="me",
    ),

    path(
        "me/permissions/",
        MePermissionsAPIView.as_view(),
        name="me-permissions",
    ),

    # Users
    path(
        "admin/users/",
        AdminUserListCreateAPIView.as_view(),
        name="admin-users",
    ),

    path(
        "admin/users/<int:pk>/",
        AdminUserDetailAPIView.as_view(),
        name="admin-user-detail",
    ),

    path(
        "admin/analysts/",
        AnalystListAPIView.as_view(),
        name="admin-analysts",
    ),

    # Editable built-in role permissions
    path(
        "admin/roles/statistics/",
        RoleStatisticsAPIView.as_view(),
        name="role-statistics",
    ),

    path(
        "admin/roles/<str:role_key>/",
        RolePermissionDetailAPIView.as_view(),
        name="role-permission-detail",
    ),

    # Existing role information
    path(
        "admin/roles/",
        RolePermissionsAPIView.as_view(),
        name="role-permissions",
    ),

    # Permission definitions for Create Role
    path(
        "admin/role-permissions/",
        RolePermissionDefinitionsAPIView.as_view(),
        name="role-permission-definitions",
    ),

    # Custom roles
    path(
        "admin/custom-roles/",
        CustomRoleListCreateAPIView.as_view(),
        name="custom-role-list-create",
    ),

    path(
        "admin/custom-roles/<int:pk>/",
        CustomRoleDetailAPIView.as_view(),
        name="custom-role-detail",
    ),
]