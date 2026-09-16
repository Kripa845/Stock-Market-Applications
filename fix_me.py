import os

path = 'Backend/apps/users/serializers.py'
with open(path) as f:
    content = f.read()

old = '''    effective_role = serializers.SerializerMethodField()

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "custom_role_id",
            "custom_role_name",
            "effective_role",
            "is_active",
            "date_joined",
            "last_login",
        ]

        read_only_fields = [
            "id",
            "username",
            "role",
            "custom_role_id",
            "custom_role_name",
            "effective_role",
            "is_active",
            "date_joined",
            "last_login",
        ]

    def get_effective_role(self, obj):
        return obj.get_effective_role_name()'''

new = '''    effective_role = serializers.SerializerMethodField()

    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "custom_role_id",
            "custom_role_name",
            "effective_role",
            "permissions",
            "is_active",
            "date_joined",
            "last_login",
        ]

        read_only_fields = [
            "id",
            "username",
            "role",
            "custom_role_id",
            "custom_role_name",
            "effective_role",
            "permissions",
            "is_active",
            "date_joined",
            "last_login",
        ]

    def get_effective_role(self, obj):
        return obj.get_effective_role_name()

    def get_permissions(self, obj):
        if obj.is_admin():
            return list(VALID_PERMISSION_KEYS)

        if obj.custom_role:
            if not obj.custom_role.is_active:
                return []

            return list(
                obj.custom_role.permissions or []
            )

        config = (
            RolePermissionConfig.objects
            .filter(
                role_key=obj.role,
                is_active=True,
            )
            .first()
        )

        if config:
            return list(config.permissions or [])

        return []'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print('OK: updated MeSerializer')
else:
    print('ERROR: old string not found')
    # Show what we have around line 308
    lines = content.split('\n')
    for i in range(305, min(360, len(lines))):
        print(f'{i+1}: {lines[i]}')