export type CrawlStatus =
  | "pending"
  | "running"
  | "success"
  | "failed"
  | "cancelled";

export type CrawlType =
  | "news"
  | "trading"
  | "floorsheet"
  | "all";

export interface CrawlRun {
  id: number;

  crawl_type: CrawlType;
  target: string;

  company: number | null;
  company_symbol: string | null;

  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  duration_seconds: number | null;

  status: CrawlStatus;

  sources: string[];

  articles_found: number;
  articles_created: number;
  articles_updated: number;

  prices_found: number;
  prices_created: number;
  prices_updated: number;

  floorsheet_found: number;
  floorsheet_created: number;
  floorsheet_updated: number;

  errors: string[];
  logs: string;

  task_id: string | null;
  process_id: number | null;
}