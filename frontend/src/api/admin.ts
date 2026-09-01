import apiClient from "./client";
import type { CrawlRun, PaginatedResponse, User } from "../types";

// --- Not yet implemented on the backend -------------------------------
// apps/crawler_runs has no urls.py at all yet, even though CrawlRun
// (models.py) and the Celery tasks (tasks.py: crawl_all_news,
// crawl_daily_prices, crawl_floorsheet) already exist. Written against
// the spec's documented shape (role-gated: Admin).
// ------------------------------------------------------------------------

export interface TriggerCrawlPayload {
  sources?: string[];
}

// POST /api/admin/crawl-runs
export async function triggerCrawlRun(payload: TriggerCrawlPayload = {}): Promise<CrawlRun> {
  const { data } = await apiClient.post<CrawlRun>("/admin/crawl-runs", payload);
  return data;
}

// GET /api/admin/crawl-runs/:id
export async function getCrawlRun(id: number | string): Promise<CrawlRun> {
  const { data } = await apiClient.get<CrawlRun>(`/admin/crawl-runs/${id}`);
  return data;
}

// GET /api/admin/users
export async function listUsers(): Promise<User[] | PaginatedResponse<User>> {
  const { data } = await apiClient.get<User[] | PaginatedResponse<User>>("/admin/users");
  return data;
}
