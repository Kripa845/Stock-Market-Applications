
// import {
//   useCallback,
//   useEffect,
//   useState,
// } from "react";

// import {
//   AlertTriangle,
//   Edit3,
//   Plus,
//   RefreshCw,
//   Search,
//   Trash2,
//   UserRound,
//   X,
// } from "lucide-react";

// import PageHeader from "../../components/common/PageHeader";
// import Badge from "../../components/common/Badge";

// import {
//   usersApi,
//   type AdminUser,
//   type BuiltInRole as Role,
//   type UserPayload,
// } from "../../api/users";

// import { useAuth } from "../../contexts/AuthContext";

// const roleColors = {
//   admin: "red",
//   analyst: "purple",
//   viewer: "gray",
// } as const;

// export default function UserManagementPage() {
//   /*
//    * ============================================================
//    * AUTH / PERMISSIONS
//    * ============================================================
//    */
//   const {
//     hasPermission,
//     user: me,
//   } = useAuth();

//   const actorIsAdmin =
//     me?.role === "admin";

//   const canViewUsers =
//     hasPermission("view_users");

//   const canCreate =
//     hasPermission("create_users");

//   const canEdit =
//     hasPermission("edit_users");

//   const canDelete =
//     hasPermission("delete_users");

//   const canChangeRoles =
//     hasPermission("change_user_roles");

//   const canToggleActive =
//     hasPermission("activate_users");

//   const canOpenEditor =
//     canEdit ||
//     canChangeRoles ||
//     canToggleActive;

//   /*
//    * Admin users are protected from non-admin users.
//    */
//   const isProtected = (
//     target: AdminUser
//   ) =>
//     target.role === "admin" &&
//     !actorIsAdmin;

//   /*
//    * ============================================================
//    * STATE
//    * ============================================================
//    */
//   const [
//     users,
//     setUsers,
//   ] = useState<AdminUser[]>([]);

//   const [
//     search,
//     setSearch,
//   ] = useState("");

//   const [
//     loading,
//     setLoading,
//   ] = useState(true);

//   const [
//     error,
//     setError,
//   ] = useState("");

//   const [
//     saving,
//     setSaving,
//   ] = useState(false);

//   const [
//     editingUser,
//     setEditingUser,
//   ] = useState<AdminUser | null>(
//     null
//   );

//   const [
//     showForm,
//     setShowForm,
//   ] = useState(false);

//   const [
//     form,
//     setForm,
//   ] = useState<UserPayload>({
//     username: "",
//     email: "",
//     first_name: "",
//     last_name: "",
//     password: "",
//     role: "viewer",
//     is_active: true,
//   });

//   /*
//    * ============================================================
//    * LOAD USERS
//    * ============================================================
//    *
//    * Do not call the users endpoint when the user does not
//    * have view_users.
//    */
//   const loadUsers = useCallback(
//     () => {
//       if (!canViewUsers) {
//         setUsers([]);
//         setLoading(false);
//         return;
//       }

//       setLoading(true);
//       setError("");

//       usersApi
//         .list()
//         .then(setUsers)
//         .catch(() =>
//           setError(
//             "Unable to load users from the database."
//           )
//         )
//         .finally(() =>
//           setLoading(false)
//         );
//     },
//     [canViewUsers]
//   );

//   useEffect(() => {
//     loadUsers();
//   }, [loadUsers]);

//   /*
//    * ============================================================
//    * SEARCH
//    * ============================================================
//    */
//   const normalizedSearch =
//     search.trim().toLowerCase();

//   const filteredUsers =
//     users.filter((user) =>
//       [
//         user.username,
//         user.email,
//         user.first_name,
//         user.last_name,
//         user.role,
//       ].some((value) =>
//         value
//           .toLowerCase()
//           .includes(
//             normalizedSearch
//           )
//       )
//     );

//   /*
//    * ============================================================
//    * OPEN CREATE FORM
//    * ============================================================
//    */
//   const openCreate = () => {
//     if (!canCreate) {
//       setError(
//         "You do not have permission to create users."
//       );
//       return;
//     }

//     setEditingUser(null);

//     setForm({
//       username: "",
//       email: "",
//       first_name: "",
//       last_name: "",
//       password: "",
//       role: "viewer",
//       is_active: true,
//     });

//     setError("");
//     setShowForm(true);
//   };

//   /*
//    * ============================================================
//    * OPEN EDIT FORM
//    * ============================================================
//    */
//   const openEdit = (
//     targetUser: AdminUser
//   ) => {
//     if (isProtected(targetUser)) {
//       setError(
//         "You do not have permission to modify this administrator."
//       );
//       return;
//     }

//     if (!canOpenEditor) {
//       setError(
//         "You do not have permission to edit users."
//       );
//       return;
//     }

//     setEditingUser(targetUser);

//     setForm({
//       username:
//         targetUser.username,
//       email:
//         targetUser.email,
//       first_name:
//         targetUser.first_name,
//       last_name:
//         targetUser.last_name,
//       password: "",
//       role: targetUser.role,
//       is_active:
//         targetUser.is_active,
//     });

//     setError("");
//     setShowForm(true);
//   };

//   /*
//    * ============================================================
//    * SAVE USER
//    * ============================================================
//    */
//   const saveUser = async (
//     event: React.FormEvent<HTMLFormElement>
//   ) => {
//     event.preventDefault();

//     setSaving(true);
//     setError("");

//     try {
//       /*
//        * ========================================================
//        * EDIT EXISTING USER
//        * ========================================================
//        */
//       if (editingUser) {
//         if (isProtected(editingUser)) {
//           setError(
//             "You do not have permission to modify this administrator."
//           );
//           return;
//         }

//         /*
//          * -----------------------------------------------
//          * ROLE VALIDATION
//          * -----------------------------------------------
//          */
//         if (
//           !actorIsAdmin &&
//           form.role === "admin" &&
//           editingUser.role !== "admin"
//         ) {
//           setError(
//             "Only admins can assign the admin role."
//           );
//           return;
//         }

//         const payload: Partial<UserPayload> =
//           {};

//         /*
//          * -----------------------------------------------
//          * GENERAL USER INFORMATION
//          * -----------------------------------------------
//          *
//          * Only edit_users can modify these fields.
//          */
//         if (canEdit) {
//           payload.email =
//             form.email;

//           payload.first_name =
//             form.first_name;

//           payload.last_name =
//             form.last_name;

//           if (form.password) {
//             payload.password =
//               form.password;
//           }

//           /*
//            * Username is intentionally not changed here.
//            * Keep the existing backend behavior.
//            */
//         }

//         /*
//          * -----------------------------------------------
//          * ROLE
//          * -----------------------------------------------
//          */
//         if (
//           canChangeRoles &&
//           form.role !==
//             editingUser.role
//         ) {
//           payload.role =
//             form.role;
//         }

//         /*
//          * -----------------------------------------------
//          * ACTIVE / INACTIVE
//          * -----------------------------------------------
//          */
//         if (
//           canToggleActive &&
//           form.is_active !==
//             editingUser.is_active
//         ) {
//           payload.is_active =
//             form.is_active;
//         }

