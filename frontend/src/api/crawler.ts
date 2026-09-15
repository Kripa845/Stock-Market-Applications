import apiClient from "./client";
import type { CrawlRun } from "../types/crawl";

export interface CrawlQuery {
  page?: number;
  status?: string;
  crawl_type?: string;
}

export interface PaginatedCrawls {
  count: number;
  next: string | null;
  previous: string | null;
  results: CrawlRun[];
}

export async function getCrawlRuns(
  params: CrawlQuery = {}
) {
  const response =
    await apiClient.get<PaginatedCrawls>(
      "/crawler-runs/",
      { params }
    );

  return response.data;
}

export async function getCrawlRun(
  id: number
) {
  const response =
    await apiClient.get<CrawlRun>(
      `/crawler-runs/${id}/`
    );

  return response.data;
}

export async function triggerCrawl(
  data: {
    crawl_type:
      | "news"
      | "trading"
      | "floorsheet"
      | "all";

    source?: string;

    company?: number | null;

    spider_args?: Record<
      string,
      string | number
    >;
  }
) {
  const response =
    await apiClient.post(
      "/crawler-runs/",
      data
    );

  return response.data;
}

export async function cancelCrawl(
  id: number
) {
  const response =
    await apiClient.post(
      `/crawler-runs/${id}/cancel/`
    );

  return response.data;
}

export async function retryCrawl(
  id: number
) {
  const response =
    await apiClient.post(
      `/crawler-runs/${id}/retry/`
    );

  return response.data;
}