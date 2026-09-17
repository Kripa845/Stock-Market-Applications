import {
  Building2,
  Newspaper,
  Activity,
  Users,
  TrendingUp,
  LineChart,
  Radio,
  ShieldCheck,
  BarChart3,
  Star,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export type DashboardCardType = 'stat' | 'quick-action';

export interface DashboardCardData {
  id: string;
  title: string;
  description?: string;
  value?: string | number;
  dataPath?: string;
  route: string;
  icon: LucideIcon;
  type?: DashboardCardType;
  badge?: string;
  iconColor?: string;
  /**
   * The permission key the user must have for this card to appear.
   * If undefined the card is always shown (e.g. the dashboard itself).
   */
  requiredPermission?: string;
}

export interface DashboardSectionData {
  id: string;
  title: string;
  description?: string;
  cards: DashboardCardData[];
  /**
   * If supplied, at least one of these permissions must be held for the
   * entire section to be visible.
   */
  requiredAnyPermission?: string[];
}

export interface DashboardConfig {
  title: string;
  subtitle: string;
  sections: DashboardSectionData[];
}

// ---------------------------------------------------------------------------
// SINGLE PERMISSION-DRIVEN CONFIG
// Each card declares the permission required to see it.
// RoleDashboard filters cards at render time using the live permissions array.
// ---------------------------------------------------------------------------

export const universalDashboardConfig: DashboardConfig = {
  title: 'Dashboard',
  subtitle: 'Your personalised market intelligence overview.',
  sections: [
    // -----------------------------------------------------------------------
    // Section 1 — System Stats (admin-level metrics)
    // -----------------------------------------------------------------------
    {
      id: 'system-overview',
      title: 'System Overview',
      description: 'Key operational metrics.',
      requiredAnyPermission: ['view_users', 'view_crawl_runs', 'view_companies'],
      cards: [
        {
          id: 'total-companies',
          title: 'Total Companies',
          description: 'View tracked companies',
          route: '/companies',
          icon: Building2,
          type: 'stat',
          dataPath: 'totalCompanies',
          iconColor: 'text-accent-light',
          requiredPermission: 'view_companies',
        },
        {
          id: 'total-news',
          title: 'Total News Articles',
          description: 'Browse all articles',
          route: '/news',
          icon: Newspaper,
          type: 'stat',
          dataPath: 'totalNews',
          iconColor: 'text-blue-400',
          requiredPermission: 'view_news',
        },
        {
          id: 'crawl-runs-today',
          title: 'Crawl Runs Today',
          description: 'Monitor crawling activity',
          route: '/crawl',
          icon: Activity,
          type: 'stat',
          dataPath: 'activeCrawlRuns',
          iconColor: 'text-yellow-400',
          requiredPermission: 'view_crawl_runs',
        },
        {
          id: 'total-users',
          title: 'Total Users',
          description: 'Manage user accounts',
          route: '/users',
          icon: Users,
          type: 'stat',
          dataPath: 'totalUsers',
          iconColor: 'text-accent-light',
          requiredPermission: 'view_users',
        },
      ],
    },

    // -----------------------------------------------------------------------
    // Section 2 — Market Data
    // -----------------------------------------------------------------------
    {
      id: 'market-data',
      title: 'Market Data',
      description: 'Real-time market data and stock performance.',
      requiredAnyPermission: ['view_market_data', 'view_price_history', 'view_trading_volume'],
      cards: [
        {
          id: 'market-overview',
          title: 'Market Overview',
          description: 'Track market movements',
          route: '/market',
          icon: TrendingUp,
          type: 'stat',
          dataPath: 'marketChange',
          badge: 'Live',
          iconColor: 'text-up',
          requiredPermission: 'view_market_data',
        },
        {
          id: 'top-stocks',
          title: 'Top Gainers / Losers',
          description: 'See stock performance',
          route: '/companies',
          icon: TrendingUp,
          type: 'stat',
          iconColor: 'text-accent-light',
          requiredPermission: 'view_market_data',
        },
        {
          id: 'trading-behaviour',
          title: 'Trading Behaviour',
          description: 'Analyze trading patterns',
          route: '/trading',
          icon: LineChart,
          type: 'stat',
          iconColor: 'text-yellow-400',
          requiredPermission: 'view_trading_volume',
        },
        {
          id: 'watchlist',
          title: 'Watchlist',
          description: 'Companies you are tracking',
          route: '/watchlist',
          icon: Star,
          type: 'stat',
          dataPath: 'trackedCompanies',
          iconColor: 'text-yellow-400',
          requiredPermission: 'view_watchlist',
        },
      ],
    },

    // -----------------------------------------------------------------------
    // Section 3 — Analysis
    // -----------------------------------------------------------------------
    {
      id: 'analysis',
      title: 'Analysis',
      description: 'Buyer/seller behaviour, VWAP, and pressure indicators.',
      requiredAnyPermission: ['view_analysis', 'view_price_trends', 'view_vwap_analysis'],
      cards: [
        {
          id: 'analysis-overview',
          title: 'Analysis Overview',
          description: 'Cross-company analytics',
          route: '/analytics',
          icon: BarChart3,
          type: 'stat',
          dataPath: 'analysisCount',
          iconColor: 'text-accent-light',
          requiredPermission: 'view_analysis',
        },
        {
          id: 'price-trends',
          title: 'Price Trends',
          description: 'Historical price movement',
          route: '/analytics',
          icon: LineChart,
          type: 'stat',
          iconColor: 'text-up',
          requiredPermission: 'view_price_trends',
        },
        {
          id: 'vwap-analysis',
          title: 'VWAP Analysis',
          description: 'Volume-weighted average price',
          route: '/analytics',
          icon: BarChart3,
          type: 'stat',
          iconColor: 'text-yellow-400',
          requiredPermission: 'view_vwap_analysis',
        },
        {
          id: 'buy-sell-pressure',
          title: 'Buy / Sell Pressure',
          description: 'Buyer vs seller analysis',
          route: '/analytics',
          icon: Activity,
          type: 'stat',
          iconColor: 'text-blue-400',
          requiredPermission: 'view_pressure_analysis',
        },
      ],
    },

    // -----------------------------------------------------------------------
    // Section 4 — News
    // -----------------------------------------------------------------------
    {
      id: 'news',
      title: 'News & Categorisation',
      description: 'Latest market news and AI categorisation.',
      requiredAnyPermission: ['view_news', 'categorize_news', 'correct_categories'],
      cards: [
        {
          id: 'news-feed',
          title: 'News Feed',
          description: 'Latest crawled articles',
          route: '/news',
          icon: Newspaper,
          type: 'stat',
          dataPath: 'totalNews',
          iconColor: 'text-blue-400',
          requiredPermission: 'view_news',
        },
        {
          id: 'news-corrections',
          title: 'Category Corrections',
          description: 'Review pending corrections',
          route: '/news',
          icon: Newspaper,
          type: 'stat',
          dataPath: 'correctionsCount',
          iconColor: 'text-yellow-400',
          requiredPermission: 'correct_categories',
        },
      ],
    },

    // -----------------------------------------------------------------------
    // Section 5 — Crawler
    // -----------------------------------------------------------------------
    {
      id: 'crawler',
      title: 'Crawler',
      description: 'Data collection pipeline status.',
      requiredAnyPermission: ['view_crawl_runs', 'run_crawler'],
      cards: [
        {
          id: 'crawl-status',
          title: 'Crawl Status',
          description: 'Monitor crawler runs',
          route: '/crawl',
          icon: Radio,
          type: 'stat',
          dataPath: 'activeCrawlRuns',
          iconColor: 'text-accent-light',
          requiredPermission: 'view_crawl_runs',
        },
        {
          id: 'crawl-success',
          title: 'Successful Crawls',
          description: 'Total successful crawl runs',
          route: '/crawl',
          icon: Activity,
          type: 'stat',
          dataPath: 'successfulCrawls',
          iconColor: 'text-up',
          requiredPermission: 'view_crawl_runs',
        },
        {
          id: 'crawl-failed',
          title: 'Failed Crawls',
          description: 'Crawl runs that failed',
          route: '/crawl',
          icon: Activity,
          type: 'stat',
          dataPath: 'failedCrawls',
          iconColor: 'text-down',
          requiredPermission: 'view_crawl_runs',
        },
      ],
    },

    // -----------------------------------------------------------------------
    // Section 6 — Administration
    // -----------------------------------------------------------------------
    {
      id: 'admin-tools',
      title: 'Administration',
      description: 'User management and access control.',
      requiredAnyPermission: ['view_users', 'view_roles'],
      cards: [
        {
          id: 'user-management',
          title: 'User Management',
          description: 'Manage user accounts',
          route: '/users',
          icon: Users,
          type: 'stat',
          dataPath: 'totalUsers',
          iconColor: 'text-yellow-400',
          requiredPermission: 'view_users',
        },
        {
          id: 'roles-permissions',
          title: 'Roles & Permissions',
          description: 'Control access rights',
          route: '/roles-permissions',
          icon: ShieldCheck,
          type: 'stat',
          iconColor: 'text-accent-light',
          requiredPermission: 'view_roles',
        },
      ],
    },

    // -----------------------------------------------------------------------
    // Section 7 — Reports
    // -----------------------------------------------------------------------
    {
      id: 'reports',
      title: 'Reports',
      description: 'Generated reports and exports.',
      requiredAnyPermission: ['view_reports'],
      cards: [
        {
          id: 'reports-overview',
          title: 'Reports',
          description: 'View generated reports',
          route: '/reports',
          icon: BarChart3,
          type: 'stat',
          iconColor: 'text-accent-light',
          requiredPermission: 'view_reports',
        },
      ],
    },
  ],
};

// ---------------------------------------------------------------------------
// Legacy named configs kept for any residual imports.
// They now all point to the universal config so nothing breaks.
// ---------------------------------------------------------------------------
export const dashboardConfigs: Record<string, DashboardConfig> = {
  admin: universalDashboardConfig,
  analyst: universalDashboardConfig,
  viewer: universalDashboardConfig,
};
