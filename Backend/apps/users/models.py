from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        ANALYST = "analyst", "Analyst"
        VIEWER = "viewer", "Viewer"

    email = models.EmailField(
        unique=True,
        blank=False,
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VIEWER,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def is_analyst(self):
        return self.role in [
            self.Role.ADMIN,
            self.Role.ANALYST,
        ] or self.is_superuser

    def is_viewer(self):
        return self.role == self.Role.VIEWER

    def __str__(self):
        return f"{self.username} - {self.role}"