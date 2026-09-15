
import { apiClient } from './client';
import type {
  AnalystDashboard,
  ViewerDashboard,
  
} from '../types';
export interface RecentCrawlRun {
  id: number;
  target: string;
  status: string;
  sources: string[];
  started_at: string | null;
  completed_at: string | null;
  articles_found: number;
  articles_created: number;
  articles_updated: number;
}
export interface AdminDashboard {
  summary: {
    total_companies: number;
    total_users: number;
    active_crawl_runs: number;
    successful_crawl_runs: number;
    failed_crawl_runs: number;
    total_news: number;
  };
  recent_crawls: RecentCrawlRun[];
  tracked_companies: import('../types').Company[];
}
export const dashboardApi = {
  // summary: () =>
  //   apiClient
  //     .get<DashboardSummary>(
  //       '/dashboard/summary/'
  //     )
  //     .then((response) => response.data),
    admin: () =>
    apiClient
      .get<AdminDashboard>('/dashboard/admin/')
      .then((response) => response.data),
  analyst: () =>
    apiClient
      .get<AnalystDashboard>(
        '/dashboard/analyst/'
      )
      .then((response) => response.data),

  viewer: () =>
    apiClient
      .get<ViewerDashboard>(
        '/dashboard/viewer/'
      )
      .then((response) => response.data),
};