//         /*
//          * No permitted field was changed.
//          */
//         if (
//           Object.keys(payload)
//             .length === 0
//         ) {
//           setShowForm(false);
//           return;
//         }

//         await usersApi.update(
//           editingUser.id,
//           payload
//         );
//       } else {
//         /*
//          * ======================================================
//          * CREATE NEW USER
//          * ======================================================
//          */
//         if (!canCreate) {
//           setError(
//             "You do not have permission to create users."
//           );
//           return;
//         }

//         if (!form.password) {
//           throw new Error(
//             "Password is required for a new user."
//           );
//         }

//         /*
//          * Non-admin users cannot create an admin.
//          */
//         if (
//           form.role === "admin" &&
//           !actorIsAdmin
//         ) {
//           setError(
//             "Only admins can assign the admin role."
//           );
//           return;
//         }

//         /*
//          * If the creator does not have
//          * change_user_roles, create the account
//          * using the safe default role.
//          */
//         const createPayload: UserPayload =
//           {
//             ...form,
//             role: canChangeRoles
//               ? form.role
//               : "viewer",
//           };

//         /*
//          * If the creator cannot activate/deactivate
//          * accounts, keep the new account active.
//          */
//         if (!canToggleActive) {
//           createPayload.is_active =
//             true;
//         }

//         await usersApi.create(
//           createPayload
//         );
//       }

//       setShowForm(false);

//       setEditingUser(null);

//       await loadUsers();
//     } catch (caught: any) {
//       const response =
//         caught?.response?.data;

//       setError(
//         response
//           ? Object.values(response)
//               .flat()
//               .join(" ")
//           : caught?.message ||
//               "Unable to save user."
//       );
//     } finally {
//       setSaving(false);
//     }
//   };

//   /*
//    * ============================================================
//    * DELETE USER
//    * ============================================================
//    */
//   const removeUser = async (
//     targetUser: AdminUser
//   ) => {
//     if (!canDelete) {
//       setError(
//         "You do not have permission to delete users."
//       );
//       return;
//     }

//     if (isProtected(targetUser)) {
//       setError(
//         "You do not have permission to delete this administrator."
//       );
//       return;
//     }

//     if (
//       !window.confirm(
//         `Delete user ${targetUser.username}?`
//       )
//     ) {
//       return;
//     }

//     try {
//       setError("");

//       await usersApi.delete(
//         targetUser.id
//       );

//       setUsers((current) =>
//         current.filter(
//           (item) =>
//             item.id !==
//             targetUser.id
//         )
//       );
//     } catch (caught: any) {
//       setError(
//         caught?.response?.data
//           ?.detail ||
//           "Unable to delete user."
//       );
//     }
//   };

//   /*
//    * ============================================================
//    * PAGE
//    * ============================================================
//    */
//   return (
//     <div className="space-y-6">
//       {/* ======================================================
//           HEADER
//       ====================================================== */}
//       <PageHeader
//         title="User Management"
//         subtitle=""
//         actions={
//           <div className="flex items-center gap-2">
//             <button
//               type="button"
//               onClick={loadUsers}
//               className="btn-ghost flex items-center gap-2"
//               disabled={
//                 loading ||
//                 !canViewUsers
//               }
//             >
//               <RefreshCw
//                 size={14}
//                 className={
//                   loading
//                     ? "animate-spin"
//                     : ""
//                 }
//               />
//               Refresh
//             </button>

//             {canCreate && (
//               <button
//                 type="button"
//                 onClick={
//                   openCreate
//                 }
//                 className="btn-primary flex items-center gap-2"
//               >
//                 <Plus size={14} />
//                 Add user
//               </button>
//             )}
//           </div>
//         }
//       />

//       {/* ======================================================
//           ERROR
//       ====================================================== */}
//       {error && (
//         <div className="flex items-center gap-2 text-sm text-down">
//           <AlertTriangle
//             size={14}
//           />

//           <span>{error}</span>

//           {canViewUsers && (
//             <button
//               type="button"
//               onClick={
//                 loadUsers
//               }
//               className="underline"
//             >
//               Retry
//             </button>
//           )}
//         </div>
//       )}

//       {/* ======================================================
//           NO VIEW USERS
//       ====================================================== */}
//       {!canViewUsers && (
//         <div className="card flex flex-col items-center gap-2 py-12 text-center">
//           <AlertTriangle
//             size={24}
//             className="text-text-muted"
//           />

//           <p className="text-sm text-text-primary">
//             You do not have permission
//             to view users.
//           </p>

//           <p className="text-xs text-text-muted">
//             Contact an administrator if
//             you need access to User
//             Management.
//           </p>
//         </div>
//       )}

//       {/* ======================================================
//           SEARCH + COUNT
//       ====================================================== */}
//       {canViewUsers && (
//         <>
//           <div className="flex flex-wrap items-center justify-between gap-3">
//             <div className="relative w-full max-w-md">
//               <Search
//                 size={14}
//                 className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
//               />

//               <input
//                 value={search}
//                 onChange={(event) =>
//                   setSearch(
//                     event.target
//                       .value
//                   )
//                 }
//                 placeholder="Search users"
//                 className="w-full rounded-lg border border-bg-border bg-bg-card py-2 pl-9 pr-3 text-sm text-text-primary"
//               />
//             </div>

//             <span className="text-xs text-text-muted">
//               {
//                 filteredUsers.length
//               }{" "}
//               of{" "}
//               {users.length}{" "}
//               users
//             </span>
//           </div>

//           {/* ==================================================
//               LOADING
//           ================================================== */}
//           {loading &&
//             users.length ===
//               0 && (
//               <p className="text-text-secondary">
//                 Loading users...
//               </p>
//             )}

//           {/* ==================================================
//               EMPTY
//           ================================================== */}
//           {!loading &&
//             !error &&
//             users.length ===
//               0 && (
//               <div className="card flex flex-col items-center gap-2 py-12 text-center">
//                 <UserRound
//                   size={24}
//                   className="text-text-muted"
//                 />

//                 <p className="text-sm text-text-primary">
//                   No users found
//                 </p>

//                 <p className="text-xs text-text-muted">
//                   The database does not
//                   contain any users yet.
//                 </p>
//               </div>
//             )}

//           {/* ==================================================
//               USER TABLE
//           ================================================== */}
//           {users.length > 0 && (
//             <div className="card overflow-x-auto">
//               <table className="w-full min-w-[760px] text-sm">
//                 <thead>
//                   <tr className="border-b border-bg-border text-text-secondary">
//                     <th className="py-3 text-left font-medium">
//                       User
//                     </th>

//                     <th className="py-3 text-left font-medium">
//                       Email
//                     </th>

//                     <th className="py-3 text-left font-medium">
//                       Role
//                     </th>

//                     <th className="py-3 text-left font-medium">
//                       Status
//                     </th>

//                     <th className="py-3 text-left font-medium">
//                       Joined
//                     </th>

//                     <th className="py-3 text-left font-medium">
//                       Last login
//                     </th>

//                     <th className="py-3 text-right font-medium">
//                       Actions
//                     </th>
//                   </tr>
//                 </thead>

