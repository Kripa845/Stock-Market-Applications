import { useCallback, useEffect, useState } from 'react';
import { getCompanies } from '../api/companies';
import { newsApi } from '../api/news';
import { dashboardApi } from '../api/dashboard';
import { getCrawlRuns } from '../api/crawler';
import { tradingApi } from '../api/trading';
import { useAuth } from '../contexts/AuthContext';
import type { Company } from '../types/company';
import type { NewsArticle } from '../types';
import type { CrawlRun } from '../types/crawl';

export interface DashboardStats {
  totalCompanies: number;
  totalNews: number;
  crawlRunsToday: number;
  totalCrawlRuns: number;
  totalUsers: number;
  successfulCrawls: number;
  failedCrawls: number;
  activeCrawlRuns: number;
  marketChange: number;
  trackedCompanies: number;
  correctionsCount: number;
  activeCompanies: Company[];
  recentNews: NewsArticle[];
  recentCrawls: CrawlRun[];
  analysisCount: number;
}

function isCompany(obj: unknown): obj is Company {
  return (
    obj !== null &&
    typeof obj === 'object' &&
    'symbol' in obj &&
    'name' in obj
  );
}

function isNewsArticle(obj: unknown): obj is NewsArticle {
  return obj !== null && typeof obj === 'object' && 'id' in obj && 'headline' in obj;
}

function isCrawlRun(obj: unknown): obj is CrawlRun {
  return obj !== null && typeof obj === 'object' && 'id' in obj;
}

