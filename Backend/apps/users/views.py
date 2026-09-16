
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
)

from .permissions import IsAdminUserRole

from .models import CustomRole, RolePermissionConfig

from .serializers import (
    AdminUserCreateSerializer,
    AdminUserUpdateSerializer,
    CustomTokenObtainPairSerializer,
    MeSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from .serializers import (
    CustomRoleSerializer,
    ROLE_PERMISSIONS,
    VALID_PERMISSION_KEYS,
)

User = get_user_model()


class CustomRoleListCreateAPIView(APIView):
    """
    GET:
        Return all custom roles.

    POST:
        Create a new custom role.

    Admin only.
    """

    permission_classes = [
        IsAdminUserRole
    ]

    def get(self, request):
        roles = CustomRole.objects.all()

        serializer = CustomRoleSerializer(
            roles,
            many=True,
        )

        return Response(
            {
                "roles": serializer.data
            }
        )

    def post(self, request):
        serializer = CustomRoleSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        role = serializer.save()

        return Response(
            CustomRoleSerializer(role).data,
            status=status.HTTP_201_CREATED,
        )


class CustomRoleDetailAPIView(APIView):
    """
    GET:
        Get one custom role.

    PATCH:
        Update custom role.

    DELETE:
        Delete custom role.

    Admin only.
    """

    permission_classes = [
        IsAdminUserRole
    ]

    def get_object(self, pk):
        return get_object_or_404(
            CustomRole,
            pk=pk,
        )

    def get(self, request, pk):
        role = self.get_object(pk)

        serializer = CustomRoleSerializer(role)

        return Response(
            serializer.data
        )

    def patch(self, request, pk):
        role = self.get_object(pk)

        serializer = CustomRoleSerializer(
            role,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(
            raise_exception=True
        )

        role = serializer.save()

        return Response(
            CustomRoleSerializer(role).data
        )

    def delete(self, request, pk):
        role = self.get_object(pk)

        # Do not physically remove the role if users
        # are assigned to it.
        role.is_active = False
        role.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        # Users assigned to this custom role become
        # normal viewers.
        User.objects.filter(
            custom_role=role
        ).update(
            custom_role=None,
            role=User.Role.VIEWER,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


class RolePermissionDefinitionsAPIView(APIView):
    """
    Returns the permission structure used by
    the Create Role page.
    """

    permission_classes = [
        IsAdminUserRole
    ]

    def get(self, request):
        groups = []

        for group_key, permissions in ROLE_PERMISSIONS.items():
            groups.append(
                {
                    "key": group_key,
                    "name": group_key.title(),
                    "permissions": permissions,
                }
            )

        return Response(
            {
                "groups": groups
            }
        )

# ======================================================
# LOGIN
# ======================================================

class CustomTokenObtainPairView(
    TokenObtainPairView
):
    serializer_class = (
        CustomTokenObtainPairSerializer
    )


# ======================================================
# REGISTRATION
# ======================================================

class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = (
            UserRegistrationSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        user = serializer.save()

        return Response(
            {
                "message":
                "Registration successful.",
                "user":
                UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ======================================================
# CURRENT USER
# ======================================================

class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            UserSerializer(
                request.user
            ).data
        )

    def patch(self, request):
        serializer = MeSerializer(
            request.user,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(
            raise_exception=True
        )

        user = serializer.save()

        return Response(
            UserSerializer(user).data
        )


# ======================================================
# ADMIN USER MANAGEMENT
# ======================================================

class AdminUserListCreateAPIView(
    generics.ListCreateAPIView
):
    """
    Admin-only user management.

    GET  -> list users
    POST -> create user
    """

    permission_classes = [
        IsAdminUserRole
    ]

    queryset = User.objects.all()

    def get_queryset(self):
        queryset = (
            User.objects
            .all()
            .order_by("-date_joined")
        )

        search = (
            self.request.query_params
            .get("search")
        )

        role = (
            self.request.query_params
            .get("role")
        )

        user_status = (
            self.request.query_params
            .get("status")
        )

        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        if role in [
            User.Role.ADMIN,
            User.Role.ANALYST,
            User.Role.VIEWER,
        ]:
            queryset = queryset.filter(
                role=role
            )

        if user_status == "active":
            queryset = queryset.filter(
                is_active=True
            )

        elif user_status == "inactive":
            queryset = queryset.filter(
                is_active=False
            )

        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminUserCreateSerializer

        return UserSerializer

    def create(
        self,
        request,
        *args,
        **kwargs,
    ):
        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        user = serializer.save()

        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


# ======================================================
# ADMIN USER DETAIL
# ======================================================

class AdminUserDetailAPIView(
    generics.RetrieveUpdateDestroyAPIView
):
    """
    Admin-only individual user management.
    """

    permission_classes = [
        IsAdminUserRole
    ]

    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method in [
            "PUT",
            "PATCH",
        ]:
            return AdminUserUpdateSerializer

        return UserSerializer

    def destroy(
        self,
        request,
        *args,
        **kwargs,
    ):
        instance = self.get_object()

        if instance.id == request.user.id:
            return Response(
                {
                    "detail":
                    "You cannot delete your "
                    "own account."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.perform_destroy(instance)

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


# ======================================================
# ADMIN ANALYSTS
# ======================================================

class AnalystListAPIView(
    generics.ListAPIView
):
    permission_classes = [
        IsAdminUserRole
    ]

    serializer_class = UserSerializer

    def get_queryset(self):
        queryset = (
            User.objects
            .filter(
                role=User.Role.ANALYST
            )
            .order_by("-date_joined")
        )

        search = (
            self.request.query_params
            .get("search")
        )

        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        return queryset


# ======================================================
# ROLE PERMISSIONS
# ======================================================

class RolePermissionDetailAPIView(APIView):
    """
    GET/PATCH a single built-in editable role
    (analyst or viewer).

    Admin only.
    """

    permission_classes = [
        IsAdminUserRole
    ]

    def get_object(self, role_key):
        config = (
            RolePermissionConfig.objects
            .filter(
                role_key=role_key,
                is_active=True,
            )
            .first()
        )

        if not config:
            return None

        return config

    def get(self, request, role_key):
        config = self.get_object(role_key)

        if not config:
            return Response(
                {
                    "detail": "Role not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "key": config.role_key,
                "name": config.name,
                "description": config.description,
                "permissions": list(
                    config.permissions or []
                ),
                "editable": True,
            }
        )

    def patch(self, request, role_key):
        if role_key == "admin":
            return Response(
                {
                    "detail": (
                        "Admin permissions cannot be "
                        "modified through this endpoint."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = self.get_object(role_key)

        if not config:
            return Response(
                {
                    "detail": "Role not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        permissions = request.data.get(
            "permissions"
        )

        if not isinstance(permissions, list):
            return Response(
                {
                    "permissions": [
                        "Permissions must be a list."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        invalid = [
            permission
            for permission in permissions
            if permission not in VALID_PERMISSION_KEYS
        ]

        if invalid:
            return Response(
                {
                    "invalid_permissions": invalid
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        config.permissions = list(
            dict.fromkeys(permissions)
        )
        config.save()

        return Response(
            {
                "key": config.role_key,
                "name": config.name,
                "description": config.description,
                "permissions": list(
                    config.permissions or []
                ),
                "editable": True,
            }
        )


class RolePermissionsAPIView(APIView):
    """
    Returns the editable role permission matrix.

    Admin is NOT included as an editable role.
    Admin always has full access.
    """

    permission_classes = [
        IsAdminUserRole
    ]

    def get(self, request):
        configs = (
            RolePermissionConfig.objects
            .filter(is_active=True)
            .order_by("role_key")
        )

        roles = []
        for config in configs:
            roles.append(
                {
                    "key": config.role_key,
                    "name": config.name,
                    "description": config.description,
                    "permissions": list(
                        config.permissions or []
                    ),
                    "editable": True,
                }
            )

        custom_roles_qs = (
            CustomRole.objects
            .prefetch_related("users")
        )

        custom_roles = []
        for role in custom_roles_qs:
            custom_roles.append(
                {
                    "id": role.id,
                    "key": f"custom:{role.id}",
                    "name": role.name,
                    "description": role.description,
                    "permissions": list(
                        role.permissions or []
                    ),
                    "editable": True,
                    "is_active": role.is_active,
                    "user_count": role.users.count(),
                }
            )

        return Response(
            {
                "roles": roles,
                "custom_roles": custom_roles,
            }
        )


# ======================================================

# ROLE STATISTICS
# ======================================================

class RoleStatisticsAPIView(APIView):
    permission_classes = [
        IsAdminUserRole
    ]

    def get(self, request):
        return Response(
            {
                "total_users":
                    User.objects.count(),

                "admins":
                    User.objects.filter(
                        role=User.Role.ADMIN
                    ).count(),

                "analysts":
                    User.objects.filter(
                        role=User.Role.ANALYST
                    ).count(),

                "viewers":
                    User.objects.filter(
                        role=User.Role.VIEWER
                    ).count(),

                "active_users":
                    User.objects.filter(
                        is_active=True
                    ).count(),

                "inactive_users":
                    User.objects.filter(
                        is_active=False
                    ).count(),
            }
        )