//                 <tbody>
//                   {filteredUsers.map(
//                     (targetUser) => (
//                       <tr
//                         key={
//                           targetUser.id
//                         }
//                         className="table-row"
//                       >
//                         {/* USER */}
//                         <td className="py-3">
//                           <div className="flex items-center gap-3">
//                             <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-glow text-accent-light">
//                               <UserRound
//                                 size={
//                                   14
//                                 }
//                               />
//                             </div>

//                             <div>
//                               <p className="font-medium text-text-primary">
//                                 {[
//                                   targetUser.first_name,
//                                   targetUser.last_name,
//                                 ]
//                                   .filter(
//                                     Boolean
//                                   )
//                                   .join(
//                                     " "
//                                   ) ||
//                                   targetUser.username}
//                               </p>

//                               <p className="text-xs text-text-muted">
//                                 @
//                                 {
//                                   targetUser.username
//                                 }
//                               </p>
//                             </div>
//                           </div>
//                         </td>

//                         {/* EMAIL */}
//                         <td className="py-3 text-text-secondary">
//                           {
//                             targetUser.email ||
//                             "—"
//                           }
//                         </td>

//                         {/* ROLE */}
//                         <td className="py-3">
//                           <Badge
//                             variant={
//                               roleColors[
//                                 targetUser
//                                   .role
//                               ]
//                             }
//                           >
//                             {
//                               targetUser.role
//                             }
//                           </Badge>
//                         </td>

//                         {/* STATUS */}
//                         <td className="py-3">
//                           <Badge
//                             variant={
//                               targetUser.is_active
//                                 ? "green"
//                                 : "red"
//                             }
//                           >
//                             {targetUser.is_active
//                               ? "Active"
//                               : "Inactive"}
//                           </Badge>
//                         </td>

//                         {/* JOINED */}
//                         <td className="py-3 text-text-secondary">
//                           {targetUser.date_joined
//                             ? new Date(
//                                 targetUser.date_joined
//                               ).toLocaleDateString()
//                             : "—"}
//                         </td>

//                         {/* LAST LOGIN */}
//                         <td className="py-3 text-text-secondary">
//                           {targetUser.last_login
//                             ? new Date(
//                                 targetUser.last_login
//                               ).toLocaleString()
//                             : "Never"}
//                         </td>

//                         {/* ACTIONS */}
//                         <td className="py-3">
//                           <div className="flex justify-end gap-1">
//                             {canOpenEditor &&
//                               !isProtected(
//                                 targetUser
//                               ) && (
//                                 <button
//                                   type="button"
//                                   onClick={() =>
//                                     openEdit(
//                                       targetUser
//                                     )
//                                   }
//                                   className="p-2 text-text-muted hover:text-accent-light"
//                                   title="Edit user"
//                                 >
//                                   <Edit3
//                                     size={
//                                       14
//                                     }
//                                   />
//                                 </button>
//                               )}

//                             {canDelete &&
//                               !isProtected(
//                                 targetUser
//                               ) && (
//                                 <button
//                                   type="button"
//                                   onClick={() =>
//                                     removeUser(
//                                       targetUser
//                                     )
//                                   }
//                                   className="p-2 text-text-muted hover:text-down"
//                                   title="Delete user"
//                                 >
//                                   <Trash2
//                                     size={
//                                       14
//                                     }
//                                   />
//                                 </button>
//                               )}
//                           </div>
//                         </td>
//                       </tr>
//                     )
//                   )}
//                 </tbody>
//               </table>

//               {!loading &&
//                 filteredUsers.length ===
//                   0 && (
//                   <p className="py-8 text-center text-sm text-text-muted">
//                     No users match this
//                     search.
//                   </p>
//                 )}
//             </div>
//           )}
//         </>
//       )}

//       {/* ======================================================
//           CREATE / EDIT MODAL
//       ====================================================== */}
//       {showForm && (
//         <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
//           <form
//             onSubmit={saveUser}
//             className="w-full max-w-lg space-y-4 rounded-xl border border-bg-border bg-bg-secondary p-6 shadow-2xl"
//           >
//             {/* MODAL HEADER */}
//             <div className="flex items-center justify-between">
//               <h2 className="text-lg font-semibold text-text-primary">
//                 {editingUser
//                   ? "Edit user"
//                   : "Add user"}
//               </h2>

//               <button
//                 type="button"
//                 onClick={() => {
//                   if (!saving) {
//                     setShowForm(
//                       false
//                     );
//                     setEditingUser(
//                       null
//                     );
//                   }
//                 }}
//                 className="text-text-muted hover:text-text-primary"
//                 title="Close"
//               >
//                 <X size={18} />
//               </button>
//             </div>

//             {/* FORM FIELDS */}
//             <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
//               {/* USERNAME */}
//               <label className="text-xs text-text-secondary">
//                 Username

//                 <input
//                   required
//                   disabled={
//                     !!editingUser
//                   }
//                   value={
//                     form.username
//                   }
//                   onChange={(
//                     event
//                   ) =>
//                     setForm({
//                       ...form,
//                       username:
//                         event
//                           .target
//                           .value,
//                     })
//                   }
//                   className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary disabled:opacity-60"
//                 />
//               </label>

//               {/* EMAIL */}
//               <label className="text-xs text-text-secondary">
//                 Email

//                 <input
//                   required
//                   disabled={
//                     !!editingUser &&
//                     !canEdit
//                   }
//                   type="email"
//                   value={
//                     form.email
//                   }
//                   onChange={(
//                     event
//                   ) =>
//                     setForm({
//                       ...form,
//                       email:
//                         event
//                           .target
//                           .value,
//                     })
//                   }
//                   className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary disabled:opacity-60"
//                 />
//               </label>

//               {/* FIRST NAME */}
//               <label className="text-xs text-text-secondary">
//                 First name

//                 <input
//                   disabled={
//                     !!editingUser &&
//                     !canEdit
//                   }
//                   value={
//                     form.first_name
//                   }
//                   onChange={(
//                     event
//                   ) =>
//                     setForm({
//                       ...form,
//                       first_name:
//                         event
//                           .target
//                           .value,
//                     })
//                   }
//                   className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary disabled:opacity-60"
//                 />
//               </label>

//               {/* LAST NAME */}
//               <label className="text-xs text-text-secondary">
//                 Last name

//                 <input
//                   disabled={
//                     !!editingUser &&
//                     !canEdit
//                   }
//                   value={
//                     form.last_name
//                   }
//                   onChange={(
//                     event
//                   ) =>
//                     setForm({
//                       ...form,
//                       last_name:
//                         event
//                           .target
//                           .value,
//                     })
//                   }
//                   className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary disabled:opacity-60"
//                 />
//               </label>

//               {/* PASSWORD */}
//               <label className="text-xs text-text-secondary">
//                 Password

