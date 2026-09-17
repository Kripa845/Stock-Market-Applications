import { Bell, Search, ChevronDown, User, LogOut } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';

export default function Header() {
  const [profileOpen, setProfileOpen] = useState(false);
  const { user, effectiveRole, logout } = useAuth();

  // Show effective role (may be a custom role name) with first+last name fallback
  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(' ') ||
    user?.username ||
    'User';

  const roleLabel =
    effectiveRole ??
    (user?.role
      ? user.role.charAt(0).toUpperCase() + user.role.slice(1)
      : 'User');

  const handleLogout = () => {
    logout();
  };

  return (
    <header className="h-14 bg-bg-secondary border-b border-bg-border flex items-center gap-4 px-6 shrink-0">
      {/* Search */}
      <div className="flex-1 max-w-md relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
        <input
          type="text"
          placeholder="Search stocks, companies, news…"
          className="w-full bg-bg-card border border-bg-border rounded-lg pl-8 pr-4 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
        />
      </div>

      <div className="flex items-center gap-3 ml-auto">
        {/* Notification */}
        <button className="relative p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors">
          <Bell size={16} />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-accent" />
        </button>

        {/* Profile */}
        <div className="relative">
          <button
            onClick={() => setProfileOpen(o => !o)}
            className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-lg hover:bg-bg-elevated transition-colors"
          >
            <div className="w-7 h-7 rounded-full bg-accent-dim flex items-center justify-center">
              <User size={14} className="text-accent-light" />
            </div>
            <span className="text-sm text-text-primary hidden sm:block">{displayName}</span>
            <ChevronDown size={12} className="text-text-muted" />
          </button>

          {profileOpen && (
            <div className="absolute right-0 top-10 w-52 bg-bg-elevated border border-bg-border rounded-xl py-1 z-50 shadow-xl">
              <div className="px-4 py-2 border-b border-bg-border">
                <p className="text-sm font-medium text-text-primary">{displayName}</p>
                <p className="text-xs text-text-muted mt-0.5">{roleLabel}</p>
              </div>
              <button className="w-full flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:text-text-primary hover:bg-bg-card transition-colors">
                <User size={13} /> Profile
              </button>
              <div className="h-px bg-bg-border my-1" />
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-4 py-2 text-sm text-down hover:bg-bg-card transition-colors"
              >
                <LogOut size={13} /> Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
