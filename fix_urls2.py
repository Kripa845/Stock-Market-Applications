import os

path = 'Backend/apps/users/urls.py'
with open(path) as f:
    content = f.read()

old = '''    # Existing role information
    path(
        "admin/roles/",
        RolePermissionsAPIView.as_view(),
        name="role-permissions",
    ),

    path(
        "admin/roles/statistics/",
        RoleStatisticsAPIView.as_view(),
        name="role-statistics",
    ),'''

new = '''    # Editable built-in role permissions
    path(
        "admin/roles/analyst/",
        RolePermissionDetailAPIView.as_view(),
        name="role-permission-analyst",
    ),

    path(
        "admin/roles/viewer/",
        RolePermissionDetailAPIView.as_view(),
        name="role-permission-viewer",
    ),

    # Existing role information
    path(
        "admin/roles/",
        RolePermissionsAPIView.as_view(),
        name="role-permissions",
    ),

    path(
        "admin/roles/statistics/",
        RoleStatisticsAPIView.as_view(),
        name="role-statistics",
    ),'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print('OK: added role permission detail endpoints')
else:
    print('ERROR: old string not found')
    for i, line in enumerate(content.split('\n')[65:80], 66):
        print(f'{i}: {line}')