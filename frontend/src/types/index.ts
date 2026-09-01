// Types mirror the DRF serializers in Backend/apps/*/serializers.py.
// Where a backend route isn't wired up yet (news, analysis, admin
// crawl-runs), the shape is inferred from the model fields + the
// assignment spec (Section 7 / Section 3) instead of a live serializer.

export type Role = "admin" | "analyst" | "viewer";

// apps/users/serializers.py:UserSerializer
export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: Role;
  is_active: boolean;
  date_joined: string;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  passwordConfirm: string;
  firstName?: string;
  lastName?: string;
}

export interface LoginPayload {
  username: string;
  password: string;
}

export interface TokenPair {
  access: string;
  refresh: string;
}

// apps/companies/serializers.py:CompanySerializer
export interface Company {
  id: number;
  symbol: string;
  name: string;
  sector: string;
  aliases: string[];
  is_active: boolean;
}

// apps/market_data/serializers.py:DailyPriceSerializers
export interface DailyPrice {
  id: number;
  company: number; // FK id
  date: string; // YYYY-MM-DD
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
  turnover: string;
}

// apps/market_data/serializers.py:FloorsheetSerializer
export interface FloorsheetTransaction {
  id: number;
  company: number;
  date: string;
  transaction_id: string;
  buyer_broker: string;
  seller_broker: string;
  quantity: number;
  rate: string;
  amount: string | null;
  created_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface FloorsheetQueryParams {
  company?: number | string;
  date?: string;
  buyer_broker?: string;
  seller_broker?: string;
  search?: string;
  ordering?: string;
}

// --- Not yet implemented on the backend (apps/news/urls.py is empty) --
// Inferred from apps/news/models.py: NewsArticle + ArticleCompanyTag
export interface NewsArticle {
  id: number;
  source: string;
  url: string;
  headline: string;
  body: string;
  published_at: string | null;
  sentiment: number | null;
  sentiment_label: string;
  confidence?: number; // from the ArticleCompanyTag for the queried company
  method?: string;
}

export interface RecategorizePayload {
  company_id: number | string;
  action: "add" | "remove" | "update";
  reason?: string;
}

// --- Not yet implemented on the backend (apps/analysis/urls.py is empty) --
// Inferred from apps/analysis/models.py: DailyAnalysis
export type Pressure = "buying" | "selling" | "neutral";

export interface BehaviorSummaryData {
  company: number;
  date: string;
  vwap: string | null;
  close_price: string;
  volume: number;
  volume_average: string | null;
  volume_anomaly: boolean;
  pressure: Pressure;
  news_count: number;
}

export interface NewsPriceCorrelation {
  company: number;
  correlation: number;
  window_days: number;
}

// --- Not yet implemented on the backend (apps/crawler_runs has no urls.py) --
// Inferred from apps/crawler_runs/models.py: CrawlRun
export type CrawlRunStatus = "pending" | "running" | "completed" | "failed";

export interface CrawlRun {
  id: number;
  started_at: string | null;
  completed_at: string | null;
  status: CrawlRunStatus;
  sources: string[];
  articles_found: number;
  articles_created: number;
  articles_updated: number;
  errors: string[];
}
