import os

path = 'Backend/apps/users/urls.py'
with open(path) as f:
    content = f.read()

old = '''from .views import (
    AdminUserDetailAPIView,
    AdminUserListCreateAPIView,
    AnalystListAPIView,
    CustomRoleDetailAPIView,
    CustomRoleListCreateAPIView,
    CustomTokenObtainPairView,
    MeAPIView,
    RegisterAPIView,
    RolePermissionDefinitionsAPIView,
    RolePermissionsAPIView,
    RoleStatisticsAPIView,
)'''

new = '''from .views import (
    AdminUserDetailAPIView,
    AdminUserListCreateAPIView,
    AnalystListAPIView,
    CustomRoleDetailAPIView,
    CustomRoleListCreateAPIView,
    CustomTokenObtainPairView,
    MeAPIView,
    RegisterAPIView,
    RolePermissionDetailAPIView,
    RolePermissionDefinitionsAPIView,
    RolePermissionsAPIView,
    RoleStatisticsAPIView,
)'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print('OK: updated urls.py imports')
else:
    print('ERROR: old string not found')
    # show what we have
    for i, line in enumerate(content.split('\n')[:25], 1):
        print(f'{i}: {line}')