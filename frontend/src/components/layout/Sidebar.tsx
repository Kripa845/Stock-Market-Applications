import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  TrendingUp,
  Newspaper,
  BarChart3,
  Activity,
  Briefcase,
  Star,
  Database,
  Settings,
  Radio,
  ChevronLeft,
  ChevronRight,
  Users,
  ShieldCheck,
} from 'lucide-react';
import clsx from 'clsx';
import { useAuth } from '../../contexts/AuthContext';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  label: string;
  icon?: React.ComponentType<{ size?: number; className?: string }>;
  to?: string;
  type?: 'divider';
  /**
   * ALL of these permissions must be held (or the user is admin) for the item
   * to be visible.  When the array is empty / undefined the item is always
   * shown.
   */
  requiredPermissions?: string[];
}

// ---------------------------------------------------------------------------
// Single navigation list — permission-gated, shared by all roles.
// ---------------------------------------------------------------------------
const NAV_ITEMS: NavItem[] = [
  {
    label: 'Dashboard',
    icon: LayoutDashboard,
    to: '/dashboard',
  },

  { type: 'divider', label: 'Market' },

  {
    label: 'Market Overview',
    icon: TrendingUp,
    to: '/market',
    requiredPermissions: ['view_market_data'],
  },
  {
    label: 'Companies',
    icon: Briefcase,
    to: '/companies',
    requiredPermissions: ['view_companies'],
  },
  {
    label: 'Trading Behaviour',
    icon: Activity,
    to: '/trading',
    requiredPermissions: ['view_trading_volume'],
  },
  {
    label: 'Analytics',
    icon: BarChart3,
    to: '/analytics',
    requiredPermissions: ['view_analysis'],
  },
  {
    label: 'Watchlist',
    icon: Star,
    to: '/watchlist',
    requiredPermissions: ['view_watchlist'],
  },

  { type: 'divider', label: 'News' },

  {
    label: 'News Feed',
    icon: Newspaper,
    to: '/news',
    requiredPermissions: ['view_news'],
  },

  { type: 'divider', label: 'Data Collection' },

  {
    label: 'Crawl Management',
    icon: Radio,
    to: '/crawl',
    requiredPermissions: ['view_crawl_runs'],
  },

  { type: 'divider', label: 'Reports' },

  {
    label: 'Reports',
    icon: Database,
    to: '/reports',
    requiredPermissions: ['view_reports'],
  },

  { type: 'divider', label: 'Administration' },

  {
    label: 'User Management',
    icon: Users,
    to: '/users',
    requiredPermissions: ['view_users'],
  },
  {
    label: 'Roles & Permissions',
    icon: ShieldCheck,
    to: '/roles-permissions',
    requiredPermissions: ['view_roles'],
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { pathname } = useLocation();
  const { user, hasPermission } = useAuth();

  /**
   * Returns true if the current user is allowed to see this nav item.
   *
   * Logic:
   *  - Admin always sees everything.
   *  - Items with no requiredPermissions are always visible.
   *  - Otherwise the user must hold ALL listed permissions.
   */
  const canSeeItem = (item: NavItem): boolean => {
    const required = item.requiredPermissions;
    if (!required || required.length === 0) return true;
    if (user?.role === 'admin') return true;
    // Require ALL listed permissions (not ANY) — prevents showing nav items
    // the user only partially has access to.
    return required.every((p) => hasPermission(p));
  };

  const isActive = (to: string): boolean => {
    if (to === '/dashboard') return pathname === '/dashboard';
    return pathname === to || pathname.startsWith(to + '/');
  };

  return (
    <aside
      className={clsx(
        'flex flex-col h-full bg-bg-secondary border-r border-bg-border transition-all duration-300',
        collapsed ? 'w-16' : 'w-60',
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-bg-border min-h-[57px]">
        {!collapsed && (
          <span className="text-sm font-bold text-text-primary tracking-wide truncate">
            StockScope
          </span>
        )}
        <button
          onClick={onToggle}
          className="ml-auto text-text-muted hover:text-text-primary transition-colors"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {/* Nav Items */}
      <nav className="flex-1 overflow-y-auto py-3 space-y-0.5 px-2">
        {NAV_ITEMS.map((item, idx) => {
          if (item.type === 'divider') {
            if (collapsed) return null;
            return (
              <div
                key={`divider-${idx}`}
                className="pt-4 pb-1 px-2"
              >
                <span className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">
                  {item.label}
                </span>
              </div>
            );
          }

          if (!canSeeItem(item)) return null;

          const Icon = item.icon;
          const active = item.to ? isActive(item.to) : false;

          return (
            <NavLink
              key={item.to}
              to={item.to!}
              title={collapsed ? item.label : undefined}
              className={clsx(
                'flex items-center gap-3 px-2 py-2 rounded-lg text-sm transition-colors',
                active
                  ? 'bg-accent/10 text-accent-light font-medium'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated',
                collapsed && 'justify-center',
              )}
            >
              {Icon && (
                <Icon
                  size={17}
                  className={clsx(
                    'shrink-0',
                    active ? 'text-accent-light' : 'text-text-muted',
                  )}
                />
              )}
              {!collapsed && <span className="truncate">{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Footer — Settings link always visible */}
      <div className="border-t border-bg-border p-2">
        <NavLink
          to="/dashboard"
          title={collapsed ? 'Dashboard' : undefined}
          className={clsx(
            'flex items-center gap-3 px-2 py-2 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors',
            collapsed && 'justify-center',
          )}
        >
          <Settings size={17} className="shrink-0 text-text-muted" />
          {!collapsed && <span>Settings</span>}
        </NavLink>
      </div>
    </aside>
  );
}
