import { useCallback, useEffect, useState } from 'react';
import { getCompanies } from '../api/companies';
import { newsApi } from '../api/news';
import { dashboardApi } from '../api/dashboard';
import { getCrawlRuns } from '../api/crawler';
import { tradingApi } from '../api/trading';
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

function isCompany(obj: any): obj is Company {
  return obj && typeof obj === 'object' && 'symbol' in obj && 'name' in obj;
}

function isNewsArticle(obj: any): obj is NewsArticle {
  return obj && typeof obj === 'object' && 'id' in obj && 'headline' in obj;
}

function isCrawlRun(obj: any): obj is CrawlRun {
  return obj && typeof obj === 'object' && 'id' in obj;
}

export function resolveDataPath(obj: Record<string, any>, path: string): any {
  if (!path || !obj) return undefined;
  const parts = path.split('.');
  let current: any = obj;
  for (const part of parts) {
    if (current === null || current === undefined) return undefined;
    current = current[part];
  }
  return current;
}

export function useDashboardData(role: string | null) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    if (!role) return;
    setLoading(true);
    setError('');

    try {
      const [adminData, analystData, viewerData, companiesRes, newsRes, crawlsRes, tradingRes] = await Promise.allSettled([
        role === 'admin' ? dashboardApi.admin() : Promise.resolve(null),
        role === 'analyst' ? dashboardApi.analyst() : Promise.resolve(null),
        role === 'viewer' ? dashboardApi.viewer() : Promise.resolve(null),
        getCompanies({ status: 'active', tracked_only: false }),
        newsApi.getNews({ page: 1 }),
        getCrawlRuns({ page: 1 }),
        tradingApi.getDashboardSummary(),
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
        const d = adminData.value as any;
        totalCompanies = d.summary?.total_companies ?? totalCompanies;
        totalNews = d.summary?.total_news ?? totalNews;
        activeCrawlRuns = d.summary?.active_crawl_runs ?? activeCrawlRuns;
        successfulCrawls = d.summary?.successful_crawl_runs ?? successfulCrawls;
        failedCrawls = d.summary?.failed_crawl_runs ?? failedCrawls;
        totalUsers = d.summary?.total_users ?? totalUsers;
        if (d.tracked_companies) {
          activeCompanies = d.tracked_companies.filter(isCompany);
        }
        if (d.recent_crawls) {
          recentCrawls = d.recent_crawls.filter(isCrawlRun);
        }
      }

      if (analystData.status === 'fulfilled' && analystData.value) {
        const d = analystData.value as any;
        trackedCompanies = d.tracked_companies ?? trackedCompanies;
        totalNews = d.total_news ?? totalNews;
        correctionsCount = d.corrections_count ?? correctionsCount;
      }

      if (viewerData.status === 'fulfilled' && viewerData.value) {
        const d = viewerData.value as any;
        trackedCompanies = d.tracked_companies ?? trackedCompanies;
        totalNews = d.total_news ?? totalNews;
      }

      if (companiesRes.status === 'fulfilled' && companiesRes.value) {
        const results = companiesRes.value.results ?? [];
        activeCompanies = results.filter(isCompany);
        totalCompanies = results.length || totalCompanies;
        const gainers = [...results].sort((a: Company, b: Company) => (b.price_change_percent ?? 0) - (a.price_change_percent ?? 0));
        marketChange = gainers.length > 0
          ? gainers.reduce((sum, c: Company) => sum + (c.price_change_percent ?? 0), 0) / gainers.length
          : 0;
      }

      if (newsRes.status === 'fulfilled' && newsRes.value) {
        const results = newsRes.value.results ?? [];
        recentNews = results.filter(isNewsArticle).slice(0, 10);
        totalNews = results.length || totalNews;
        if (newsRes.value.count !== undefined) {
          totalNews = newsRes.value.count;
        }
      }

      if (crawlsRes.status === 'fulfilled' && crawlsRes.value) {
        const results = crawlsRes.value.results ?? [];
        const allCrawls = results.filter(isCrawlRun);
        totalCrawlRuns = crawlsRes.value.count ?? allCrawls.length;
        const today = new Date().toISOString().split('T')[0];
        crawlRunsToday = allCrawls.filter((c: CrawlRun) => {
          const start = c.started_at ? c.started_at.split('T')[0] : '';
          return start === today;
        }).length;
        recentCrawls = allCrawls.slice(0, 10);
        activeCrawlRuns = allCrawls.filter((c: CrawlRun) => c.status === 'running').length;
        successfulCrawls = allCrawls.filter((c: CrawlRun) => c.status === 'success').length;
        failedCrawls = allCrawls.filter((c: CrawlRun) => c.status === 'failed').length;
      }

      if (tradingRes.status === 'fulfilled' && tradingRes.value) {
        const d = tradingRes.value as any;
        if (d.market_change !== undefined) marketChange = d.market_change;
        if (d.total_articles !== undefined) totalNews = d.total_articles;
        if (d.active_analysis !== undefined) analysisCount = d.active_analysis;
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
    } catch (err: any) {
      console.error('Failed to load dashboard data:', err);
      setError(err?.response?.data?.detail || 'Unable to load dashboard data.');
    } finally {
      setLoading(false);
    }
  }, [role]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { stats, loading, error, refetch: fetchData };
}