//                 <input
//                   required={
//                     !editingUser
//                   }
//                   disabled={
//                     !!editingUser &&
//                     !canEdit
//                   }
//                   type="password"
//                   value={
//                     form.password
//                   }
//                   onChange={(
//                     event
//                   ) =>
//                     setForm({
//                       ...form,
//                       password:
//                         event
//                           .target
//                           .value,
//                     })
//                   }
//                   className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary disabled:opacity-60"
//                   placeholder={
//                     editingUser
//                       ? "Leave blank to keep current"
//                       : ""
//                   }
//                 />
//               </label>

//               {/* ROLE */}
//               {canChangeRoles && (
//                 <label className="text-xs text-text-secondary">
//                   Role

//                   <select
//                     value={
//                       form.role
//                     }
//                     onChange={(
//                       event
//                     ) =>
//                       setForm({
//                         ...form,
//                         role:
//                           event
//                             .target
//                             .value as Role,
//                       })
//                     }
//                     className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary"
//                   >
//                     <option value="viewer">
//                       Viewer
//                     </option>

//                     <option value="analyst">
//                       Analyst
//                     </option>

//                     {actorIsAdmin && (
//                       <option value="admin">
//                         Admin
//                       </option>
//                     )}
//                   </select>
//                 </label>
//               )}
//             </div>

//             {/* ACTIVE */}
//             {canToggleActive && (
//               <label className="flex items-center gap-2 text-sm text-text-secondary">
//                 <input
//                   type="checkbox"
//                   checked={
//                     form.is_active
//                   }
//                   onChange={(
//                     event
//                   ) =>
//                     setForm({
//                       ...form,
//                       is_active:
//                         event
//                           .target
//                           .checked,
//                     })
//                   }
//                 />

//                 Active account
//               </label>
//             )}

//             {/* ERROR */}
//             {error && (
//               <p className="text-sm text-down">
//                 {error}
//               </p>
//             )}

//             {/* FOOTER */}
//             <div className="flex justify-end gap-2">
//               <button
//                 type="button"
//                 onClick={() => {
//                   if (!saving) {
//                     setShowForm(
//                       false
//                     );
//                     setEditingUser(
//                       null
//                     );
//                   }
//                 }}
//                 disabled={saving}
//                 className="btn-ghost"
//               >
//                 Cancel
//               </button>

//               <button
//                 type="submit"
//                 disabled={
//                   saving ||
//                   (!editingUser &&
//                     !canCreate)
//                 }
//                 className="btn-primary"
//               >
//                 {saving
//                   ? "Saving..."
//                   : "Save user"}
//               </button>
//             </div>
//           </form>
//         </div>
//       )}
//     </div>
//   );
// }

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  AlertTriangle,
  Building2,
  Check,
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
  getUserCompanyAccess,
  saveUserCompanyAccess,
  type AdminUser,
  type BuiltInRole as Role,
  type UserPayload,
  type UserCompanyAccess,
} from "../../api/users";

import {
  rolesApi,
  type CustomRoleSummary,
} from "../../api/roles";

import { useAuth } from "../../contexts/AuthContext";


const roleColors: Record<
  Role,
  "red" | "purple" | "gray"
> = {
  admin: "red",
  analyst: "purple",
  viewer: "gray",
};


