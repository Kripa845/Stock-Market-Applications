import {
  useEffect,
  useState,
} from "react";

import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Edit3,
  Plus,
  Shield,
  Trash2,
  X,
} from "lucide-react";

import { useNavigate } from "react-router-dom";

import {
  rolesApi,
  type CustomRole,
  type PermissionGroup,
  type EditableRole,
  type CustomRoleSummary,
} from "../../api/roles";

import {
  usersApi,
  type AdminUser,
} from "../../api/users";

import { useAuth } from "../../contexts/AuthContext";


type BuiltInRole =
  | "admin"
  | "analyst"
  | "viewer";


interface RoleForm {
  name: string;
  description: string;
  permissions: string[];
}


const emptyForm: RoleForm = {
  name: "",
  description: "",
  permissions: [],
};


export default function RolesPermissionsPage() {
  const navigate = useNavigate();
  const { refreshPermissions } = useAuth();
  const [
    permissionGroups,
    setPermissionGroups,
  ] = useState<PermissionGroup[]>([]);

  const [
    customRoles,
    setCustomRoles,
  ] = useState<CustomRoleSummary[]>([]);

  const [
    users,
    setUsers,
  ] = useState<AdminUser[]>([]);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    saving,
    setSaving,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState("");

  const [
    showCreate,
    setShowCreate,
  ] = useState(false);

  const [
    editingRole,
    setEditingRole,
  ] = useState<CustomRole | null>(null);

  const [
    form,
    setForm,
  ] = useState<RoleForm>(emptyForm);

  const [
    expandedGroups,
    setExpandedGroups,
  ] = useState<string[]>([]);

  // Role selector state.
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
      // Refresh current user's permissions so changes apply on next navigation
      await refreshPermissions();
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

  const loadData = async () => {
    try {
      setLoading(true);
      setError("");

      const [
        permissionsResponse,
        rolesResponse,
        usersResponse,
      ] = await Promise.all([
        rolesApi.getPermissionDefinitions(),
        rolesApi.getRoles(),
        usersApi.list(),
      ]);

      setPermissionGroups(
        permissionsResponse.groups
      );

      setCustomRoles(
        rolesResponse.custom_roles
      );

      setUsers(
        usersResponse
      );

      setExpandedGroups(
        permissionsResponse.groups.map(
          (group) => group.key
        )
      );
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        "Unable to load roles and permissions."
      );
    } finally {
      setLoading(false);
    }
  };


  useEffect(() => {
    loadData();
  }, []);


