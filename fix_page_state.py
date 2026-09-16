import os

path = 'frontend/src/pages/admin/RolesPermissionPage.tsx'
with open(path) as f:
    content = f.read()

old = '''// Role selector state.
  const [
    selectedRole,
    setSelectedRole,
  ] = useState<BuiltInRole | null>(null);

  const [
    selectedCustomRole,
    setSelectedCustomRole,
  ] = useState<CustomRole | null>(null);

  const [
    currentPermissions,
    setCurrentPermissions,
  ] = useState<string[]>([]);

  const builtInRoleDefaultPermissions: Record<BuiltInRole, string[]> = {
    admin: [],
    analyst: [
      "view_companies",
      "view_market_data",
      "view_price_history",
      "view_trading_volume",
      "view_vwap",
      "view_buy_sell_pressure",
      "view_news",
      "categorize_news",
      "correct_categories",
      "view_watchlist",
      "view_crawl_runs",
      "view_crawl_logs",
      "view_analysis",
      "view_price_trends",
      "view_volume_trends",
      "view_vwap_analysis",
      "view_pressure_analysis",
      "view_reports",
      "generate_reports",
      "export_reports",
    ],
    viewer: [
      "view_companies",
      "view_market_data",
      "view_price_history",
      "view_trading_volume",
      "view_news",
      "view_watchlist",
      "view_analysis",
      "view_price_trends",
      "view_volume_trends",
      "view_vwap_analysis",
      "view_pressure_analysis",
      "view_reports",
    ],
  };

  const selectBuiltInRole = (role: BuiltInRole) => {
    setSelectedRole(role);
    setSelectedCustomRole(null);
    setCurrentPermissions(builtInRoleDefaultPermissions[role]);
  };

  const selectCustomRole = (role: CustomRole) => {
    setSelectedRole(null);
    setSelectedCustomRole(role);
    setCurrentPermissions([...role.permissions]);
  };

  const closeRoleEditor = () => {
    setSelectedRole(null);
    setSelectedCustomRole(null);
    setCurrentPermissions([]);
  };

  const togglePermissionInGrid = (permissionKey: string) => {
    setCurrentPermissions((current) => {
      const exists = current.includes(permissionKey);

      return exists
        ? current.filter((p) => p !== permissionKey)
        : [...current, permissionKey];
    });
  };

  const toggleGroupPermissions = (group: PermissionGroup) => {
    const keys = group.permissions.map((p) => p.key);

    setCurrentPermissions((current) => {
      const allSelected = keys.every((k) => current.includes(k));

      if (allSelected) {
        return current.filter((p) => !keys.includes(p));
      }

      return Array.from(new Set([...current, ...keys]));
    });
  };

  const saveRoleEdits = async () => {
    if (!selectedCustomRole) {
      return;
    }

    try {
      setSaving(true);
      setError("");

      await rolesApi.updateCustomRole(selectedCustomRole.id, {
        name: selectedCustomRole.name,
        description: selectedCustomRole.description,
        permissions: currentPermissions,
      });

      closeRoleEditor();
      await loadData();
    } catch (err: any) {
      const data = err?.response?.data;
      setError(
        data?.name?.[0] ||
          data?.permissions?.[0] ||
          data?.detail ||
          "Unable to save role."
      );
    } finally {
      setSaving(false);
    }
  };

  const loadData = async () => {'''

new = '''// Role selector state.
  const [
    selectedRole,
    setSelectedRole,
  ] = useState<EditableRole | null>(null);

  const [
    selectedCustomRole,
    setSelectedCustomRole,
  ] = useState<CustomRoleSummary | null>(null);

  const [
    currentPermissions,
    setCurrentPermissions,
  ] = useState<string[]>([]);

  const builtInRoles = [
    {
      key: "analyst" as const,
      name: "Analyst",
      description:
        "Market analysis and news review access.",
    },

    {
      key: "viewer" as const,
      name: "Viewer",
      description:
        "Read-only access to market information.",
    },
  ];

  const selectBuiltInRole = async (
    roleKey: "analyst" | "viewer"
  ) => {
    try {
      const data =
        await rolesApi.getBuiltInRole(
          roleKey
        );

      setSelectedRole(data);
      setSelectedCustomRole(null);
      setCurrentPermissions(
        data.permissions
      );
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          "Unable to load role permissions."
      );
    }
  };

  const selectCustomRole = (
    role: CustomRoleSummary
  ) => {
    setSelectedRole(null);
    setSelectedCustomRole(role);
    setCurrentPermissions(
      role.permissions
    );
  };

  const closeRoleEditor = () => {
    setSelectedRole(null);
    setSelectedCustomRole(null);
    setCurrentPermissions([]);
  };

  const togglePermissionInGrid = (
    permissionKey: string
  ) => {
    setCurrentPermissions((current) => {
      const exists = current.includes(
        permissionKey
      );

      return exists
        ? current.filter(
            (p) => p !== permissionKey
          )
        : [...current, permissionKey];
    });
  };

  const toggleGroupPermissions = (
    group: PermissionGroup
  ) => {
    const keys = group.permissions.map(
      (p) => p.key
    );

    setCurrentPermissions((current) => {
      const allSelected = keys.every(
        (k) => current.includes(k)
      );

      if (allSelected) {
        return current.filter(
          (p) => !keys.includes(p)
        );
      }

      return Array.from(
        new Set([...current, ...keys])
      );
    });
  };

  const saveRoleEdits = async () => {
    try {
      setSaving(true);
      setError("");

      if (selectedRole) {
        if (
          selectedRole.key === "admin"
        ) {
          setError(
            "Admin permissions cannot be modified."
          );

          return;
        }

        await rolesApi.updateBuiltInRole(
          selectedRole.key as
            | "analyst"
            | "viewer",
          currentPermissions
        );

        setSelectedRole((current) =>
          current
            ? {
                ...current,
                permissions: [
                  ...currentPermissions,
                ],
              }
            : current
        );
      } else if (selectedCustomRole) {
        await rolesApi.updateCustomRole(
          selectedCustomRole.id,
          {
            permissions: currentPermissions,
          }
        );

        setSelectedCustomRole((current) =>
          current
            ? {
                ...current,
                permissions: [
                  ...currentPermissions,
                ],
              }
            : current
        );
      }

      closeRoleEditor();
      await loadData();
    } catch (err: any) {
      const data = err?.response?.data;

      setError(
        data?.name?.[0] ||
          data?.permissions?.[0] ||
          data?.invalid_permissions?.[0] ||
          data?.detail ||
          "Unable to save role."
      );
    } finally {
      setSaving(false);
    }
  };

  const loadData = async () => {'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print('OK: replaced state and handlers')
else:
    print('ERROR: old string not found')
    # Show the area
    idx = content.find('// Role selector state.')
    if idx >= 0:
        print(content[idx:idx+200])