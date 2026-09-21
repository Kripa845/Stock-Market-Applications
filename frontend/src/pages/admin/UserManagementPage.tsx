
import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  AlertTriangle,
  Edit3,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UserRound,
  X,
} from "lucide-react";

import PageHeader from "../../components/common/PageHeader";
import Badge from "../../components/common/Badge";

import {
  usersApi,
  type AdminUser,
  type BuiltInRole as Role,
  type UserPayload,
} from "../../api/users";

import { useAuth } from "../../contexts/AuthContext";

const roleColors = {
  admin: "red",
  analyst: "purple",
  viewer: "gray",
} as const;

export default function UserManagementPage() {
  /*
   * ============================================================
   * AUTH / PERMISSIONS
   * ============================================================
   */
  const {
    hasPermission,
    user: me,
  } = useAuth();

  const actorIsAdmin =
    me?.role === "admin";

  const canViewUsers =
    hasPermission("view_users");

  const canCreate =
    hasPermission("create_users");

  const canEdit =
    hasPermission("edit_users");

  const canDelete =
    hasPermission("delete_users");

  const canChangeRoles =
    hasPermission("change_user_roles");

  const canToggleActive =
    hasPermission("activate_users");

  const canOpenEditor =
    canEdit ||
    canChangeRoles ||
    canToggleActive;

  /*
   * Admin users are protected from non-admin users.
   */
  const isProtected = (
    target: AdminUser
  ) =>
    target.role === "admin" &&
    !actorIsAdmin;

  /*
   * ============================================================
   * STATE
   * ============================================================
   */
  const [
    users,
    setUsers,
  ] = useState<AdminUser[]>([]);

  const [
    search,
    setSearch,
  ] = useState("");

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    error,
    setError,
  ] = useState("");

  const [
    saving,
    setSaving,
  ] = useState(false);

  const [
    editingUser,
    setEditingUser,
  ] = useState<AdminUser | null>(
    null
  );

  const [
    showForm,
    setShowForm,
  ] = useState(false);

  const [
    form,
    setForm,
  ] = useState<UserPayload>({
    username: "",
    email: "",
    first_name: "",
    last_name: "",
    password: "",
    role: "viewer",
    is_active: true,
  });

  /*
   * ============================================================
   * LOAD USERS
   * ============================================================
   *
   * Do not call the users endpoint when the user does not
   * have view_users.
   */
  const loadUsers = useCallback(
    () => {
      if (!canViewUsers) {
        setUsers([]);
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");

      usersApi
        .list()
        .then(setUsers)
        .catch(() =>
          setError(
            "Unable to load users from the database."
          )
        )
        .finally(() =>
          setLoading(false)
        );
    },
    [canViewUsers]
  );

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  /*
   * ============================================================
   * SEARCH
   * ============================================================
   */
  const normalizedSearch =
    search.trim().toLowerCase();

  const filteredUsers =
    users.filter((user) =>
      [
        user.username,
        user.email,
        user.first_name,
        user.last_name,
        user.role,
      ].some((value) =>
        value
          .toLowerCase()
          .includes(
            normalizedSearch
          )
      )
    );

  /*
   * ============================================================
   * OPEN CREATE FORM
   * ============================================================
   */
  const openCreate = () => {
    if (!canCreate) {
      setError(
        "You do not have permission to create users."
      );
      return;
    }

    setEditingUser(null);

    setForm({
      username: "",
      email: "",
      first_name: "",
      last_name: "",
      password: "",
      role: "viewer",
      is_active: true,
    });

    setError("");
    setShowForm(true);
  };

  /*
   * ============================================================
   * OPEN EDIT FORM
   * ============================================================
   */
  const openEdit = (
    targetUser: AdminUser
  ) => {
    if (isProtected(targetUser)) {
      setError(
        "You do not have permission to modify this administrator."
      );
      return;
    }

    if (!canOpenEditor) {
      setError(
        "You do not have permission to edit users."
      );
      return;
    }

    setEditingUser(targetUser);

    setForm({
      username:
        targetUser.username,
      email:
        targetUser.email,
      first_name:
        targetUser.first_name,
      last_name:
        targetUser.last_name,
      password: "",
      role: targetUser.role,
      is_active:
        targetUser.is_active,
    });

    setError("");
    setShowForm(true);
  };

  /*
   * ============================================================
   * SAVE USER
   * ============================================================
   */
  const saveUser = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    setSaving(true);
    setError("");

    try {
      /*
       * ========================================================
       * EDIT EXISTING USER
       * ========================================================
       */
      if (editingUser) {
        if (isProtected(editingUser)) {
          setError(
            "You do not have permission to modify this administrator."
          );
          return;
        }

        /*
         * -----------------------------------------------
         * ROLE VALIDATION
         * -----------------------------------------------
         */
        if (
          !actorIsAdmin &&
          form.role === "admin" &&
          editingUser.role !== "admin"
        ) {
          setError(
            "Only admins can assign the admin role."
          );
          return;
        }

        const payload: Partial<UserPayload> =
          {};

        /*
         * -----------------------------------------------
         * GENERAL USER INFORMATION
         * -----------------------------------------------
         *
         * Only edit_users can modify these fields.
         */
        if (canEdit) {
          payload.email =
            form.email;

          payload.first_name =
            form.first_name;

          payload.last_name =
            form.last_name;

          if (form.password) {
            payload.password =
              form.password;
          }

          /*
           * Username is intentionally not changed here.
           * Keep the existing backend behavior.
           */
        }

        /*
         * -----------------------------------------------
         * ROLE
         * -----------------------------------------------
         */
        if (
          canChangeRoles &&
          form.role !==
            editingUser.role
        ) {
          payload.role =
            form.role;
        }

        /*
         * -----------------------------------------------
         * ACTIVE / INACTIVE
         * -----------------------------------------------
         */
        if (
          canToggleActive &&
          form.is_active !==
            editingUser.is_active
        ) {
          payload.is_active =
            form.is_active;
        }

        /*
         * No permitted field was changed.
         */
        if (
          Object.keys(payload)
            .length === 0
        ) {
          setShowForm(false);
          return;
        }

        await usersApi.update(
          editingUser.id,
          payload
        );
      } else {
        /*
         * ======================================================
         * CREATE NEW USER
         * ======================================================
         */
        if (!canCreate) {
          setError(
            "You do not have permission to create users."
          );
          return;
        }

        if (!form.password) {
          throw new Error(
            "Password is required for a new user."
          );
        }

        /*
         * Non-admin users cannot create an admin.
         */
        if (
          form.role === "admin" &&
          !actorIsAdmin
        ) {
          setError(
            "Only admins can assign the admin role."
          );
          return;
        }

        /*
         * If the creator does not have
         * change_user_roles, create the account
         * using the safe default role.
         */
        const createPayload: UserPayload =
          {
            ...form,
            role: canChangeRoles
              ? form.role
              : "viewer",
          };

        /*
         * If the creator cannot activate/deactivate
         * accounts, keep the new account active.
         */
        if (!canToggleActive) {
          createPayload.is_active =
            true;
        }

        await usersApi.create(
          createPayload
        );
      }

      setShowForm(false);

      setEditingUser(null);

      await loadUsers();
    } catch (caught: any) {
      const response =
        caught?.response?.data;

      setError(
        response
          ? Object.values(response)
              .flat()
              .join(" ")
          : caught?.message ||
              "Unable to save user."
      );
    } finally {
      setSaving(false);
    }
  };

  /*
   * ============================================================
   * DELETE USER
   * ============================================================
   */
  const removeUser = async (
    targetUser: AdminUser
  ) => {
    if (!canDelete) {
      setError(
        "You do not have permission to delete users."
      );
      return;
    }

    if (isProtected(targetUser)) {
      setError(
        "You do not have permission to delete this administrator."
      );
      return;
    }

    if (
      !window.confirm(
        `Delete user ${targetUser.username}?`
      )
    ) {
      return;
    }

    try {
      setError("");

      await usersApi.delete(
        targetUser.id
      );

      setUsers((current) =>
        current.filter(
          (item) =>
            item.id !==
            targetUser.id
        )
      );
    } catch (caught: any) {
      setError(
        caught?.response?.data
          ?.detail ||
          "Unable to delete user."
      );
    }
  };

  /*
   * ============================================================
   * PAGE
   * ============================================================
   */
  return (
    <div className="space-y-6">
      {/* ======================================================
          HEADER
      ====================================================== */}
      <PageHeader
        title="User Management"
        subtitle=""
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={loadUsers}
              className="btn-ghost flex items-center gap-2"
              disabled={
                loading ||
                !canViewUsers
              }
            >
              <RefreshCw
                size={14}
                className={
                  loading
                    ? "animate-spin"
                    : ""
                }
              />
              Refresh
            </button>

            {canCreate && (
              <button
                type="button"
                onClick={
                  openCreate
                }
                className="btn-primary flex items-center gap-2"
              >
                <Plus size={14} />
                Add user
              </button>
            )}
          </div>
        }
      />

      {/* ======================================================
          ERROR
      ====================================================== */}
      {error && (
        <div className="flex items-center gap-2 text-sm text-down">
          <AlertTriangle
            size={14}
          />

          <span>{error}</span>

          {canViewUsers && (
            <button
              type="button"
              onClick={
                loadUsers
              }
              className="underline"
            >
              Retry
            </button>
          )}
        </div>
      )}

      {/* ======================================================
          NO VIEW USERS
      ====================================================== */}
      {!canViewUsers && (
        <div className="card flex flex-col items-center gap-2 py-12 text-center">
          <AlertTriangle
            size={24}
            className="text-text-muted"
          />

          <p className="text-sm text-text-primary">
            You do not have permission
            to view users.
          </p>

          <p className="text-xs text-text-muted">
            Contact an administrator if
            you need access to User
            Management.
          </p>
        </div>
      )}

      {/* ======================================================
          SEARCH + COUNT
      ====================================================== */}
      {canViewUsers && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="relative w-full max-w-md">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
              />

              <input
                value={search}
                onChange={(event) =>
                  setSearch(
                    event.target
                      .value
                  )
                }
                placeholder="Search users"
                className="w-full rounded-lg border border-bg-border bg-bg-card py-2 pl-9 pr-3 text-sm text-text-primary"
              />
            </div>

            <span className="text-xs text-text-muted">
              {
                filteredUsers.length
              }{" "}
              of{" "}
              {users.length}{" "}
              users
            </span>
          </div>

          {/* ==================================================
              LOADING
          ================================================== */}
          {loading &&
            users.length ===
              0 && (
              <p className="text-text-secondary">
                Loading users...
              </p>
            )}

          {/* ==================================================
              EMPTY
          ================================================== */}
          {!loading &&
            !error &&
            users.length ===
              0 && (
              <div className="card flex flex-col items-center gap-2 py-12 text-center">
                <UserRound
                  size={24}
                  className="text-text-muted"
                />

                <p className="text-sm text-text-primary">
                  No users found
                </p>

                <p className="text-xs text-text-muted">
                  The database does not
                  contain any users yet.
                </p>
              </div>
            )}

          {/* ==================================================
              USER TABLE
          ================================================== */}
          {users.length > 0 && (
            <div className="card overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-bg-border text-text-secondary">
                    <th className="py-3 text-left font-medium">
                      User
                    </th>

                    <th className="py-3 text-left font-medium">
                      Email
                    </th>

                    <th className="py-3 text-left font-medium">
                      Role
                    </th>

                    <th className="py-3 text-left font-medium">
                      Status
                    </th>

                    <th className="py-3 text-left font-medium">
                      Joined
                    </th>

                    <th className="py-3 text-left font-medium">
                      Last login
                    </th>

                    <th className="py-3 text-right font-medium">
                      Actions
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {filteredUsers.map(
                    (targetUser) => (
                      <tr
                        key={
                          targetUser.id
                        }
                        className="table-row"
                      >
                        {/* USER */}
                        <td className="py-3">
                          <div className="flex items-center gap-3">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-glow text-accent-light">
                              <UserRound
                                size={
                                  14
                                }
                              />
                            </div>

                            <div>
                              <p className="font-medium text-text-primary">
                                {[
                                  targetUser.first_name,
                                  targetUser.last_name,
                                ]
                                  .filter(
                                    Boolean
                                  )
                                  .join(
                                    " "
                                  ) ||
                                  targetUser.username}
                              </p>

                              <p className="text-xs text-text-muted">
                                @
                                {
                                  targetUser.username
                                }
                              </p>
                            </div>
                          </div>
                        </td>

                        {/* EMAIL */}
                        <td className="py-3 text-text-secondary">
                          {
                            targetUser.email ||
                            "—"
                          }
                        </td>

                        {/* ROLE */}
                        <td className="py-3">
                          <Badge
                            variant={
                              roleColors[
                                targetUser
                                  .role
                              ]
                            }
                          >
                            {
                              targetUser.role
                            }
                          </Badge>
                        </td>

                        {/* STATUS */}
                        <td className="py-3">
                          <Badge
                            variant={
                              targetUser.is_active
                                ? "green"
                                : "red"
                            }
                          >
                            {targetUser.is_active
                              ? "Active"
                              : "Inactive"}
                          </Badge>
                        </td>

                        {/* JOINED */}
                        <td className="py-3 text-text-secondary">
                          {targetUser.date_joined
                            ? new Date(
                                targetUser.date_joined
                              ).toLocaleDateString()
                            : "—"}
                        </td>

                        {/* LAST LOGIN */}
                        <td className="py-3 text-text-secondary">
                          {targetUser.last_login
                            ? new Date(
                                targetUser.last_login
                              ).toLocaleString()
                            : "Never"}
                        </td>

                        {/* ACTIONS */}
                        <td className="py-3">
                          <div className="flex justify-end gap-1">
                            {canOpenEditor &&
                              !isProtected(
                                targetUser
                              ) && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    openEdit(
                                      targetUser
                                    )
                                  }
                                  className="p-2 text-text-muted hover:text-accent-light"
                                  title="Edit user"
                                >
                                  <Edit3
                                    size={
                                      14
                                    }
                                  />
                                </button>
                              )}

                            {canDelete &&
                              !isProtected(
                                targetUser
                              ) && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    removeUser(
                                      targetUser
                                    )
                                  }
                                  className="p-2 text-text-muted hover:text-down"
                                  title="Delete user"
                                >
                                  <Trash2
                                    size={
                                      14
                                    }
                                  />
                                </button>
                              )}
                          </div>
                        </td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>

              {!loading &&
                filteredUsers.length ===
                  0 && (
                  <p className="py-8 text-center text-sm text-text-muted">
                    No users match this
                    search.
                  </p>
                )}
            </div>
          )}
        </>
      )}

      {/* ======================================================
          CREATE / EDIT MODAL
      ====================================================== */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <form
            onSubmit={saveUser}
            className="w-full max-w-lg space-y-4 rounded-xl border border-bg-border bg-bg-secondary p-6 shadow-2xl"
          >
            {/* MODAL HEADER */}
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-text-primary">
                {editingUser
                  ? "Edit user"
                  : "Add user"}
              </h2>

              <button
                type="button"
                onClick={() => {
                  if (!saving) {
                    setShowForm(
                      false
                    );
                    setEditingUser(
                      null
                    );
                  }
                }}
                className="text-text-muted hover:text-text-primary"
                title="Close"
              >
                <X size={18} />
              </button>
            </div>

            {/* FORM FIELDS */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {/* USERNAME */}
              <label className="text-xs text-text-secondary">
                Username

                <input
                  required
                  disabled={
                    !!editingUser
                  }
                  value={
                    form.username
                  }
                  onChange={(
                    event
                  ) =>
                    setForm({
                      ...form,
                      username:
                        event
                          .target
                          .value,
                    })
                  }
                  className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary disabled:opacity-60"
                />
              </label>

              {/* EMAIL */}
              <label className="text-xs text-text-secondary">
                Email

                <input
                  required
                  disabled={
                    !!editingUser &&
                    !canEdit
                  }
                  type="email"
                  value={
                    form.email
                  }
                  onChange={(
                    event
                  ) =>
                    setForm({
                      ...form,
                      email:
                        event
                          .target
                          .value,
                    })
                  }
                  className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary disabled:opacity-60"
                />
              </label>

              {/* FIRST NAME */}
              <label className="text-xs text-text-secondary">
                First name

                <input
                  disabled={
                    !!editingUser &&
                    !canEdit
                  }
                  value={
                    form.first_name
                  }
                  onChange={(
                    event
                  ) =>
                    setForm({
                      ...form,
                      first_name:
                        event
                          .target
                          .value,
                    })
                  }
                  className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary disabled:opacity-60"
                />
              </label>

              {/* LAST NAME */}
              <label className="text-xs text-text-secondary">
                Last name

                <input
                  disabled={
                    !!editingUser &&
                    !canEdit
                  }
                  value={
                    form.last_name
                  }
                  onChange={(
                    event
                  ) =>
                    setForm({
                      ...form,
                      last_name:
                        event
                          .target
                          .value,
                    })
                  }
                  className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary disabled:opacity-60"
                />
              </label>

              {/* PASSWORD */}
              <label className="text-xs text-text-secondary">
                Password

                <input
                  required={
                    !editingUser
                  }
                  disabled={
                    !!editingUser &&
                    !canEdit
                  }
                  type="password"
                  value={
                    form.password
                  }
                  onChange={(
                    event
                  ) =>
                    setForm({
                      ...form,
                      password:
                        event
                          .target
                          .value,
                    })
                  }
                  className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary disabled:opacity-60"
                  placeholder={
                    editingUser
                      ? "Leave blank to keep current"
                      : ""
                  }
                />
              </label>

              {/* ROLE */}
              {canChangeRoles && (
                <label className="text-xs text-text-secondary">
                  Role

                  <select
                    value={
                      form.role
                    }
                    onChange={(
                      event
                    ) =>
                      setForm({
                        ...form,
                        role:
                          event
                            .target
                            .value as Role,
                      })
                    }
                    className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary"
                  >
                    <option value="viewer">
                      Viewer
                    </option>

                    <option value="analyst">
                      Analyst
                    </option>

                    {actorIsAdmin && (
                      <option value="admin">
                        Admin
                      </option>
                    )}
                  </select>
                </label>
              )}
            </div>

            {/* ACTIVE */}
            {canToggleActive && (
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                <input
                  type="checkbox"
                  checked={
                    form.is_active
                  }
                  onChange={(
                    event
                  ) =>
                    setForm({
                      ...form,
                      is_active:
                        event
                          .target
                          .checked,
                    })
                  }
                />

                Active account
              </label>
            )}

            {/* ERROR */}
            {error && (
              <p className="text-sm text-down">
                {error}
              </p>
            )}

            {/* FOOTER */}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  if (!saving) {
                    setShowForm(
                      false
                    );
                    setEditingUser(
                      null
                    );
                  }
                }}
                disabled={saving}
                className="btn-ghost"
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={
                  saving ||
                  (!editingUser &&
                    !canCreate)
                }
                className="btn-primary"
              >
                {saving
                  ? "Saving..."
                  : "Save user"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

