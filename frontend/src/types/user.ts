export type CrawlStatus =
  | "pending"
  | "running"
  | "success"
  | "failed"
  | "cancelled";

export type CrawlType =
  | "news"
  | "trading_data"
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

  status: CrawlStatus;

  sources: string[];

  articles_found: number;
  articles_created: number;
  articles_updated: number;

  errors: string[];
  logs: string;

  task_id: string | null;
}