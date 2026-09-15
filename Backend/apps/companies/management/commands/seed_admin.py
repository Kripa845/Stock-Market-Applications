from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Create or update the default admin user"

    def handle(self, *args, **options):
        User = get_user_model()

        username = "admin1"
        email = "admin@.com"
        password = "Admin@123"

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "role": "admin",
                "is_active": True,
            },
        )

        # Make sure the existing user also becomes admin
        user.email = email
        user.role = "admin"
        user.is_active = True
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    "Admin user created successfully."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Admin user already existed. Admin details updated."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Username: {username}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Password: {password}"
            )
        )