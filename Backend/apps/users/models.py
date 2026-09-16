from django.contrib.auth.models import AbstractUser
from django.db import models


class RolePermissionConfig(models.Model):
  

    class Meta:
        ordering = ["role_key"]

    ANALYST = "analyst"
    VIEWER = "viewer"

    ROLE_KEY_CHOICES = [
        (ANALYST, "Analyst"),
        (VIEWER, "Viewer"),
    ]

    role_key = models.CharField(
        max_length=20,
        choices=ROLE_KEY_CHOICES,
        unique=True,
    )

    name = models.CharField(
        max_length=100,
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    permissions = models.JSONField(
        default=list,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.name


class CustomRole(models.Model):
   

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    permissions = models.JSONField(
        default=list,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        ANALYST = "analyst", "Analyst"
        VIEWER = "viewer", "Viewer"

    email = models.EmailField(
        unique=True,
        blank=False,
    )

    # Built-in role.
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VIEWER,
    )

    # Optional custom role.
    custom_role = models.ForeignKey(
        CustomRole,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def is_admin(self):
        return (
            self.is_superuser
            or self.role == self.Role.ADMIN
        )

    def is_analyst(self):
        return (
            self.is_superuser
            or self.role in [
                self.Role.ADMIN,
                self.Role.ANALYST,
            ]
        )

    def is_viewer(self):
        return self.role == self.Role.VIEWER

    def has_custom_permission(self, permission_key):
        """
        Returns True if this user has the requested
        custom-role permission.
        """

        if self.is_admin():
            return True

        if not self.custom_role:
            return False

        if not self.custom_role.is_active:
            return False

        return permission_key in (
            self.custom_role.permissions or []
        )

    def has_app_permission(self, permission_key):
        """
        Central permission checker.

        Admin always has full access.
        Custom roles use their selected permissions.
        Analyst and Viewer use the database-backed
        RolePermissionConfig.
        """

        if self.is_superuser:
            return True

        # Admin has everything.
        if self.role == self.Role.ADMIN:
            return True

        # Custom role.
        if self.custom_role:
            return self.has_custom_permission(
                permission_key
            )

        # Database-backed built-in roles.
        config = (
            RolePermissionConfig.objects
            .filter(
                role_key=self.role,
                is_active=True,
            )
            .first()
        )

        if config:
            return permission_key in (
                config.permissions or []
            )

        return False

    def get_effective_role_name(self):
        if self.custom_role:
            return self.custom_role.name

        return self.get_role_display()

    def __str__(self):
        if self.custom_role:
            return f"{self.username} - {self.custom_role.name}"

        return f"{self.username} - {self.role}"