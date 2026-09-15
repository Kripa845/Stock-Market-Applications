import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Edit3, Plus, RefreshCw, Search, Trash2, UserRound, X } from 'lucide-react';
import PageHeader from '../../components/common/PageHeader';
import Badge from '../../components/common/Badge';
import { usersApi, type AdminUser } from '../../api/users';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';
import type { Role, UserPayload } from '../../api/users';

const roleColors = {
  admin: 'red',
  analyst: 'purple',
  viewer: 'gray',
} as const;

export default function UserManagementPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<UserPayload>({
    username: '', email: '', first_name: '', last_name: '', password: '', role: 'viewer', is_active: true,
  });

  const loadUsers = useCallback(() => {
    setLoading(true);
    usersApi.list()
      .then(setUsers)
      .catch(() => setError('Unable to load users from the database.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadUsers(); }, [loadUsers]);
  useLiveRefresh(loadUsers, 10000);

  const normalizedSearch = search.trim().toLowerCase();
  const filteredUsers = users.filter((user) =>
    [user.username, user.email, user.first_name, user.last_name, user.role]
      .some((value) => value.toLowerCase().includes(normalizedSearch)),
  );

  const openCreate = () => {
    setEditingUser(null);
    setForm({ username: '', email: '', first_name: '', last_name: '', password: '', role: 'viewer', is_active: true });
    setError('');
    setShowForm(true);
  };

  const openEdit = (user: AdminUser) => {
    setEditingUser(user);
    setForm({ username: user.username, email: user.email, first_name: user.first_name, last_name: user.last_name, password: '', role: user.role, is_active: user.is_active });
    setError('');
    setShowForm(true);
  };

  const saveUser = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      if (editingUser) {
        const { password, ...withoutPassword } = form;
        await usersApi.update(editingUser.id, password ? form : withoutPassword);
      } else {
        if (!form.password) throw new Error('Password is required for a new user.');
        await usersApi.create(form);
      }
      setShowForm(false);
      await loadUsers();
    } catch (caught: any) {
      const response = caught?.response?.data;
      setError(response ? Object.values(response).flat().join(' ') : caught.message || 'Unable to save user.');
    } finally {
      setSaving(false);
    }
  };

  const removeUser = async (user: AdminUser) => {
    if (!window.confirm(`Delete user ${user.username}?`)) return;
    try {
      setError('');
      await usersApi.delete(user.id);
      setUsers(current => current.filter(item => item.id !== user.id));
    } catch (caught: any) {
      setError(caught?.response?.data?.detail || 'Unable to delete user.');
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="User Management"
        subtitle=""
        actions={
          <div className="flex items-center gap-2">
            <button onClick={loadUsers} className="btn-ghost flex items-center gap-2" disabled={loading}><RefreshCw size={14} className={loading ? 'animate-spin' : ''} />Refresh</button>
            <button onClick={openCreate} className="btn-primary flex items-center gap-2"><Plus size={14} />Add user</button>
          </div>
        }
      />

      {error && (
        <div className="flex items-center gap-2 text-sm text-down">
          <AlertTriangle size={14} />
          {error}
          <button onClick={loadUsers} className="underline">Retry</button>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative w-full max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search users"
            className="w-full bg-bg-card border border-bg-border rounded-lg pl-9 pr-3 py-2 text-sm text-text-primary"
          />
        </div>
        <span className="text-xs text-text-muted">{filteredUsers.length} of {users.length} users</span>
      </div>

      {loading && users.length === 0 && <p className="text-text-secondary">Loading users...</p>}
      {!loading && !error && users.length === 0 && (
        <div className="card flex flex-col items-center gap-2 py-12 text-center">
          <UserRound size={24} className="text-text-muted" />
          <p className="text-sm text-text-primary">No users found</p>
          <p className="text-xs text-text-muted">The database does not contain any users yet.</p>
        </div>
      )}

      {users.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-bg-border text-text-secondary">
                <th className="text-left py-3 font-medium">User</th>
                <th className="text-left py-3 font-medium">Email</th>
                <th className="text-left py-3 font-medium">Role</th>
                <th className="text-left py-3 font-medium">Status</th>
                <th className="text-left py-3 font-medium">Joined</th>
                <th className="text-left py-3 font-medium">Last login</th>
                <th className="text-right py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((user) => (
                <tr key={user.id} className="table-row">
                  <td className="py-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-glow text-accent-light">
                        <UserRound size={14} />
                      </div>
                      <div>
                        <p className="font-medium text-text-primary">
                          {[user.first_name, user.last_name].filter(Boolean).join(' ') || user.username}
                        </p>
                        <p className="text-xs text-text-muted">@{user.username}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 text-text-secondary">{user.email || '—'}</td>
                  <td className="py-3"><Badge variant={roleColors[user.role]}>{user.role}</Badge></td>
                  <td className="py-3"><Badge variant={user.is_active ? 'green' : 'red'}>{user.is_active ? 'Active' : 'Inactive'}</Badge></td>
                  <td className="py-3 text-text-secondary">{user.date_joined ? new Date(user.date_joined).toLocaleDateString() : '—'}</td>
                  <td className="py-3 text-text-secondary">{user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}</td>
                  <td className="py-3"><div className="flex justify-end gap-1"><button onClick={() => openEdit(user)} className="p-2 text-text-muted hover:text-accent-light" title="Edit user"><Edit3 size={14} /></button><button onClick={() => removeUser(user)} className="p-2 text-text-muted hover:text-down" title="Delete user"><Trash2 size={14} /></button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && filteredUsers.length === 0 && <p className="py-8 text-center text-sm text-text-muted">No users match this search.</p>}
        </div>
      )}

      {showForm && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"><form onSubmit={saveUser} className="w-full max-w-lg space-y-4 rounded-xl border border-bg-border bg-bg-secondary p-6 shadow-2xl"><div className="flex items-center justify-between"><h2 className="text-lg font-semibold text-text-primary">{editingUser ? 'Edit user' : 'Add user'}</h2><button type="button" onClick={() => setShowForm(false)} className="text-text-muted hover:text-text-primary" title="Close"><X size={18} /></button></div><div className="grid grid-cols-1 sm:grid-cols-2 gap-3"><label className="text-xs text-text-secondary">Username<input required value={form.username} onChange={event => setForm({ ...form, username: event.target.value })} className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary" /></label><label className="text-xs text-text-secondary">Email<input required type="email" value={form.email} onChange={event => setForm({ ...form, email: event.target.value })} className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary" /></label><label className="text-xs text-text-secondary">First name<input value={form.first_name} onChange={event => setForm({ ...form, first_name: event.target.value })} className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary" /></label><label className="text-xs text-text-secondary">Last name<input value={form.last_name} onChange={event => setForm({ ...form, last_name: event.target.value })} className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary" /></label><label className="text-xs text-text-secondary">Password<input required={!editingUser} type="password" value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary" placeholder={editingUser ? 'Leave blank to keep current' : ''} /></label><label className="text-xs text-text-secondary">Role<select value={form.role} onChange={event => setForm({ ...form, role: event.target.value as Role })} className="mt-1 w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary"><option value="viewer">Viewer</option><option value="analyst">Analyst</option><option value="admin">Admin</option></select></label></div><label className="flex items-center gap-2 text-sm text-text-secondary"><input type="checkbox" checked={form.is_active} onChange={event => setForm({ ...form, is_active: event.target.checked })} />Active account</label>{error && <p className="text-sm text-down">{error}</p>}<div className="flex justify-end gap-2"><button type="button" onClick={() => setShowForm(false)} className="btn-ghost">Cancel</button><button type="submit" disabled={saving} className="btn-primary">{saving ? 'Saving...' : 'Save user'}</button></div></form></div>}
    </div>
  );
}