export function resolveDataPath(obj: Record<string, unknown>, path: string): unknown {
  if (!path || !obj) return undefined;
  const parts = path.split('.');
  let current: unknown = obj;
  for (const part of parts) {
    if (current === null || current === undefined) return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

/**
 * Fetches dashboard data based on the current user's PERMISSIONS, not their
 * role.  Only the API endpoints the user can access are called; all others are
 * skipped to avoid 403 responses cluttering the console.
 */
export function useDashboardData(_role: string | null) {
  const { hasPermission, user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError('');

    // Determine which API calls to make based on permissions
    const isAdmin = user.role === 'admin';
    const canViewCompanies = isAdmin || hasPermission('view_companies') || hasPermission('view_market_data');
    const canViewNews = isAdmin || hasPermission('view_news');
    const canViewCrawls = isAdmin || hasPermission('view_crawl_runs');
    const canViewAnalysis = isAdmin || hasPermission('view_analysis') || hasPermission('view_market_data');
    const canViewAdminDash = isAdmin || hasPermission('view_users') || hasPermission('view_crawl_runs');

    try {
      const [adminData, analystData, companiesRes, newsRes, crawlsRes, tradingRes] =
        await Promise.allSettled([
          // Admin dashboard — only if user can see admin-level data
          canViewAdminDash ? dashboardApi.admin() : Promise.resolve(null),
          // Analyst dashboard — provides correction counts etc.
          canViewNews ? dashboardApi.analyst() : Promise.resolve(null),
          // Companies list — for market change calculation
          canViewCompanies
            ? getCompanies({ status: 'active', tracked_only: false })
            : Promise.resolve(null),
          // News — total count + recent
          canViewNews ? newsApi.getNews({ page: 1 }) : Promise.resolve(null),
          // Crawl runs
          canViewCrawls ? getCrawlRuns({ page: 1 }) : Promise.resolve(null),
          // Trading/analysis summary
          canViewAnalysis ? tradingApi.getDashboardSummary() : Promise.resolve(null),
        ]);

      let totalCompanies = 0;
      let totalNews = 0;
      let crawlRunsToday = 0;
      let totalCrawlRuns = 0;
      let totalUsers = 0;
      let successfulCrawls = 0;
      let failedCrawls = 0;
      let activeCrawlRuns = 0;
      let marketChange = 0;
      let trackedCompanies = 0;
      let correctionsCount = 0;
      let activeCompanies: Company[] = [];
      let recentNews: NewsArticle[] = [];
      let recentCrawls: CrawlRun[] = [];
      let analysisCount = 0;

      if (adminData.status === 'fulfilled' && adminData.value) {
        const d = adminData.value as unknown as Record<string, unknown>;
        const summary = d.summary as Record<string, unknown> | undefined;
        if (summary) {
          totalCompanies = (summary.total_companies as number) ?? totalCompanies;
          totalNews = (summary.total_news as number) ?? totalNews;
          activeCrawlRuns = (summary.active_crawl_runs as number) ?? activeCrawlRuns;
          successfulCrawls = (summary.successful_crawl_runs as number) ?? successfulCrawls;
          failedCrawls = (summary.failed_crawl_runs as number) ?? failedCrawls;
          totalUsers = (summary.total_users as number) ?? totalUsers;
        }
        const trackedList = d.tracked_companies as unknown[];
        if (Array.isArray(trackedList)) {
          activeCompanies = trackedList.filter(isCompany);
        }
        const recentList = d.recent_crawls as unknown[];
        if (Array.isArray(recentList)) {
          recentCrawls = recentList.filter(isCrawlRun);
        }
      }

      if (analystData.status === 'fulfilled' && analystData.value) {
        const d = analystData.value as unknown as Record<string, unknown>;
        trackedCompanies = (d.tracked_companies as number) ?? trackedCompanies;
        totalNews = (d.total_news as number) ?? totalNews;
        correctionsCount = (d.corrections_count as number) ?? correctionsCount;
      }

      if (companiesRes.status === 'fulfilled' && companiesRes.value) {
        const results = (companiesRes.value as { results?: unknown[] }).results ?? [];
        activeCompanies = results.filter(isCompany);
        totalCompanies = results.length || totalCompanies;
        const gainers = [...activeCompanies].sort(
          (a, b) => ((b as Company).price_change_percent ?? 0) - ((a as Company).price_change_percent ?? 0),
        );
        marketChange =
          gainers.length > 0
            ? gainers.reduce((sum, c) => sum + ((c as Company).price_change_percent ?? 0), 0) /
              gainers.length
            : 0;
      }

      if (newsRes.status === 'fulfilled' && newsRes.value) {
        const val = newsRes.value as { results?: unknown[]; count?: number };
        const results = val.results ?? [];
        recentNews = results.filter(isNewsArticle).slice(0, 10);
        totalNews = val.count !== undefined ? val.count : results.length || totalNews;
      }

      if (crawlsRes.status === 'fulfilled' && crawlsRes.value) {
        const val = crawlsRes.value as { results?: unknown[]; count?: number };
        const results = val.results ?? [];
        const allCrawls = results.filter(isCrawlRun);
        totalCrawlRuns = val.count ?? allCrawls.length;
        const today = new Date().toISOString().split('T')[0];
        crawlRunsToday = allCrawls.filter((c) => {
          const start = (c as CrawlRun).started_at
            ? (c as CrawlRun).started_at!.split('T')[0]
            : '';
          return start === today;
        }).length;
        recentCrawls = allCrawls.slice(0, 10);
        activeCrawlRuns = allCrawls.filter((c) => (c as CrawlRun).status === 'running').length;
        successfulCrawls = allCrawls.filter((c) => (c as CrawlRun).status === 'success').length;
        failedCrawls = allCrawls.filter((c) => (c as CrawlRun).status === 'failed').length;
      }

      if (tradingRes.status === 'fulfilled' && tradingRes.value) {
        const d = tradingRes.value as Record<string, unknown>;
        if (d.market_change !== undefined) marketChange = d.market_change as number;
        if (d.total_articles !== undefined) totalNews = d.total_articles as number;
        if (d.active_analysis !== undefined) analysisCount = d.active_analysis as number;
      }

      setStats({
        totalCompanies,
        totalNews,
        crawlRunsToday,
        totalCrawlRuns,
        totalUsers,
        successfulCrawls,
        failedCrawls,
        activeCrawlRuns,
        marketChange,
        trackedCompanies,
        correctionsCount,
        activeCompanies,
        recentNews,
        recentCrawls,
        analysisCount,
      });
    } catch (err: unknown) {
      console.error('Failed to load dashboard data:', err);
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Unable to load dashboard data.');
    } finally {
      setLoading(false);
    }
  }, [user, hasPermission]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { stats, loading, error, refetch: fetchData };
}
