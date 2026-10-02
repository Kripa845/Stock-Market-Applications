import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  TrendingUp,
  Newspaper,
  BarChart3,
  Activity,
  Landmark,
  Briefcase,
  Star,
  Database,
  Settings,
  Radio,
  ChevronLeft,
  ChevronRight,
  Users,
  ShieldCheck,
  Gauge,
} from 'lucide-react';
import clsx from 'clsx';
import { useAuth } from '../../contexts/AuthContext';
import { ROUTE_RULES } from '../../config/routePermissions';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  label: string;
  icon?: React.ComponentType<{ size?: number; className?: string }>;
  to?: string;
  type?: 'divider';
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
  },
  {
    label: 'Tracked Companies',
    icon: Gauge,
    to: '/tracked',
  },
  {
    label: 'Companies',
    icon: Briefcase,
    to: '/companies',
  },
  {
    label: 'Company Analysis',
    icon: Activity,
    to: '/company-analysis',
  },
  {
    label: 'Broker Analysis',
    icon: Landmark,
    to: '/broker-analysis',
    requiredPermissions: ['view_analysis'],
  },
  {
    label: 'Watchlist',
    icon: Star,
    to: '/watchlist',
    requiredPermissions: ['view_watchlist'],
  },
  {
    label: 'Comparison',
    icon: BarChart3,
    to: '/watchlist-comparison',
    requiredPermissions: ['view_analysis'],
  },

  { type: 'divider', label: 'News' },

  {
    label: 'News Feed',
    icon: Newspaper,
    to: '/news',
  },

  { type: 'divider', label: 'Data Collection' },

  {
    label: 'Crawl Management',
    icon: Radio,
    to: '/crawl',
  },

  { type: 'divider', label: 'Reports' },

  {
    label: 'Reports',
    icon: Database,
    to: '/reports',
    requiredPermissions: ['export_reports'],
  },

  { type: 'divider', label: 'Administration' },

  {
    label: 'User Management',
    icon: Users,
    to: '/users',
  },
  {
    label: 'Roles & Permissions',
    icon: ShieldCheck,
    to: '/roles-permissions',
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { pathname } = useLocation();
  const { hasAnyPermission, hasAllPermissions } = useAuth();

  const canSeeItem = (item: NavItem): boolean => {
    const rule = item.to ? ROUTE_RULES[item.to] : undefined;
    if (!rule) return true;
    return rule.mode === 'all' ? hasAllPermissions(rule.permissions) : hasAnyPermission(rule.permissions);
  };

  const isActive = (to: string): boolean => {
    if (to === '/dashboard') return pathname === '/dashboard';
    return pathname === to || pathname.startsWith(to + '/');
  };

  return (
    <aside
      className={clsx(
        'sidebar-wrap flex flex-col h-full bg-bg-secondary border-r border-bg-border transition-all duration-300',
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
