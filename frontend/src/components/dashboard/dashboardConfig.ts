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
  Play,
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
  allowedRoles?: string[];
}

export interface DashboardSectionData {
  id: string;
  title: string;
  description?: string;
  cards: DashboardCardData[];
}

export interface DashboardConfig {
  title: string;
  subtitle: string;
  sections: DashboardSectionData[];
}

export const dashboardConfigs: Record<string, DashboardConfig> = {
  admin: {
    title: 'Admin Dashboard',
    subtitle: 'System overview, market intelligence, and administrative controls.',
    sections: [
      {
        id: 'overview',
        title: 'System Overview',
        description: 'Key metrics across your organization.',
        cards: [
          {
            id: 'total-companies',
            title: 'Total Companies',
            description: 'View tracked companies',
            route: '/admin/companies',
            icon: Building2,
            type: 'stat',
            dataPath: 'totalCompanies',
            iconColor: 'text-accent-light',
          },
          {
            id: 'total-news',
            title: 'Total News Articles',
            description: 'Browse all articles',
            route: '/admin/news',
            icon: Newspaper,
            type: 'stat',
            dataPath: 'totalNews',
            iconColor: 'text-blue-400',
          },
          {
            id: 'crawl-runs-today',
            title: 'Crawl Runs Today',
            description: 'Monitor crawling activity',
            route: '/admin/crawl-runs',
            icon: Activity,
            type: 'stat',
            dataPath: 'activeCrawlRuns',
            iconColor: 'text-yellow-400',
          },
          {
            id: 'total-users',
            title: 'Total Users',
            description: 'Manage user accounts',
            route: '/admin/users',
            icon: Users,
            type: 'stat',
            dataPath: 'totalUsers',
            iconColor: 'text-accent-light',
          },
        ],
      },
      {
        id: 'market-analytics',
        title: 'Market Analytics',
        description: 'Real-time market data and stock performance.',
        cards: [
          {
            id: 'market-overview',
            title: 'Market Overview',
            description: 'Track market movements',
            route: '/analyst/market',
            icon: TrendingUp,
            type: 'stat',
            dataPath: 'marketChange',
            badge: 'Live',
            iconColor: 'text-up',
          },
          {
            id: 'top-stocks',
            title: 'Top Gainers / Losers',
            description: 'See stock performance',
            route: '/analyst/stocks',
            icon: TrendingUp,
            type: 'stat',
            iconColor: 'text-accent-light',
          },
          {
            id: 'trading-behaviour',
            title: 'Trading Behaviour',
            description: 'Analyze trading patterns',
            route: '/analyst/trading',
            icon: LineChart,
            type: 'stat',
            iconColor: 'text-yellow-400',
          },
        ],
      },
      {
        id: 'content',
        title: 'Content & Crawling',
        description: 'News and crawler management.',
        cards: [
          {
            id: 'recent-news',
            title: 'Recent News',
            description: 'Review latest articles',
            route: '/admin/news',
            icon: Newspaper,
            type: 'stat',
            dataPath: 'totalNews',
            iconColor: 'text-blue-400',
          },
          {
            id: 'crawl-runs',
            title: 'Crawl Runs',
            description: 'Monitor crawler activity',
            route: '/admin/crawl-runs',
            icon: Radio,
            type: 'stat',
            dataPath: 'activeCrawlRuns',
            iconColor: 'text-accent-light',
          },
        ],
      },
      {
        id: 'admin-tools',
        title: 'Administrative Tools',
        description: 'User management and system configuration.',
        cards: [
          {
            id: 'user-management',
            title: 'User Management',
            description: 'Manage user accounts',
            route: '/admin/users',
            icon: Users,
            type: 'stat',
            dataPath: 'totalUsers',
            iconColor: 'text-yellow-400',
            allowedRoles: ['admin'],
          },
          {
            id: 'roles-permissions',
            title: 'Roles & Permissions',
            description: 'Control access rights',
            route: '/admin/roles-permissions',
            icon: ShieldCheck,
            type: 'stat',
            iconColor: 'text-accent-light',
            allowedRoles: ['admin'],
          },
          {
            id: 'crawlers',
            title: 'Crawlers',
            description: 'Manage crawler configurations',
            route: '/admin/crawl',
            icon: Radio,
            type: 'stat',
            iconColor: 'text-accent-light',
          },
          {
            id: 'reports',
            title: 'Reports',
            description: 'View generated reports',
            route: '/reports',
            icon: BarChart3,
            type: 'stat',
            iconColor: 'text-accent-light',
          },
        ],
      },
    ],
  },
  analyst: {
    title: 'Analyst Dashboard',
    subtitle: 'News categorization, market analysis, and stock insights.',
    sections: [
      {
        id: 'metrics',
        title: 'Key Metrics',
        description: 'Your analysis metrics at a glance.',
        cards: [
          {
            id: 'total-companies',
            title: 'Total Companies',
            description: 'Tracked companies',
            route: '/analyst/companies',
            icon: Building2,
            type: 'stat',
            dataPath: 'trackedCompanies',
            iconColor: 'text-accent-light',
          },
          {
            id: 'new-articles',
            title: 'New Articles',
            description: 'Latest crawled articles',
            route: '/analyst/news',
            icon: Newspaper,
            type: 'stat',
            dataPath: 'totalNews',
            iconColor: 'text-blue-400',
          },
          {
            id: 'crawl-runs-today',
            title: 'Crawl Runs Today',
            description: 'Crawling activity',
            route: '/admin/crawl-runs',
            icon: Activity,
            type: 'stat',
            dataPath: 'totalCrawlRuns',
            iconColor: 'text-yellow-400',
          },
          {
            id: 'market-overview',
            title: 'Market Overview',
            description: 'Track market movements',
            route: '/analyst/market',
            icon: TrendingUp,
            type: 'stat',
            dataPath: 'marketChange',
            badge: 'Live',
            iconColor: 'text-up',
          },
        ],
      },
      {
        id: 'performance',
        title: 'Performance',
        description: 'Stock and trading analysis.',
        cards: [
          {
            id: 'stocks-performance',
            title: 'Stocks Performance',
            description: 'View stock data',
            route: '/analyst/stocks',
            icon: TrendingUp,
            type: 'stat',
            iconColor: 'text-accent-light',
          },
          {
            id: 'trading-behaviour',
            title: 'Trading Behaviour',
            description: 'Trading pattern analysis',
            route: '/analyst/trading',
            icon: LineChart,
            type: 'stat',
            iconColor: 'text-yellow-400',
          },
          {
            id: 'latest-news',
            title: 'Latest News',
            description: 'Read latest articles',
            route: '/analyst/news',
            icon: Newspaper,
            type: 'stat',
            dataPath: 'totalNews',
            iconColor: 'text-blue-400',
          },
        ],
      },
      {
        id: 'quick-actions',
        title: 'Quick Actions',
        description: 'Common analyst tasks.',
        cards: [
          {
            id: 'quick-trigger-crawl',
            title: 'Trigger Crawl Run',
            description: 'Start a new crawl',
            route: '/admin/crawl-runs',
            icon: Play,
            type: 'quick-action',
          },
          {
            id: 'quick-view-reports',
            title: 'View Reports',
            description: 'Check reports',
            route: '/reports',
            icon: BarChart3,
            type: 'quick-action',
          },
          {
            id: 'quick-analyze-stocks',
            title: 'Analyze Stocks',
            description: 'Go to stocks',
            route: '/analyst/stocks',
            icon: TrendingUp,
            type: 'quick-action',
          },
          {
            id: 'quick-view-news',
            title: 'View News',
            description: 'Browse news',
            route: '/analyst/news',
            icon: Newspaper,
            type: 'quick-action',
          },
        ],
      },
      {
        id: 'crawler-access',
        title: 'Crawler Access',
        description: 'Crawler monitoring.',
        cards: [
          {
            id: 'crawlers',
            title: 'Crawlers',
            description: 'Monitor crawler status',
            route: '/admin/crawl-runs',
            icon: Radio,
            type: 'stat',
            iconColor: 'text-accent-light',
          },
        ],
      },
    ],
  },
  viewer: {
    title: 'Viewer Dashboard',
    subtitle: 'Read-only access to market information.',
    sections: [
      {
        id: 'overview',
        title: 'Overview',
        description: 'Key metrics and market data.',
        cards: [
          {
            id: 'total-companies',
            title: 'Total Companies',
            description: 'Tracked companies',
            route: '/analyst/companies',
            icon: Building2,
            type: 'stat',
            dataPath: 'trackedCompanies',
            iconColor: 'text-accent-light',
          },
          {
            id: 'new-articles',
            title: 'New Articles',
            description: 'Latest crawled articles',
            route: '/viewer/news',
            icon: Newspaper,
            type: 'stat',
            dataPath: 'totalNews',
            iconColor: 'text-blue-400',
          },
          {
            id: 'crawl-runs-today',
            title: 'Crawl Runs Today',
            description: 'Crawling activity',
            route: '/admin/crawl-runs',
            icon: Activity,
            type: 'stat',
            iconColor: 'text-yellow-400',
          },
          {
            id: 'market-overview',
            title: 'Market Overview',
            description: 'Track market movements',
            route: '/viewer/market',
            icon: TrendingUp,
            type: 'stat',
            dataPath: 'marketChange',
            badge: 'Live',
            iconColor: 'text-up',
          },
        ],
      },
      {
        id: 'market-data',
        title: 'Market Data',
        description: 'Stock and trading information.',
        cards: [
          {
            id: 'top-stocks',
            title: 'Top Gainers / Losers',
            description: 'Stock performance',
            route: '/viewer/stocks',
            icon: TrendingUp,
            type: 'stat',
            iconColor: 'text-accent-light',
          },
          {
            id: 'trading-behaviour',
            title: 'Trading Behaviour',
            description: 'Trading patterns',
            route: '/viewer/trading',
            icon: LineChart,
            type: 'stat',
            iconColor: 'text-yellow-400',
          },
          {
            id: 'latest-news',
            title: 'Latest News',
            description: 'Recent articles',
            route: '/viewer/news',
            icon: Newspaper,
            type: 'stat',
            dataPath: 'totalNews',
            iconColor: 'text-blue-400',
          },
        ],
      },
      {
        id: 'tools',
        title: 'Tools',
        description: 'Reports and crawler status.',
        cards: [
          {
            id: 'reports',
            title: 'Reports',
            description: 'View generated reports',
            route: '/reports',
            icon: BarChart3,
            type: 'stat',
            iconColor: 'text-accent-light',
          },
          {
            id: 'crawlers',
            title: 'Crawlers',
            description: 'Monitor crawler status',
            route: '/admin/crawl-runs',
            icon: Radio,
            type: 'stat',
            iconColor: 'text-accent-light',
          },
        ],
      },
    ],
  },
};
