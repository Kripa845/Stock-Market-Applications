import {
  Activity,
  BarChart3,
  Building2,
  CheckCircle2,
  FileText,
  Landmark,
  LineChart,
  Newspaper,
  PenLine,
  Radio,
  ShieldCheck,
  Star,
  TrendingUp,
  Users,
  XCircle,
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
  /** How a stat value is shown: plain count (default) or a signed percentage. */
  format?: 'count' | 'percent';
  /**
   * Permission key(s) the user must ALL have for this card to appear. Use the same keys as
   * the destination route in config/routePermissions.ts. Undefined = always shown.
   */
  requiredPermission?: string | string[];
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
    // Section 1 - At a glance: one row of headline numbers
    // -----------------------------------------------------------------------
    {
      id: 'overview',
      title: 'At a glance',
      description: 'Headline numbers for your tracked companies and content.',
      requiredAnyPermission: ['view_companies', 'view_market_data', 'view_watchlist', 'view_news'],
      cards: [
        {
          id: 'total-companies',
          title: 'Companies',
          description: 'Companies in the system',
          route: '/companies',
          icon: Building2,
          type: 'stat',
          dataPath: 'totalCompanies',
          iconColor: 'text-accent-light',
          requiredPermission: 'view_companies',
        },
        {
          id: 'market-change',
          title: 'Tracked avg. change',
          description: 'Average latest-session change of the tracked companies',
          route: '/market',
          icon: TrendingUp,
          type: 'stat',
          dataPath: 'marketChange',
          format: 'percent',
          badge: 'Latest close',
          iconColor: 'text-up',
          requiredPermission: ['view_companies', 'view_market_data'],
        },
        {
          id: 'watchlist',
          title: 'Watchlist',
          description: 'Companies on your watchlist',
          route: '/watchlist',
          icon: Star,
          type: 'stat',
          dataPath: 'trackedCompanies',
          iconColor: 'text-yellow-400',
          requiredPermission: ['view_watchlist', 'view_companies'],
        },
        {
          id: 'total-news',
          title: 'News articles',
          description: 'Crawled and categorised articles',
          route: '/news',
          icon: Newspaper,
          type: 'stat',
          dataPath: 'totalNews',
          iconColor: 'text-sky-400',
          requiredPermission: 'view_news',
        },
      ],
    },

    // -----------------------------------------------------------------------
    // Section 2 - Data pipeline
    // -----------------------------------------------------------------------
    {
      id: 'pipeline',
      title: 'Data pipeline',
      description: 'Crawler runs that collect prices, floorsheets and news.',
      requiredAnyPermission: ['view_crawl_runs'],
      cards: [
        {
          id: 'crawl-runs-today',
          title: 'Runs today',
          description: 'Crawl runs started today',
          route: '/crawl',
          icon: Activity,
          type: 'stat',
          dataPath: 'crawlRunsToday',
          iconColor: 'text-accent-light',
          requiredPermission: 'view_crawl_runs',
        },
        {
          id: 'crawl-active',
          title: 'Running now',
          description: 'Crawl runs in progress',
          route: '/crawl',
          icon: Radio,
          type: 'stat',
          dataPath: 'activeCrawlRuns',
          iconColor: 'text-yellow-400',
          requiredPermission: 'view_crawl_runs',
        },
        {
          id: 'crawl-success',
          title: 'Successful',
          description: 'Crawl runs that finished',
          route: '/crawl',
          icon: CheckCircle2,
          type: 'stat',
          dataPath: 'successfulCrawls',
          iconColor: 'text-up',
          requiredPermission: 'view_crawl_runs',
        },
        {
          id: 'crawl-failed',
          title: 'Failed',
          description: 'Crawl runs that failed',
          route: '/crawl',
          icon: XCircle,
          type: 'stat',
          dataPath: 'failedCrawls',
          iconColor: 'text-down',
          requiredPermission: 'view_crawl_runs',
        },
      ],
    },

    // -----------------------------------------------------------------------
    // Section 3 - Administration numbers
    // -----------------------------------------------------------------------
    {
      id: 'admin',
      title: 'Administration',
      description: 'Accounts and items waiting for review.',
      requiredAnyPermission: ['view_users', 'correct_categories'],
      cards: [
        {
          id: 'total-users',
          title: 'Users',
          description: 'Registered accounts',
          route: '/users',
          icon: Users,
          type: 'stat',
          dataPath: 'totalUsers',
          iconColor: 'text-accent-light',
          requiredPermission: 'view_users',
        },
        {
          id: 'news-corrections',
          title: 'Category corrections',
          description: 'News categories corrected by reviewers',
          route: '/news',
          icon: PenLine,
          type: 'stat',
          dataPath: 'correctionsCount',
          iconColor: 'text-yellow-400',
          requiredPermission: ['correct_categories', 'view_news'],
        },
      ],
    },

    // -----------------------------------------------------------------------
    // Section 4 - Quick links (pages without one headline number)
    // -----------------------------------------------------------------------
    {
      id: 'shortcuts',
      title: 'Quick links',
      cards: [
        {
          id: 'link-market',
          title: 'Market Overview',
          description: 'NEPSE, gainers, losers, turnover, volume and trades',
          route: '/market',
          icon: LineChart,
          type: 'quick-action',
          requiredPermission: ['view_companies', 'view_market_data'],
        },
        {
          id: 'link-tracked',
          title: 'Tracked Companies',
          description: 'Movers, signals and broker activity per company',
          route: '/tracked',
          icon: Building2,
          type: 'quick-action',
          requiredPermission: 'view_market_data',
        },
        {
          id: 'link-brokers',
          title: 'Broker Analysis',
          description: 'Buy, sell and net activity from the floorsheet',
          route: '/broker-analysis',
          icon: Landmark,
          type: 'quick-action',
          requiredPermission: 'view_analysis',
        },
        {
          id: 'link-analysis',
          title: 'Technical Charts',
          description: 'Price, volume and news for one company',
          route: '/company-analysis',
          icon: BarChart3,
          type: 'quick-action',
          requiredPermission: ['view_analysis', 'view_companies', 'view_price_history', 'view_market_data'],
        },
        {
          id: 'link-news',
          title: 'News Feed',
          description: 'Latest crawled articles',
          route: '/news',
          icon: Newspaper,
          type: 'quick-action',
          requiredPermission: 'view_news',
        },
        {
          id: 'link-crawl',
          title: 'Crawl Management',
          description: 'Start and monitor crawler runs',
          route: '/crawl',
          icon: Activity,
          type: 'quick-action',
          requiredPermission: 'view_crawl_runs',
        },
        {
          id: 'link-reports',
          title: 'Reports',
          description: 'Generated reports and exports',
          route: '/reports',
          icon: FileText,
          type: 'quick-action',
          requiredPermission: ['view_reports'],
        },
        {
          id: 'link-roles',
          title: 'Roles & Permissions',
          description: 'Control access rights',
          route: '/roles-permissions',
          icon: ShieldCheck,
          type: 'quick-action',
          requiredPermission: 'view_roles',
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
