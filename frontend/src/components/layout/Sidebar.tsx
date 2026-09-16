import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  TrendingUp,
  Newspaper,
  BarChart3,
  Activity,
  LineChart,
  Briefcase,
  Star,
  BookOpen,
  Database,
  
  Settings,
  Radio,
  ChevronLeft,
  ChevronRight,
  Zap,
  Users,
  ShieldCheck,
} from "lucide-react";
import clsx from "clsx";
import { useAuth } from "../../contexts/AuthContext";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  label: string;
  icon?: any;
  to?: string;
  type?: "divider";
  requiredPermissions?: string[];
}

// One permission mapping is shared by every role-specific layout.  Roles pick
// the URL namespace only; permission data decides whether an item is visible.
const PATH_PERMISSIONS: Record<string, string[]> = {
  "/admin": ["view_analysis"],
  "/analyst": ["view_analysis"],
  "/viewer": ["view_analysis"],
  "/admin/companies": ["view_companies", "manage_tracked_companies"],
  "/admin/watchlist": ["view_watchlist", "add_watchlist"],
  "/admin/users": ["view_users", "create_users", "edit_users"],
  "/admin/roles-permissions": ["view_roles", "edit_roles"],
  "/admin/news": ["view_news", "categorize_news", "correct_categories"],
  "/admin/crawl": ["view_crawl_runs", "run_crawler"],
  "/analyst/market": ["view_market_data"],
  "/viewer/market": ["view_market_data"],
  "/analyst/stocks": ["view_companies"],
  "/viewer/stocks": ["view_companies"],
  "/analyst/trading": ["view_market_data"],
  "/viewer/trading": ["view_market_data"],
  "/analyst/analytics": ["view_analysis"],
  "/viewer/analytics": ["view_analysis"],
  "/analyst/news": ["view_news"],
  "/viewer/news": ["view_news"],
  "/analyst/news-review": ["correct_categories", "categorize_news"],
  "/analyst/watchlist": ["view_watchlist"],
  "/viewer/watchlist": ["view_watchlist"],
  "/analyst/reports": ["view_reports", "export_reports"],
  "/viewer/reports": ["view_reports"],
};

/* =========================
   ADMIN NAVIGATION
   ========================= */

const ADMIN_NAV: NavItem[] = [
  {
    label: "Dashboard",
    icon: LayoutDashboard,
    to: "/admin",
  },

  {
    type: "divider",
    label: "Management",
  },

  {
    label: "Companies",
    icon: Briefcase,
    to: "/admin/companies",
    requiredPermissions: ["view_companies", "manage_tracked_companies"],
  },

  {
    label: "Watchlist",
    icon: Star,
    to: "/admin/watchlist",
    requiredPermissions: ["view_watchlist", "add_watchlist"],
  },

  {
    label: "User Management",
    icon: Users,
    to: "/admin/users",
    requiredPermissions: ["view_users", "create_users", "edit_users"],
  },

  {
    label: "Roles & Permissions",
    icon: ShieldCheck,
    to: "/admin/roles-permissions",
    requiredPermissions: ["view_roles", "edit_roles"],
  },

  {
    type: "divider",
    label: "News & Data",
  },

  {
    label: "News Review",
    icon: Newspaper,
    to: "/admin/news",
    requiredPermissions: ["view_news", "categorize_news", "correct_categories"],
  },

  {
    label: "Crawl Management",
    icon: Radio,
    to: "/admin/crawl",
    requiredPermissions: ["view_crawl_runs", "run_crawler"],
  },

  {
    type: "divider",
    label: "System",
  },

  {
    label: "Settings",
    icon: Settings,
    to: "/admin/settings",
  },
];

/* =========================
   ANALYST NAVIGATION
   ========================= */

const ANALYST_NAV: NavItem[] = [
  {
    label: "Dashboard",
    icon: LayoutDashboard,
    to: "/analyst",
  },

  {
    type: "divider",
    label: "Market",
  },

  {
    label: "Market Overview",
    icon: TrendingUp,
    to: "/analyst/market",
  },

  {
    label: "Stocks",
    icon: LineChart,
    to: "/analyst/stocks",
  },

  {
    label: "Trading Behavior",
    icon: Activity,
    to: "/analyst/trading",
  },

  {
    label: "Analytics",
    icon: BarChart3,
    to: "/analyst/analytics",
  },

  {
    type: "divider",
    label: "News",
  },

  {
    label: "News",
    icon: Newspaper,
    to: "/analyst/news",
  },

  {
    label: "News Review",
    icon: BookOpen,
    to: "/analyst/news-review",
  },

  {
    type: "divider",
    label: "Comparison",
  },

  {
    label: "Watchlist Comparison",
    icon: Star,
    to: "/analyst/watchlist",
  },

  {
    type: "divider",
    label: "Reports",
  },

  {
    label: "Export Reports",
    icon: Database,
    to: "/analyst/reports",
  },

  {
    type: "divider",
    label: "System",
  },

  {
    label: "Settings",
    icon: Settings,
    to: "/analyst/settings",
  },
];