const openCreate = () => {
    setEditingRole(null);

    setForm({
      ...emptyForm,
      permissions: [],
    });

    setShowCreate(true);
  };


  const closeModal = () => {
    if (saving) {
      return;
    }

    setShowCreate(false);
    setEditingRole(null);
    setForm(emptyForm);
  };

  const deleteRole = async (
    role: CustomRoleSummary
  ) => {
    const confirmed =
      window.confirm(
        `Delete "${role.name}"? Users assigned to this role will become Viewers.`
      );

    if (!confirmed) {
      return;
    }

    try {
      setError("");

      await rolesApi.deleteCustomRole(
        role.id
      );

      await loadData();
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
        "Unable to delete role."
      );
    }
  };


  const togglePermission = (
    permissionKey: string
  ) => {
    setForm((current) => {
      const exists =
        current.permissions.includes(
          permissionKey
        );

      return {
        ...current,

        permissions: exists
          ? current.permissions.filter(
              (permission) =>
                permission !== permissionKey
            )
          : [
              ...current.permissions,
              permissionKey,
            ],
      };
    });
  };


  const toggleGroup = (
    group: PermissionGroup
  ) => {
    const keys =
      group.permissions.map(
        (permission) =>
          permission.key
      );

    const allSelected =
      keys.every((key) =>
        form.permissions.includes(key)
      );

    setForm((current) => {
      if (allSelected) {
        return {
          ...current,
          permissions:
            current.permissions.filter(
              (permission) =>
                !keys.includes(permission)
            ),
        };
      }

      return {
        ...current,
        permissions: Array.from(
          new Set([
            ...current.permissions,
            ...keys,
          ])
        ),
      };
    });
  };


  const saveRole = async () => {
    const name =
      form.name.trim();

    if (!name) {
      setError(
        "Please enter a role name."
      );

      return;
    }

    if (
      form.permissions.length === 0
    ) {
      setError(
        "Please select at least one permission."
      );

      return;
    }

    try {
      setSaving(true);
      setError("");

      if (editingRole) {
        await rolesApi.updateCustomRole(
          editingRole.id,
          {
            name,
            description:
              form.description.trim(),
            permissions:
              form.permissions,
          }
        );
      } else {
        await rolesApi.createCustomRole({
          name,
          description:
            form.description.trim(),
          permissions:
            form.permissions,
        });
      }

      closeModal();

      await loadData();
    } catch (err: any) {
      const data =
        err?.response?.data;

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


  const assignRole = async (
    user: AdminUser,
    value: string
  ) => {
    try {
      setError("");

      if (value.startsWith("custom:")) {
        const id = Number(
          value.replace("custom:", "")
        );

        await usersApi.update(
          user.id,
          {
            custom_role_id: id,
          }
        );
      } else {
        await usersApi.update(
          user.id,
          {
            role:
              value as BuiltInRole,
            custom_role_id:
              null,
          }
        );
      }

      await loadData();
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
        "Unable to update user role."
      );
    }
  };


  const toggleUserStatus = async (
    user: AdminUser
  ) => {
    try {
      setError("");

      await usersApi.update(
        user.id,
        {
          is_active:
            !user.is_active,
        }
      );

      await loadData();
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
        "Unable to update user."
      );
    }
  };


  if (loading) {
    return (
      <div className="p-6">
        <div className="card p-8 text-center">
          Loading roles and permissions...
        </div>
      </div>
    );
  }


  return (
    <div className="space-y-6 p-6">

      {/* HEADER */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            Roles & Permissions
          </h1>

          <p className="mt-1 text-sm text-text-muted">
            Manage built-in roles and create
            custom roles with specific permissions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigate("/admin")}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-bg-border bg-bg-card px-4 py-2.5 text-sm font-medium text-text-secondary hover:bg-bg-elevated hover:text-text-primary"
          >
            <ArrowLeft size={18} />
            Back to Dashboard
          </button>

          <button
            type="button"
            onClick={openCreate}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:opacity-90"
          >
            <Plus size={18} />

            Create Role
          </button>
        </div>
      </div>

      {/* ROLE SELECTOR */}
      <div className="card p-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <label className="mb-1 block text-sm font-medium text-text-primary">
              Select Role
            </label>
            <p className="text-xs text-text-muted">
              View and edit permission assignments.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {builtInRoles.map((role) => (
              <button
                key={role.key}
                type="button"
                onClick={() =>
                  selectBuiltInRole(role.key)
                }
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                  selectedRole?.key === role.key
                    ? "border-accent bg-accent/15 text-accent-light"
                    : "border-bg-border bg-bg-card text-text-secondary hover:bg-bg-elevated"
                }`}
              >
                {role.name}
              </button>
            ))}

            {customRoles.length > 0 && (
              <>
                <span className="h-4 w-px bg-bg-border" />

                {customRoles
                  .filter((r) => r.is_active)
                  .map((role) => (
                    <button
                      key={role.id}
                      type="button"
                      onClick={() =>
                        selectCustomRole(role)
                      }
                      className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                        selectedCustomRole?.id === role.id
                          ? "border-accent bg-accent/15 text-accent-light"
                          : "border-bg-border bg-bg-card text-text-secondary hover:bg-bg-elevated"
                      }`}
                    >
                      {role.name}
                    </button>
                  ))}
              </>
            )}
          </div>
        </div>
      </div>

      {/* PERMISSION GRID */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {permissionGroups.map((group) => {
          const keys = group.permissions.map((p) => p.key);
          const selectedCount = keys.filter((k) => currentPermissions.includes(k)).length;
          const allSelected = selectedCount === keys.length && keys.length > 0;
          const someSelected = selectedCount > 0 && !allSelected;

          return (
            <div
              key={group.key}
              className="card overflow-hidden"
            >
              <div className="flex items-center justify-between border-b border-bg-border bg-bg-elevated px-4 py-3">
                <h3 className="text-sm font-semibold text-text-primary">
                  {group.name}
                </h3>

                <label className="flex cursor-pointer items-center gap-2 text-xs text-text-secondary">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => {
                      if (el) {
                        el.indeterminate = someSelected;
                      }
                    }}
                    onChange={() => toggleGroupPermissions(group)}
                    className="h-4 w-4 rounded border-bg-border bg-bg-card text-accent focus:ring-2 focus:ring-accent/30"
                  />
                  Select All
                </label>
              </div>

              <div className="divide-y divide-bg-border">
                {group.permissions.map((permission) => (
                  <label
                    key={permission.key}
                    className="flex cursor-pointer items-center gap-3 px-4 py-2 hover:bg-bg-elevated"
                  >
                    <input
                      type="checkbox"
                      checked={currentPermissions.includes(permission.key)}
                      onChange={() => togglePermissionInGrid(permission.key)}
                      className="h-4 w-4 rounded border-bg-border bg-bg-card text-accent focus:ring-2 focus:ring-accent/30"
                    />

                    <span className="text-sm text-text-secondary">
                      {permission.name}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* FOOTER */}
      {(selectedCustomRole || selectedRole) && (
        <div className="flex items-center justify-between gap-3">
          <div>
            {selectedCustomRole && (
              <p className="text-sm text-text-muted">
                Editing:{" "}
                <span className="font-medium text-text-primary">
                  {selectedCustomRole.name}
                </span>
              </p>
            )}

            {selectedRole && !selectedCustomRole && (
              <p className="text-sm text-text-muted">
                Editing:{" "}
                <span className="font-medium text-text-primary">
                  {selectedRole.name}
                </span>
              </p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={closeRoleEditor}
              className="rounded-lg border border-bg-border px-4 py-2.5 text-sm font-medium text-text-secondary hover:bg-bg-elevated"
            >
              Cancel
            </button>

            {selectedRole && selectedRole.key === "admin" ? (
              <button
                type="button"
                disabled
                className="rounded-lg bg-bg-elevated px-5 py-2.5 text-sm font-medium text-text-muted"
              >
                Admin - Protected
              </button>
            ) : (
              <button
                type="button"
                onClick={saveRoleEdits}
                disabled={saving}
                className="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Update Role"}
              </button>
            )}
          </div>
        </div>
      )}


      {/* ERROR */}
      {error && (
        <div className="flex items-start justify-between rounded-lg border border-down/30 bg-down/10 p-4 text-sm text-down">
          <span>
            {error}
          </span>

          <button
            onClick={() =>
              setError("")
            }
          >
            <X size={18} />
          </button>
        </div>
      )}


      {/* USER ROLE ASSIGNMENT */}
      <section>
        <div className="mb-3">
          <h2 className="text-lg font-semibold text-text-primary">
            User Role Assignment
          </h2>

          <p className="text-sm text-text-muted">
            Assign built-in or custom roles to users.
          </p>
        </div>

        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-bg-border bg-bg-elevated">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">
                    User
                  </th>

                  <th className="px-4 py-3 text-left font-medium">
                    Email
                  </th>

                  <th className="px-4 py-3 text-left font-medium">
                    Role
                  </th>

                  <th className="px-4 py-3 text-left font-medium">
                    Status
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-bg-border">
                {users.map((user) => {
                  const currentValue =
                    user.custom_role_id
                      ? `custom:${user.custom_role_id}`
                      : user.role;

                  return (
                    <tr
                      key={user.id}
                      className="hover:bg-bg-elevated"
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium">
                          {user.username}
                        </div>
                      </td>

                      <td className="px-4 py-3 text-text-muted">
                        {user.email}
                      </td>

                      <td className="px-4 py-3">
                        <select
                          value={currentValue}
                          onChange={(event) =>
                            assignRole(
                              user,
                              event.target.value
                            )
                          }
                          className="rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary"
                        >
                          <optgroup label="System Roles">
                            <option value="admin">
                              Admin
                            </option>

                            <option value="analyst">
                              Analyst
                            </option>

                            <option value="viewer">
                              Viewer
                            </option>
                          </optgroup>

                          {customRoles.length > 0 && (
                            <optgroup label="Custom Roles">
                              {customRoles.map((role) => (
                                <option
                                  key={role.id}
                                  value={`custom:${role.id}`}
                                >
                                  {role.name}
                                </option>
                              ))}
                            </optgroup>
                          )}
                        </select>
                      </td>

                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() =>
                            toggleUserStatus(user)
                          }
                          className={
                            user.is_active
                              ? "rounded-full bg-up/10 px-3 py-1 text-xs text-up"
                              : "rounded-full bg-down/10 px-3 py-1 text-xs text-down"
                          }
                        >
                          {user.is_active
                            ? "Active"
                            : "Inactive"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>


      {/* CUSTOM ROLES */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">
              Custom Roles
            </h2>

            <p className="text-sm text-text-muted">
              Roles created by administrators.
            </p>
          </div>

          <button
            type="button"
            onClick={openCreate}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-xs font-medium text-white hover:opacity-90"
          >
            <Plus size={16} />
            Create Role
          </button>
        </div>

        {customRoles.length === 0 ? (
          <div className="card p-8 text-center">
            <Shield
              className="mx-auto mb-3 text-text-muted"
              size={32}
            />

            <p className="font-medium">
              No custom roles yet
            </p>

            <p className="mt-1 text-sm text-text-muted">
              Create a role such as News Reviewer
              or Research Analyst.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {customRoles.map((role) => (
              <div
                key={role.id}
                className="card p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold">
                      {role.name}
                    </h3>

                    <span className="mt-1 inline-block rounded-full bg-accent/15 px-2 py-1 text-xs text-accent-light">
                      Custom Role
                    </span>
                  </div>

<div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() =>
                        selectCustomRole(role)
                      }
                      className="rounded-lg p-2 text-text-muted hover:bg-bg-elevated hover:text-text-primary"
                      title="Edit role"
                    >
                      <Edit3 size={16} />
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        deleteRole(role)
                      }
                      className="rounded-lg p-2 text-down hover:bg-down/15"
                      title="Delete role"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                <p className="mt-3 text-sm text-text-secondary">
                  {role.description ||
                    "No description."}
                </p>

                <div className="mt-4 flex items-center justify-between text-xs text-text-muted">
                  <span>
                    {role.permissions.length} permissions
                  </span>

                  <span>
                    {role.user_count} users
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>


      {/* CREATE / EDIT MODAL */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">

          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-bg-border bg-bg-secondary shadow-2xl">

            {/* MODAL HEADER */}
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-bg-border bg-bg-secondary px-6 py-4">

              <div>
                <h2 className="text-xl font-semibold text-text-primary">
                  {editingRole
                    ? "Edit Role"
                    : "Create Role"}
                </h2>

                <p className="mt-1 text-sm text-text-muted">
                  Select the permissions this role
                  should have.
                </p>
              </div>

              <button
                type="button"
                onClick={closeModal}
                className="rounded-lg p-2 hover:bg-bg-elevated"
              >
                <X size={20} />
              </button>

            </div>


            {/* FORM */}
            <div className="space-y-6 p-6">

              {/* ROLE NAME */}
              <div>
                <label className="mb-2 block text-sm font-medium text-text-primary">
                  Role Name
                </label>

                <input
                  type="text"
                  value={form.name}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      name:
                        event.target.value,
                    })
                  }
                  placeholder="News Reviewer"
                  className="w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2.5 text-sm text-text-primary outline-none focus:ring-2 focus:ring-accent/30"
                />
              </div>


              {/* DESCRIPTION */}
              <div>
                <label className="mb-2 block text-sm font-medium text-text-primary">
                  Description
                </label>

                <textarea
                  value={form.description}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      description:
                        event.target.value,
                    })
                  }
                  placeholder="Reviews and categorizes financial news."
                  rows={3}
                  className="w-full resize-none rounded-lg border border-bg-border bg-bg-card px-3 py-2.5 text-sm text-text-primary outline-none focus:ring-2 focus:ring-accent/30"
                />
              </div>


              {/* PERMISSIONS */}
              <div>

                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">
                      Permissions
                    </h3>

                    <p className="text-xs text-text-muted">
                      Select individual permissions.
                    </p>
                  </div>

                  <span className="text-xs text-text-muted">
                    {form.permissions.length}
                    {" "}
                    selected
                  </span>
                </div>


                <div className="space-y-3">

                  {permissionGroups.map(
                    (group) => {

                      const keys =
                        group.permissions.map(
                          (permission) =>
                            permission.key
                        );

                      const selectedCount =
                        keys.filter(
                          (key) =>
                            form.permissions.includes(
                              key
                            )
                        ).length;

                      const allSelected =
                        selectedCount ===
                          keys.length &&
                        keys.length > 0;

                      const expanded =
                        expandedGroups.includes(
                          group.key
                        );

                      return (
                        <div
                          key={group.key}
                          className="overflow-hidden rounded-lg border"
                        >

                          {/* GROUP */}
                          <div className="flex items-center justify-between bg-bg-elevated px-4 py-3">

                            <button
                              type="button"
                              onClick={() =>
                                setExpandedGroups(
                                  (current) =>
                                    current.includes(
                                      group.key
                                    )
                                      ? current.filter(
                                          (key) =>
                                            key !==
                                            group.key
                                        )
                                      : [
                                          ...current,
                                          group.key,
                                        ]
                                )
                              }
                              className="flex items-center gap-2 font-medium"
                            >
                              {expanded ? (
                                <ChevronDown
                                  size={17}
                                />
                              ) : (
                                <ChevronRight
                                  size={17}
                                />
                              )}

                              {group.name}

                              <span className="text-xs text-text-muted">
                                ({selectedCount}/
                                {keys.length})
                              </span>
                            </button>


                            <label className="flex cursor-pointer items-center gap-2 text-xs">
                              <input
                                type="checkbox"
                                checked={allSelected}
                                onChange={() =>
                                  toggleGroup(
                                    group
                                  )
                                }
                              />

                              Select all
                            </label>

                          </div>


                          {/* PERMISSION LIST */}
                          {expanded && (
                            <div className="space-y-1 p-3">

                              {group.permissions.map(
                                (permission) => (
                                  <label
                                    key={
                                      permission.key
                                    }
                                    className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-bg-elevated"
                                  >

                                    <input
                                      type="checkbox"
                                      checked={form.permissions.includes(
                                        permission.key
                                      )}
                                      onChange={() =>
                                        togglePermission(
                                          permission.key
                                        )
                                      }
                                      className="h-4 w-4"
                                    />

                                    <span className="text-sm">
                                      {
                                        permission.name
                                      }
                                    </span>

                                  </label>
                                )
                              )}

                            </div>
                          )}

                        </div>
                      );
                    }
                  )}

                </div>

              </div>

            </div>


            {/* FOOTER */}
            <div className="flex items-center justify-end gap-3 border-t px-6 py-4">

              <button
                type="button"
                onClick={closeModal}
                disabled={saving}
                className="rounded-lg border border-bg-border px-4 py-2.5 text-sm font-medium text-text-secondary hover:bg-bg-elevated"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={saveRole}
                disabled={saving}
                className="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {saving
                  ? "Saving..."
                  : editingRole
                    ? "Save Changes"
                    : "Create Role"}
              </button>

            </div>

          </div>

        </div>
      )}

    </div>
  );
}