// ── Company & Market Data ─────────────────────────────────────────────

export interface Company {
  id: number;
  symbol: string;
  name: string;
  sector: string;
  is_active: boolean;
  aliases?: string[];
  is_tracked?: boolean;
  latest_price: number;
  price_change: number;
  price_change_percent: number;
  volume_24h: number;
  turnover_24h: number;
  high_24h: number;
  low_24h: number;
  news_count: number;
  sentiment_score: number;
  sparkline: number[];
  last_crawl?: string | null;
  last_crawl_status?: string | null;
}

export interface DailyPrice {
  id: number;
  company: number;
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
  turnover: string;
}

export interface FloorsheetTransaction {
  id: number;
  company: number;
  date: string;
  transaction_id: string;
  buyer_broker: string;
  seller_broker: string;
  quantity: number;
  rate: string;
  amount: string;
}

// ── News & Categorization ─────────────────────────────────────────────

export type SentimentLabel = 'positive' | 'neutral' | 'negative' | null;

export interface CompanyTag {
  id: number;
  company: number;
  company_symbol?: string;
  symbol?: string;
  company_name: string;
  confidence: number;
  method: string;
  is_manual: boolean;
}

export interface CategorizationCorrection {
  id: number;
  article: number;
  article_headline?: string;
  company: number;
  company_symbol?: string;
  company_name?: string;
  previous_confidence: number | null;
  previous_method: string;
  action: 'add' | 'remove' | 'update';
  reason: string;
  corrected_by: number | null;
  corrected_by_username?: string;
  corrected_at: string;
}

export interface NewsArticle {
  id: number;
  headline: string;
  body?: string;
  source: string;
  url: string;
  published_at: string;
  sentiment: number | null;
  sentiment_label: SentimentLabel;
  is_processed: boolean;
  company_tags: CompanyTag[];
  corrections?: CategorizationCorrection[];
  created_at: string;
  updated_at?: string;
}

export interface NewsStats {
  total_articles: number;
  categorized: number;
  uncategorized: number;
  multi_company_articles: number;
  by_source: { source: string; count: number }[];
  by_company: { company__symbol: string; company__name: string; count: number }[];
}


// ── Analysis ──────────────────────────────────────────────────────────

export type Pressure = 'buying' | 'selling' | 'neutral';

export interface DailyAnalysis {
  id: number;
  company: number;
  symbol: string;
  company_name: string;
  date: string;
  vwap: string | null;
  close_price: string;
  volume: number;
  volume_average: string | null;
  volume_anomaly: boolean;
  pressure: Pressure;
  news_count: number;
  created_at: string;
}

export interface BehaviorSummary {
  company_id: number;
  symbol: string;
  company_name: string;
  latest_close: string | null;
  latest_vwap: string | null;
  current_pressure: Pressure | null;
  volume_anomaly_days: number;
  anomaly_threshold_multiplier: number;
  avg_daily_volume: number | null;
  daily_analysis: DailyAnalysis[];
}

export interface NewsPriceCorrelation {
  date: string;
  news_count: number;
  avg_sentiment: number | null;
  next_day_price_change_pct: number | null;
  next_day_volume_change_pct: number | null;
  pressure: Pressure | null;
}

export interface BrokerRow {
  buyer_broker?: string;
  seller_broker?: string;
  total_quantity: number;
  total_amount: number;
  transaction_count: number;
}

export interface TopBrokers {
  company_id: number;
  symbol: string;
  top_buyers: BrokerRow[];
  top_sellers: BrokerRow[];
}

export interface CompanyBehaviorOverview {
  company_id: number;
  symbol: string;
  company_name: string;
  sector: string;
  latest_close: number | null;
  latest_vwap: number | null;
  pressure: Pressure;
  volume_anomaly: boolean;
  anomaly_count_30d: number;
  total_news: number;
}

// ── Crawler ───────────────────────────────────────────────────────────

export type CrawlStatus = 'running' | 'success' | 'failed' | 'pending' | 'cancelled';

export interface CrawlRun {
  id: number;
  status: CrawlStatus;
  sources: string[];
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  articles_found: number;
  articles_created: number;
  articles_updated: number;
  errors: string | null;
}

// ── Auth ──────────────────────────────────────────────────────────────

export type UserRole = 'admin' | 'analyst' | 'viewer';

export interface User { id: number;
   username: string;
    email: string;
     first_name: string;
      last_name: string; 
      role: UserRole; 
      is_active: boolean;
       date_joined: string; 
       last_login: string | null; }

// ── Pagination ────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface AdminDashboard {
           role: 'admin'; 
           users_count: number;
            active_users: number; 
            tracked_companies: number;
             crawl_runs_count: number; 
             latest_crawl: 
             { id: number; status: string; started_at: string; completed_at: string | null; } | null; }


export interface AnalystDashboard { role: 'analyst'; tracked_companies: number; total_news: number; corrections_count: number; } export interface ViewerDashboard { role: 'viewer'; tracked_companies: number; total_news: number; } export interface DashboardSummary { tracked_companies: number; total_news: number; total_trading_days: number; total_floorsheet_transactions: number; market_volume: number; market_turnover: number; positive_news: number; negative_news: number;
     neutral_news: number; }