export default function UserManagementPage() {
  const {
    hasPermission,
    user: me,
  } = useAuth();

  const actorIsAdmin = me?.role === "admin";

  /*
   * ---------------------------------------------------------
   * Permissions
   * ---------------------------------------------------------
   */

  const canViewUsers = hasPermission("view_users");
  const canCreate = hasPermission("create_users");
  const canEdit = hasPermission("edit_users");
  const canDelete = hasPermission("delete_users");
  const canChangeRoles = hasPermission("change_user_roles");
  const canToggleActive = hasPermission("activate_users");

  /*
   * Backend company-access API uses:
   *
   * permission_key = "edit_users"
   *
   * Therefore company access management requires edit_users.
   */
  const canManageCompanyAccess = canEdit;

  const canOpenEditor =
    canEdit ||
    canChangeRoles ||
    canToggleActive;


  /*
   * ---------------------------------------------------------
   * User management state
   * ---------------------------------------------------------
   */

  const [users, setUsers] = useState<AdminUser[]>([]);

  const [search, setSearch] = useState("");

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState("");

  const [saving, setSaving] = useState(false);

  const [editingUser, setEditingUser] =
    useState<AdminUser | null>(null);

  const [showForm, setShowForm] = useState(false);

  const [form, setForm] = useState<UserPayload>({
    username: "",
    email: "",
    first_name: "",
    last_name: "",
    password: "",
    role: "viewer",
    custom_role_id: null,
    is_active: true,
  });

  const [customRoles, setCustomRoles] = useState<
    CustomRoleSummary[]
  >([]);


  /*
   * ---------------------------------------------------------
   * Company access state
   * ---------------------------------------------------------
   */

  const [companyAccessUser, setCompanyAccessUser] =
    useState<AdminUser | null>(null);

  const [companyAccess, setCompanyAccess] =
    useState<UserCompanyAccess[]>([]);

  const [companyAccessLoading, setCompanyAccessLoading] =
    useState(false);

  const [companyAccessSaving, setCompanyAccessSaving] =
    useState(false);

  const [companyAccessSearch, setCompanyAccessSearch] =
    useState("");

  const [companyAccessError, setCompanyAccessError] =
    useState("");

  const [companyAccessSuccess, setCompanyAccessSuccess] =
    useState("");


  /*
   * ---------------------------------------------------------
   * Load users
   * ---------------------------------------------------------
   */

  const loadUsers = useCallback(async () => {
    if (!canViewUsers) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError("");

      const response = await usersApi.list();

      setUsers(response);
    } catch (err: any) {
      console.error("Failed to load users:", err);

      setError(
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        "Failed to load users."
      );
    } finally {
      setLoading(false);
    }
  }, [canViewUsers]);

  const loadRoles = useCallback(async () => {
    try {
      const response = await rolesApi.getRoles();

      setCustomRoles(
        response.custom_roles.filter(
          (role) => role.is_active
        )
      );
    } catch (err: any) {
      console.error("Failed to load roles:", err);

      setCustomRoles([]);
    }
  }, []);


  useEffect(() => {
    void loadUsers();
    void loadRoles();
  }, [loadUsers, loadRoles]);


  /*
   * ---------------------------------------------------------
   * Search users
   * ---------------------------------------------------------
   */

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) {
      return users;
    }

    return users.filter((user) => {
      const fullName =
        `${user.first_name || ""} ${user.last_name || ""}`
          .trim()
          .toLowerCase();

      return (
        user.username?.toLowerCase().includes(query) ||
        user.email?.toLowerCase().includes(query) ||
        fullName.includes(query) ||
        user.role?.toLowerCase().includes(query)
      );
    });
  }, [users, search]);


  /*
   * ---------------------------------------------------------
   * Admin protection
   * ---------------------------------------------------------
   *
   * Non-admin users cannot modify admin accounts.
   */

  const isProtected = (target: AdminUser) => {
    return target.role === "admin" && !actorIsAdmin;
  };

  const roleValue = form.custom_role_id
    ? `custom:${form.custom_role_id}`
    : form.role;

  const selectRole = (value: string) => {
    if (value.startsWith("custom:")) {
      const customRoleId = Number(value.slice("custom:".length));

      if (Number.isNaN(customRoleId)) {
        return;
      }

      setForm((current) => ({
        ...current,
        role: "viewer",
        custom_role_id: customRoleId,
      }));
      return;
    }

    setForm((current) => ({
      ...current,
      role: value as Role,
      custom_role_id: null,
    }));
  };


  /*
   * ---------------------------------------------------------
   * Create user
   * ---------------------------------------------------------
   */

  const openCreate = () => {
    if (!canCreate) {
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
      custom_role_id: null,
      is_active: true,
    });

    void loadRoles();



    setError("");
    setShowForm(true);
  };


  /*
   * ---------------------------------------------------------
   * Edit user
   * ---------------------------------------------------------
   */

  const openEdit = (target: AdminUser) => {
    if (!canOpenEditor) {
      return;
    }

    if (isProtected(target)) {
      setError("You cannot modify an administrator account.");
      return;
    }

    setEditingUser(target);

    setForm({
      username: target.username || "",
      email: target.email || "",
      first_name: target.first_name || "",
      last_name: target.last_name || "",
      password: "",
      role: target.role,
      custom_role_id: target.custom_role_id ?? null,
      is_active: target.is_active,
    });

    setError("");
    setShowForm(true);
  };


  /*
   * ---------------------------------------------------------
   * Save user
   * ---------------------------------------------------------
   */

  const saveUser = async () => {
    if (!editingUser && !canCreate) {
      return;
    }

    if (editingUser && !canOpenEditor) {
      return;
    }

    if (
      editingUser &&
      isProtected(editingUser)
    ) {
      setError(
        "You cannot modify an administrator account."
      );
      return;
    }

    try {
      setSaving(true);
      setError("");

      const payload: UserPayload = {
        ...form,
      };

      /*
       * When editing an existing user, don't send
       * an empty password.
       */
      if (
        editingUser &&
        !payload.password?.trim()
      ) {
        delete payload.password;
      }

      if (editingUser) {
        await usersApi.update(
          editingUser.id,
          payload
        );
      } else {
        await usersApi.create(payload);
      }

      setShowForm(false);
      setEditingUser(null);

      await loadUsers();
    } catch (err: any) {
      console.error("Failed to save user:", err);

      setError(
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        "Failed to save user."
      );
    } finally {
      setSaving(false);
    }
  };


  /*
   * ---------------------------------------------------------
   * Delete user
   * ---------------------------------------------------------
   */

  const removeUser = async (target: AdminUser) => {
    if (!canDelete) {
      return;
    }

    if (isProtected(target)) {
      setError(
        "You cannot delete an administrator account."
      );
      return;
    }

    const confirmed = window.confirm(
      `Are you sure you want to delete "${target.username}"?`
    );

    if (!confirmed) {
      return;
    }

    try {
      setError("");

      await usersApi.remove(target.id);

      await loadUsers();
    } catch (err: any) {
      console.error("Failed to delete user:", err);

      setError(
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        "Failed to delete user."
      );
    }
  };


  /*
   * ---------------------------------------------------------
   * Open company access modal
   * ---------------------------------------------------------
   */

  const openCompanyAccess = async (
    targetUser: AdminUser
  ) => {
    if (!canManageCompanyAccess) {
      return;
    }

    if (isProtected(targetUser)) {
      setError(
        "You cannot manage company access for an administrator account."
      );
      return;
    }

    setCompanyAccessUser(targetUser);

    setCompanyAccess([]);
    setCompanyAccessSearch("");

    setCompanyAccessError("");
    setCompanyAccessSuccess("");

    setCompanyAccessLoading(true);

    try {
      const response =
        await getUserCompanyAccess(targetUser.id);

      setCompanyAccess(
        response.company_access || []
      );
    } catch (err: any) {
      console.error(
        "Failed to load company access:",
        err
      );

      setCompanyAccessError(
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        "Failed to load company access."
      );
    } finally {
      setCompanyAccessLoading(false);
    }
  };


  /*
   * ---------------------------------------------------------
   * Close company access modal
   * ---------------------------------------------------------
   */

  const closeCompanyAccess = () => {
    if (companyAccessSaving) {
      return;
    }

    setCompanyAccessUser(null);
    setCompanyAccess([]);
    setCompanyAccessSearch("");
    setCompanyAccessError("");
    setCompanyAccessSuccess("");
  };


  /*
   * ---------------------------------------------------------
   * Toggle individual company
   * ---------------------------------------------------------
   */

  const toggleCompanyAccess = (
    companyId: number
  ) => {
    setCompanyAccess((current) =>
      current.map((company) =>
        company.company_id === companyId
          ? {
              ...company,
              status:
                company.status === 1
                  ? 0
                  : 1,
            }
          : company
      )
    );

    setCompanyAccessSuccess("");
  };


  /*
   * ---------------------------------------------------------
   * Enable all companies
   * ---------------------------------------------------------
   */

  const enableAllCompanies = () => {
    setCompanyAccess((current) =>
      current.map((company) => ({
        ...company,
        status: 1,
      }))
    );

    setCompanyAccessSuccess("");
  };


  /*
   * ---------------------------------------------------------
   * Disable all companies
   * ---------------------------------------------------------
   */

  const disableAllCompanies = () => {
    setCompanyAccess((current) =>
      current.map((company) => ({
        ...company,
        status: 0,
      }))
    );

    setCompanyAccessSuccess("");
  };


  /*
   * ---------------------------------------------------------
   * Save company access
   * ---------------------------------------------------------
   */

  const saveCompanyAccess = async () => {
    if (!companyAccessUser) {
      return;
    }

    if (!canManageCompanyAccess) {
      return;
    }

    try {
      setCompanyAccessSaving(true);

      setCompanyAccessError("");
      setCompanyAccessSuccess("");

      const payload = companyAccess.map(
        (company) => ({
          company_id: company.company_id,
          status: company.status,
        })
      );

      const response =
        await saveUserCompanyAccess(
          companyAccessUser.id,
          payload
        );

      setCompanyAccess(
        response.company_access || []
      );

      setCompanyAccessSuccess(
        "Company access saved successfully."
      );
    } catch (err: any) {
      console.error(
        "Failed to save company access:",
        err
      );

      setCompanyAccessError(
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        "Failed to save company access."
      );
    } finally {
      setCompanyAccessSaving(false);
    }
  };


  /*
   * ---------------------------------------------------------
   * Filter companies
   * ---------------------------------------------------------
   */

  const filteredCompanyAccess =
    useMemo(() => {
      const query =
        companyAccessSearch
          .trim()
          .toLowerCase();

      if (!query) {
        return companyAccess;
      }

      return companyAccess.filter(
        (company) =>
          company.company_name
            ?.toLowerCase()
            .includes(query) ||
          company.company_symbol
            ?.toLowerCase()
            .includes(query)
      );
    }, [
      companyAccess,
      companyAccessSearch,
    ]);


  /*
   * ---------------------------------------------------------
   * Enabled company count
   * ---------------------------------------------------------
   */

  const enabledCompanyCount =
    companyAccess.filter(
      (company) => company.status === 1
    ).length;


  /*
   * ---------------------------------------------------------
   * Permission denied screen
   * ---------------------------------------------------------
   */

  if (!canViewUsers) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="User Management"
          subtitle="Manage system users and access."
        />

        <div className="card p-8 text-center">
          <AlertTriangle
            size={32}
            className="mx-auto mb-3 text-text-muted"
          />

          <h3 className="text-lg font-semibold text-text-primary">
            Access denied
          </h3>

          <p className="mt-2 text-sm text-text-secondary">
            You do not have permission to view users.
          </p>
        </div>
      </div>
    );
  }


  /*
   * ---------------------------------------------------------
   * Main UI
   * ---------------------------------------------------------
   */

  return (
    <div className="space-y-6">

      {/* =====================================================
          PAGE HEADER
          ===================================================== */}

      <PageHeader
        title="User Management"
        subtitle="Manage users, roles, status and company access."
      />


      {/* =====================================================
          TOP TOOLBAR
          ===================================================== */}

      <div className="card p-4">

        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">

          {/* Search */}

          <div className="relative w-full lg:max-w-md">

            <Search
              size={17}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
            />

            <input
              type="text"
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Search users..."
              className="w-full rounded-lg border border-bg-border bg-bg-secondary py-2.5 pl-10 pr-4 text-sm text-text-primary outline-none focus:border-accent"
            />

          </div>


          {/* Right controls */}

          <div className="flex items-center gap-2">

            <button
              type="button"
              onClick={loadUsers}
              disabled={loading}
              className="btn-ghost inline-flex items-center gap-2"
              title="Refresh users"
            >
              <RefreshCw
                size={16}
                className={
                  loading
                    ? "animate-spin"
                    : ""
                }
              />

              <span className="hidden sm:inline">
                Refresh
              </span>
            </button>


            {canCreate && (
              <button
                type="button"
                onClick={openCreate}
                className="btn-primary inline-flex items-center gap-2"
              >
                <Plus size={16} />

                <span>
                  Add User
                </span>
              </button>
            )}

          </div>

        </div>

      </div>


      {/* =====================================================
          ERROR
          ===================================================== */}

      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-red-500/20 bg-red-500/10 p-4">

          <AlertTriangle
            size={18}
            className="mt-0.5 shrink-0 text-red-400"
          />

          <div className="flex-1">

            <p className="text-sm text-red-300">
              {error}
            </p>

          </div>

          <button
            type="button"
            onClick={() => setError("")}
            className="text-red-300 hover:text-red-200"
          >
            <X size={16} />
          </button>

        </div>
      )}


      {/* =====================================================
          USER TABLE
          ===================================================== */}

      <div className="card overflow-hidden">

        <div className="overflow-x-auto">

          <table className="w-full">

            <thead>
              <tr className="border-b border-bg-border text-left">

                <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-text-muted">
                  User
                </th>

                <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-text-muted">
                  Email
                </th>

                <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-text-muted">
                  Role
                </th>

                <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-text-muted">
                  Status
                </th>

                <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-text-muted">
                  Joined
                </th>

                <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-text-muted">
                  Last Login
                </th>

                <th className="px-5 py-4 text-right text-xs font-medium uppercase tracking-wide text-text-muted">
                  Actions
                </th>

              </tr>
            </thead>


            <tbody>

              {loading ? (

                <tr>

                  <td
                    colSpan={7}
                    className="px-5 py-12 text-center"
                  >
                    <RefreshCw
                      size={24}
                      className="mx-auto mb-3 animate-spin text-text-muted"
                    />

                    <p className="text-sm text-text-secondary">
                      Loading users...
                    </p>
                  </td>

                </tr>

              ) : filteredUsers.length === 0 ? (

                <tr>

                  <td
                    colSpan={7}
                    className="px-5 py-12 text-center"
                  >

                    <UserRound
                      size={28}
                      className="mx-auto mb-3 text-text-muted"
                    />

                    <p className="text-sm text-text-secondary">
                      No users found.
                    </p>

                  </td>

                </tr>

              ) : (

                filteredUsers.map((targetUser) => {

                  const protectedUser =
                    isProtected(targetUser);

                  return (
                    <tr
                      key={targetUser.id}
                      className="table-row border-b border-bg-border last:border-b-0"
                    >

                      {/* User */}

                      <td className="px-5 py-4">

                        <div className="flex items-center gap-3">

                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-bg-secondary">

                            <UserRound
                              size={17}
                              className="text-text-muted"
                            />

                          </div>

                          <div className="min-w-0">

                            <p className="truncate text-sm font-medium text-text-primary">
                              {targetUser.first_name ||
                              targetUser.last_name
                                ? `${targetUser.first_name || ""} ${targetUser.last_name || ""}`.trim()
                                : targetUser.username}
                            </p>

                            <p className="truncate text-xs text-text-muted">
                              @{targetUser.username}
                            </p>

                          </div>

                        </div>

                      </td>


                      {/* Email */}

                      <td className="px-5 py-4">

                        <span className="text-sm text-text-secondary">
                          {targetUser.email || "—"}
                        </span>

                      </td>


                      {/* Role */}

                      <td className="px-5 py-4">

                        <Badge
                          variant={
                            roleColors[
                              targetUser.role
                            ]
                          }
                        >
                          {targetUser.role}
                        </Badge>

                      </td>


                      {/* Status */}

                      <td className="px-5 py-4">

                        <Badge
                          variant={
                            targetUser.is_active
                              ? "green"
                              : "gray"
                          }
                        >
                          {targetUser.is_active
                            ? "Active"
                            : "Inactive"}
                        </Badge>

                      </td>


                      {/* Joined */}

                      <td className="px-5 py-4">

                        <span className="text-sm text-text-secondary">
                          {targetUser.date_joined
                            ? new Date(
                                targetUser.date_joined
                              ).toLocaleDateString()
                            : "—"}
                        </span>

                      </td>


                      {/* Last login */}

                      <td className="px-5 py-4">

                        <span className="text-sm text-text-secondary">
                          {targetUser.last_login
                            ? new Date(
                                targetUser.last_login
                              ).toLocaleDateString()
                            : "Never"}
                        </span>

                      </td>


                      {/* Actions */}

                      <td className="px-5 py-4">

                        <div className="flex justify-end gap-1">

                          {/* Company Access */}

                          {canManageCompanyAccess &&
                            !protectedUser && (
                              <button
                                type="button"
                                onClick={() =>
                                  openCompanyAccess(
                                    targetUser
                                  )
                                }
                                className="rounded-md p-2 text-text-muted transition hover:bg-bg-secondary hover:text-accent-light"
                                title="Manage company access"
                              >
                                <Building2
                                  size={15}
                                />
                              </button>
                            )}


                          {/* Edit */}

                          {canOpenEditor &&
                            !protectedUser && (
                              <button
                                type="button"
                                onClick={() =>
                                  openEdit(
                                    targetUser
                                  )
                                }
                                className="rounded-md p-2 text-text-muted transition hover:bg-bg-secondary hover:text-accent-light"
                                title="Edit user"
                              >
                                <Edit3
                                  size={15}
                                />
                              </button>
                            )}


                          {/* Delete */}

                          {canDelete &&
                            !protectedUser && (
                              <button
                                type="button"
                                onClick={() =>
                                  removeUser(
                                    targetUser
                                  )
                                }
                                className="rounded-md p-2 text-text-muted transition hover:bg-bg-secondary hover:text-red-400"
                                title="Delete user"
                              >
                                <Trash2
                                  size={15}
                                />
                              </button>
                            )}

                        </div>

                      </td>

                    </tr>
                  );
                })

              )}

            </tbody>

          </table>

        </div>

      </div>


      {/* =====================================================
          CREATE / EDIT USER MODAL
          ===================================================== */}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">

          <div className="w-full max-w-lg rounded-xl border border-bg-border bg-bg-card shadow-2xl">

            {/* Header */}

            <div className="flex items-center justify-between border-b border-bg-border px-6 py-4">

              <div>

                <h2 className="text-lg font-semibold text-text-primary">
                  {editingUser
                    ? "Edit User"
                    : "Create User"}
                </h2>

                <p className="mt-1 text-xs text-text-muted">
                  {editingUser
                    ? "Update user information and permissions."
                    : "Create a new system user."}
                </p>

              </div>

              <button
                type="button"
                onClick={() =>
                  setShowForm(false)
                }
                disabled={saving}
                className="rounded-md p-2 text-text-muted hover:bg-bg-secondary hover:text-text-primary"
              >
                <X size={18} />
              </button>

            </div>


            {/* Form */}

            <div className="space-y-4 px-6 py-5">

              {/* Username */}

              <div>

                <label className="mb-1.5 block text-sm font-medium text-text-primary">
                  Username
                </label>

                <input
                  type="text"
                  value={form.username}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      username:
                        event.target.value,
                    }))
                  }
                  disabled={!!editingUser}
                  className="w-full rounded-lg border border-bg-border bg-bg-secondary px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent disabled:cursor-not-allowed disabled:opacity-60"
                  placeholder="Enter username"
                />

              </div>


              {/* Email */}

              <div>

                <label className="mb-1.5 block text-sm font-medium text-text-primary">
                  Email
                </label>

                <input
                  type="email"
                  value={form.email}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      email:
                        event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-bg-border bg-bg-secondary px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent"
                  placeholder="Enter email"
                />

              </div>


              {/* First / Last name */}

              <div className="grid grid-cols-2 gap-3">

                <div>

                  <label className="mb-1.5 block text-sm font-medium text-text-primary">
                    First Name
                  </label>

                  <input
                    type="text"
                    value={form.first_name}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        first_name:
                          event.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-bg-border bg-bg-secondary px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent"
                    placeholder="First name"
                  />

                </div>


                <div>

                  <label className="mb-1.5 block text-sm font-medium text-text-primary">
                    Last Name
                  </label>

                  <input
                    type="text"
                    value={form.last_name}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        last_name:
                          event.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-bg-border bg-bg-secondary px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent"
                    placeholder="Last name"
                  />

                </div>

              </div>


              {/* Password */}

              <div>

                <label className="mb-1.5 block text-sm font-medium text-text-primary">
                  {editingUser
                    ? "New Password"
                    : "Password"}
                </label>

                <input
                  type="password"
                  value={form.password || ""}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      password:
                        event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-bg-border bg-bg-secondary px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent"
                  placeholder={
                    editingUser
                      ? "Leave blank to keep current password"
                      : "Enter password"
                  }
                />

              </div>


              {/* Role */}

              <div>

                <label className="mb-1.5 block text-sm font-medium text-text-primary">
                  Role
                </label>

                <select
                  value={roleValue}
                  disabled={
                    !canChangeRoles
                  }
                  onChange={(event) =>
                    selectRole(
                      event.target.value
                    )
                  }
                  className="w-full rounded-lg border border-bg-border bg-bg-secondary px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <optgroup label="System Roles">
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

              </div>


              {/* Active */}

              <label className="flex cursor-pointer items-center gap-3">

                <input
                  type="checkbox"
                  checked={form.is_active}
                  disabled={
                    !canToggleActive
                  }
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      is_active:
                        event.target.checked,
                    }))
                  }
                  className="h-4 w-4 rounded border-bg-border"
                />

                <div>

                  <p className="text-sm font-medium text-text-primary">
                    Active account
                  </p>

                  <p className="text-xs text-text-muted">
                    Allow this user to log into the system.
                  </p>

                </div>

              </label>

            </div>


            {/* Footer */}

            <div className="flex justify-end gap-2 border-t border-bg-border px-6 py-4">

              <button
                type="button"
                onClick={() =>
                  setShowForm(false)
                }
                disabled={saving}
                className="btn-ghost"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={saveUser}
                disabled={saving}
                className="btn-primary inline-flex items-center gap-2"
              >

                {saving && (
                  <RefreshCw
                    size={15}
                    className="animate-spin"
                  />
                )}

                {editingUser
                  ? "Save Changes"
                  : "Create User"}

              </button>

            </div>

          </div>

        </div>
      )}


      {/* =====================================================
          COMPANY ACCESS MODAL
          ===================================================== */}

      {companyAccessUser && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">

          <div className="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-xl border border-bg-border bg-bg-card shadow-2xl">

            {/* =================================================
                HEADER
                ================================================= */}

            <div className="flex items-center justify-between border-b border-bg-border px-6 py-4">

              <div className="flex items-center gap-3">

                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-light">

                  <Building2
                    size={19}
                    className="text-accent"
                  />

                </div>

                <div>

                  <h2 className="text-lg font-semibold text-text-primary">
                    Company Access
                  </h2>

                  <p className="text-xs text-text-muted">
                    Manage which companies this user can access.
                  </p>

                </div>

              </div>


              <button
                type="button"
                onClick={closeCompanyAccess}
                disabled={companyAccessSaving}
                className="rounded-md p-2 text-text-muted hover:bg-bg-secondary hover:text-text-primary"
              >
                <X size={18} />
              </button>

            </div>


            {/* =================================================
                USER INFORMATION
                ================================================= */}

            <div className="border-b border-bg-border px-6 py-4">

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">

                <div>

                  <p className="text-sm font-medium text-text-primary">
                    {companyAccessUser.first_name ||
                    companyAccessUser.last_name
                      ? `${companyAccessUser.first_name || ""} ${companyAccessUser.last_name || ""}`.trim()
                      : companyAccessUser.username}
                  </p>

                  <p className="mt-0.5 text-xs text-text-muted">
                    @{companyAccessUser.username}
                    {companyAccessUser.email
                      ? ` • ${companyAccessUser.email}`
                      : ""}
                  </p>

                </div>


                <div className="rounded-lg bg-bg-secondary px-3 py-2">

                  <p className="text-xs text-text-muted">
                    Companies enabled
                  </p>

                  <p className="text-sm font-semibold text-text-primary">
                    {enabledCompanyCount}
                    {" / "}
                    {companyAccess.length}
                  </p>

                </div>

              </div>

            </div>


            {/* =================================================
                SEARCH + BULK ACTIONS
                ================================================= */}

            <div className="border-b border-bg-border px-6 py-4">

              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">

                {/* Search */}

                <div className="relative w-full lg:max-w-sm">

                  <Search
                    size={16}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
                  />

                  <input
                    type="text"
                    value={companyAccessSearch}
                    onChange={(event) =>
                      setCompanyAccessSearch(
                        event.target.value
                      )
                    }
                    placeholder="Search company or symbol..."
                    className="w-full rounded-lg border border-bg-border bg-bg-secondary py-2.5 pl-9 pr-3 text-sm text-text-primary outline-none focus:border-accent"
                  />

                </div>


                {/* Bulk buttons */}

                <div className="flex flex-wrap gap-2">

                  <button
                    type="button"
                    onClick={
                      enableAllCompanies
                    }
                    disabled={
                      companyAccessLoading ||
                      companyAccessSaving ||
                      companyAccess.length === 0
                    }
                    className="btn-ghost inline-flex items-center gap-2"
                  >
                    <Check size={15} />
                    Enable All
                  </button>


                  <button
                    type="button"
                    onClick={
                      disableAllCompanies
                    }
                    disabled={
                      companyAccessLoading ||
                      companyAccessSaving ||
                      companyAccess.length === 0
                    }
                    className="btn-ghost inline-flex items-center gap-2"
                  >
                    <X size={15} />
                    Disable All
                  </button>

                </div>

              </div>

            </div>


            {/* =================================================
                ERROR / SUCCESS
                ================================================= */}

            {(companyAccessError ||
              companyAccessSuccess) && (
              <div className="px-6 pt-4">

                {companyAccessError && (
                  <div className="flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3">

                    <AlertTriangle
                      size={16}
                      className="mt-0.5 shrink-0 text-red-400"
                    />

                    <p className="text-sm text-red-300">
                      {companyAccessError}
                    </p>

                  </div>
                )}


                {companyAccessSuccess && (
                  <div className="flex items-center gap-2 rounded-lg border border-green-500/20 bg-green-500/10 p-3">

                    <Check
                      size={16}
                      className="text-green-400"
                    />

                    <p className="text-sm text-green-300">
                      {companyAccessSuccess}
                    </p>

                  </div>
                )}

              </div>
            )}


            {/* =================================================
                COMPANY TABLE
                ================================================= */}

            <div className="min-h-0 flex-1 overflow-auto px-6 py-4">

              {companyAccessLoading ? (

                <div className="flex min-h-[250px] items-center justify-center">

                  <div className="text-center">

                    <RefreshCw
                      size={25}
                      className="mx-auto mb-3 animate-spin text-text-muted"
                    />

                    <p className="text-sm text-text-secondary">
                      Loading company access...
                    </p>

                  </div>

                </div>

              ) : companyAccess.length === 0 ? (

                <div className="flex min-h-[250px] items-center justify-center">

                  <div className="text-center">

                    <Building2
                      size={30}
                      className="mx-auto mb-3 text-text-muted"
                    />

                    <p className="text-sm font-medium text-text-primary">
                      No companies available
                    </p>

                    <p className="mt-1 text-xs text-text-muted">
                      There are no active companies available for access management.
                    </p>

                  </div>

                </div>

              ) : filteredCompanyAccess.length === 0 ? (

                <div className="flex min-h-[200px] items-center justify-center">

                  <div className="text-center">

                    <Search
                      size={26}
                      className="mx-auto mb-3 text-text-muted"
                    />

                    <p className="text-sm text-text-secondary">
                      No companies match your search.
                    </p>

                  </div>

                </div>

              ) : (

                <div className="overflow-hidden rounded-lg border border-bg-border">

                  <table className="w-full">

                    <thead>

                      <tr className="border-b border-bg-border bg-bg-secondary">

                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-text-muted">
                          Company
                        </th>

                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-text-muted">
                          Symbol
                        </th>

                        <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wide text-text-muted">
                          Access
                        </th>

                      </tr>

                    </thead>


                    <tbody>

                      {filteredCompanyAccess.map(
                        (company) => {

                          const enabled =
                            company.status ===
                            1;

                          return (
                            <tr
                              key={
                                company.company_id
                              }
                              className="border-b border-bg-border last:border-b-0"
                            >

                              {/* Company */}

                              <td className="px-4 py-3">

                                <div className="flex items-center gap-3">

                                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-bg-secondary">

                                    <Building2
                                      size={15}
                                      className="text-text-muted"
                                    />

                                  </div>

                                  <span className="text-sm font-medium text-text-primary">
                                    {
                                      company.company_name
                                    }
                                  </span>

                                </div>

                              </td>


                              {/* Symbol */}

                              <td className="px-4 py-3">

                                <span className="rounded-md bg-bg-secondary px-2 py-1 text-xs font-medium text-text-secondary">
                                  {
                                    company.company_symbol
                                  }
                                </span>

                              </td>


                              {/* Toggle */}

                              <td className="px-4 py-3">

                                <div className="flex justify-center">

                                  <button
                                    type="button"
                                    onClick={() =>
                                      toggleCompanyAccess(
                                        company.company_id
                                      )
                                    }
                                    disabled={
                                      companyAccessSaving
                                    }
                                    className={`relative h-6 w-11 rounded-full transition ${
                                      enabled
                                        ? "bg-accent"
                                        : "bg-bg-border"
                                    } ${
                                      companyAccessSaving
                                        ? "cursor-not-allowed opacity-60"
                                        : ""
                                    }`}
                                    aria-label={
                                      enabled
                                        ? `Disable ${company.company_name}`
                                        : `Enable ${company.company_name}`
                                    }
                                  >

                                    <span
                                      className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${
                                        enabled
                                          ? "left-6"
                                          : "left-1"
                                      }`}
                                    />

                                  </button>

                                </div>

                              </td>

                            </tr>
                          );
                        }
                      )}

                    </tbody>

                  </table>

                </div>

              )}

            </div>


            {/* =================================================
                FOOTER
                ================================================= */}

            <div className="flex flex-col gap-3 border-t border-bg-border px-6 py-4 sm:flex-row sm:items-center sm:justify-between">

              <p className="text-xs text-text-muted">

                {enabledCompanyCount}{" "}
                {enabledCompanyCount === 1
                  ? "company"
                  : "companies"}{" "}
                currently enabled.

              </p>


              <div className="flex justify-end gap-2">

                <button
                  type="button"
                  onClick={closeCompanyAccess}
                  disabled={
                    companyAccessSaving
                  }
                  className="btn-ghost"
                >
                  Cancel
                </button>


                <button
                  type="button"
                  onClick={saveCompanyAccess}
                  disabled={
                    companyAccessSaving ||
                    companyAccessLoading ||
                    !companyAccessUser
                  }
                  className="btn-primary inline-flex items-center gap-2"
                >

                  {companyAccessSaving && (
                    <RefreshCw
                      size={15}
                      className="animate-spin"
                    />
                  )}

                  Save Access

                </button>

              </div>

            </div>

          </div>

        </div>
      )}

    </div>
  );
}