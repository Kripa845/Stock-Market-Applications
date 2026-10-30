import { useEffect, useState } from 'react';
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
  ChevronDown,
  Users,
  ShieldCheck,
  Trophy,
  Search,
  Zap,
  ScrollText,
  Gift,
  List,
  FileSpreadsheet,
  ChartColumnStacked,
  CalendarDays,
  CalendarRange,
  LayoutGrid,
  Grid3x3
} from 'lucide-react';
import clsx from 'clsx';
import { useAuth } from '../../contexts/AuthContext';
import { ROUTE_RULES } from '../../config/routePermissions';
import { TOP_LIST_PAGES } from '../market/TopListControls';
import { SECTOR_CODES, SECTOR_LABELS } from '../../api/quarterlyReports';

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
  /** Active only on this exact path, not on its sub-pages. */
  end?: boolean;
  /** Sub-pages shown in a dropdown under this item. */
  children?: NavItem[];
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

  // { type: 'divider', label: 'Market' },

  {
    label: 'Market Overview',
    icon: TrendingUp,
    to: '/market',
    end: true,
    children: TOP_LIST_PAGES,
  },
  {
    label: 'Indices',
    icon: BarChart3,
    to: '/market/indices',
  },
  {
    label: 'Proposed Dividend',
    icon: Gift,
    to: '/market/dividends',
  },
  {
    label: 'Market Calendar',
    icon: CalendarDays,
    to: '/market/calendar',
  },
  {
    label: 'Weekday Summary',
    icon: CalendarRange,
    to: '/market/weekdays',
  },
  {
    label: 'NEPSE Day by Day',
    icon: LayoutGrid,
    to: '/market/day-by-day',
  },
  {
    label: 'Latest Report',
    icon: FileSpreadsheet,
    to: '/market/quarterly-report',
    end: true,
    children: SECTOR_CODES.map((code) => ({
      label: SECTOR_LABELS[code],
      to: `/market/quarterly-report/${code.toLowerCase()}`,
    })),
  },
  {
    label: 'Companies',
    icon: Briefcase,
    to: '/companies',
  },
  {
    label: 'Technical Charts',
    icon: Activity,
    to: '/technical-charts',
  },
  {
    label: 'Floorsheet',
    icon: ScrollText,
    to: '/floorsheet',
    end: true,
  },
  {
    label: 'Floor Sheet Summary',
    icon: Grid3x3,
    to: '/floorsheet/summary',
  },
  {
    label: 'Broker Analysis',
    icon: Landmark,
    requiredPermissions: ['view_analysis'],
    children: [
      { label: 'Top Brokers', icon: Trophy, to: '/top-brokers' },
      { label: 'Broker Explorer', icon: Search, to: '/broker-analysis' },
      { label: 'Broker List', icon: List, to: '/brokers' },
      { label: 'Broker Accumulation & Distribution', icon: ChartColumnStacked, to: '/broker-acc-dist' },
      { label: 'Broker Acc / Dist Chart', icon: Activity, to: '/broker-position' },
    ],
  },
  {
    label: 'Watchlist',
    icon: Star,
    to: '/watchlist',
    requiredPermissions: ['view_watchlist'],
  },
  {
    label: 'Live Trading',
    icon: Zap,
    to: '/live-trading',
    requiredPermissions: ['view_watchlist'],
  },
  {
    label: 'Comparison',
    icon: BarChart3,
    to: '/watchlist-comparison',
    requiredPermissions: ['view_analysis'],
  },

  // { type: 'divider', label: 'News' },
  {
    label: 'News Feed',
    icon: Newspaper,
    to: '/news',
  },

  // { type: 'divider', label: 'Data Collection' },

  {
    label: 'Crawl Management',
    icon: Radio,
    to: '/crawl',
  },

  // { type: 'divider', label: 'Reports' },

  {
    label: 'Reports',
    icon: Database,
    to: '/reports',
    requiredPermissions: ['view_reports'],
  },

  // { type: 'divider', label: 'Administration' },

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

  const isActive = (to: string, end = false): boolean => {
    if (end || to === '/dashboard') return pathname === to;
    return pathname === to || pathname.startsWith(to + '/');
  };

  // Dropdowns: open while one of their sub-pages is showing, otherwise as the user left them.
  // A group without its own page (no `to`) is keyed by its label.
  const groupKey = (item: NavItem) => item.to ?? item.label;
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  useEffect(() => {
    NAV_ITEMS.forEach((item) => {
      if (item.children?.some((child) => child.to && isActive(child.to))) {
        const key = groupKey(item);
        setOpenGroups((groups) => (groups[key] ? groups : { ...groups, [key]: true }));
      }
    });
  }, [pathname]);

  const renderLink = (item: NavItem, sub = false) => {
    const Icon = item.icon;
    const active = item.to ? isActive(item.to, item.end) : false;
    return (
      <NavLink
        key={item.to}
        to={item.to!}
        title={collapsed ? item.label : undefined}
        className={clsx(
          'flex min-w-0 flex-1 items-center gap-3 px-2 py-2 rounded-lg text-sm transition-colors',
          sub && 'py-1.5 text-[13px]',
          active
            ? 'bg-accent/10 text-accent-light font-medium'
            : 'text-text-secondary hover:text-text-primary hover:bg-blue-500/10',
          collapsed && 'justify-center',
        )}
      >
        {Icon && (
          <Icon
            size={sub ? 15 : 17}
            className={clsx(
              'shrink-0',
              active ? 'text-accent-light' : 'text-text-muted',
            )}
          />
        )}
        {!collapsed && <span className="truncate">{item.label}</span>}
      </NavLink>
    );
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

          const children = (item.children ?? []).filter(canSeeItem);
          if (!children.length) return item.to ? renderLink(item) : null;
          // Collapsed: a group with its own page shows just that icon; one without shows its pages' icons.
          if (collapsed) return item.to ? renderLink(item) : children.map((child) => renderLink(child));

          const key = groupKey(item);
          const open = !!openGroups[key];
          const toggle = () => setOpenGroups((groups) => ({ ...groups, [key]: !open }));
          const chevron = <ChevronDown size={15} className={clsx('shrink-0 transition-transform', open && 'rotate-180')} />;
          const GroupIcon = item.icon;
          const childActive = children.some((child) => child.to && isActive(child.to));
          return (
            <div key={key}>
              {item.to ? (
                <div className="flex items-center gap-0.5">
                  {renderLink(item)}
                  <button
                    onClick={toggle}
                    aria-expanded={open}
                    aria-label={`${open ? 'Hide' : 'Show'} ${item.label} pages`}
                    className="rounded-lg p-2 text-text-muted transition-colors hover:bg-blue-500/10 hover:text-text-primary"
                  >
                    {chevron}
                  </button>
                </div>
              ) : (
                <button
                  onClick={toggle}
                  aria-expanded={open}
                  className={clsx(
                    'flex w-full items-center gap-3 px-2 py-2 rounded-lg text-sm transition-colors hover:bg-blue-500/10',
                    childActive ? 'text-accent-light font-medium' : 'text-text-secondary hover:text-text-primary',
                  )}
                >
                  {GroupIcon && <GroupIcon size={17} className={clsx('shrink-0', childActive ? 'text-accent-light' : 'text-text-muted')} />}
                  <span className="flex-1 truncate text-left">{item.label}</span>
                  {chevron}
                </button>
              )}
              {open && (
                <div className="ml-4 mt-0.5 space-y-0.5 border-l border-bg-border pl-2">
                  {children.map((child) => renderLink(child, true))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Footer — Settings link always visible */}
      <div className="border-t border-bg-border p-2">
        <NavLink
          to="/dashboard"
          title={collapsed ? 'Dashboard' : undefined}
          className={clsx(
            'flex items-center gap-3 px-2 py-2 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-blue-500/10 transition-colors',
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