/* =========================
   VIEWER NAVIGATION
   ========================= */

const VIEWER_NAV: NavItem[] = [
  {
    label: "Dashboard",
    icon: LayoutDashboard,
    to: "/viewer",
  },

  {
    type: "divider",
    label: "Market",
  },

  {
    label: "Market Overview",
    icon: TrendingUp,
    to: "/viewer/market",
  },

  {
    label: "Stocks",
    icon: LineChart,
    to: "/viewer/stocks",
  },

  {
    label: "Trading Behavior",
    icon: Activity,
    to: "/viewer/trading",
  },

  {
    label: "Analytics",
    icon: BarChart3,
    to: "/viewer/analytics",
  },

  {
    type: "divider",
    label: "News",
  },

  {
    label: "News",
    icon: Newspaper,
    to: "/viewer/news",
  },

  {
    type: "divider",
    label: "Comparison",
  },

  {
    label: "Watchlist Comparison",
    icon: Star,
    to: "/viewer/watchlist",
  },

  {
    type: "divider",
    label: "Reports",
  },

  {
    label: "Reports",
    icon: BookOpen,
    to: "/viewer/reports",
  },

  {
    type: "divider",
    label: "System",
  },

  {
    label: "Settings",
    icon: Settings,
    to: "/viewer/settings",
  },
];

/* =========================
   SIDEBAR COMPONENT
   ========================= */

export default function Sidebar({
  collapsed,
  onToggle,
}: SidebarProps) {
  const { pathname } = useLocation();
  const { user, hasAnyPermission } = useAuth();

  const canSeeItem = (item: NavItem): boolean => {
    const required = item.requiredPermissions || (item.to ? PATH_PERMISSIONS[item.to] : undefined);
    if (!required || required.length === 0) {
      return true;
    }

    // Admin always has access
    if (user?.role === "admin") {
      return true;
    }

    return hasAnyPermission(required);
  };

  /*
   * Select navigation based on current URL.
   *
   * /admin/*   -> Admin sidebar
   * /analyst/* -> Analyst sidebar
   * /viewer/*  -> Viewer sidebar
   */

  let NAV: NavItem[] = VIEWER_NAV;

  if (pathname.startsWith("/admin")) {
    NAV = ADMIN_NAV.filter((item) => item.type === "divider" || canSeeItem(item));
  } else if (pathname.startsWith("/analyst")) {
    NAV = ANALYST_NAV;
  } else if (pathname.startsWith("/viewer")) {
    NAV = VIEWER_NAV;
  }

  NAV = NAV.filter((item) => item.type === "divider" || canSeeItem(item));

  return (
    <aside
      className={clsx(
        "flex flex-col bg-bg-secondary border-r border-bg-border transition-all duration-300 shrink-0 z-20",
        collapsed ? "w-14" : "w-56"
      )}
    >
      {/* =========================
          LOGO
         ========================= */}

      <div className="flex items-center gap-3 h-14 px-4 border-b border-bg-border shrink-0">
        <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center shrink-0">
          <Zap size={14} className="text-white" />
        </div>

        {!collapsed && (
          <span className="font-bold text-sm text-text-primary tracking-wide whitespace-nowrap">
            StockScope
          </span>
        )}
      </div>

      {/* =========================
          NAVIGATION
         ========================= */}

      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {NAV.map((item, i) => {
          /* =========================
             DIVIDER
             ========================= */

          if ("type" in item && item.type === "divider") {
            return (
              <div
                key={`divider-${i}`}
                className="pt-4 pb-1"
              >
                {!collapsed && (
                  <span className="px-2 text-[10px] font-semibold uppercase tracking-widest text-text-muted">
                    {item.label}
                  </span>
                )}

                {collapsed && (
                  <div className="h-px bg-bg-border mx-1" />
                )}
              </div>
            );
          }

          /* =========================
             NAVIGATION ITEM
             ========================= */

          const Icon = item.icon;

          if (!item.to || !Icon) {
            return null;
          }

          /*
           * Dashboard should only be active
           * when we are exactly on:
           *
           * /admin
           * /analyst
           * /viewer
           */

          const isDashboard =
            item.to === "/admin" ||
            item.to === "/analyst" ||
            item.to === "/viewer";

          const isActive = isDashboard
            ? pathname === item.to
            : pathname.startsWith(item.to);

          return (
            <NavLink
              key={`${item.to}-${i}`}
              to={item.to}
              className={clsx(
                "nav-item",
                isActive && "active",
                collapsed && "justify-center px-2"
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon
                size={16}
                className="shrink-0"
              />

              {!collapsed && (
                <span className="truncate">
                  {item.label}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* =========================
          COLLAPSE TOGGLE
         ========================= */}

      <button
        onClick={onToggle}
        className="flex items-center justify-center h-10 border-t border-bg-border text-text-muted hover:text-text-primary hover:bg-bg-elevated transition-colors"
      >
        {collapsed ? (
          <ChevronRight size={15} />
        ) : (
          <ChevronLeft size={15} />
        )}
      </button>
    </aside>
  );
}
