// ── Company & Market Data ─────────────────────────────────────────────
// Company is defined in ./company.ts — re-exported here for backwards
// compatibility with files that import from '../types'.
export type { Company } from './company';
import type { Company } from './company';

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
  buyer_broker_name: string;
  buyer_broker_short_name: string;
  buyer_broker_logo_url: string | null;
  seller_broker_name: string;
  seller_broker_short_name: string;
  seller_broker_logo_url: string | null;
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
  /** Lead image on the source portal; empty when the page had none. */
  image_url?: string;
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
// These types are re-exported from api/analysis.ts which is the
// single source of truth for analysis-related shapes.
// Kept here only for backwards-compatibility with existing imports.
export type { PressureLabel as Pressure } from '../api/analysis';
export type {
  DailyAnalysis,
  BehaviorSummary,
  NewsPriceCorrelation,
  CompanyStat as CompanyBehaviorOverview,
  BrokerActivity as BrokerRow,
  CrossCompanyAnalysis,
} from '../api/analysis';

// ── Crawler ───────────────────────────────────────────────────────────
// CrawlStatus, CrawlType, and CrawlRun are defined in ./crawl.ts —
// re-exported here for backwards compatibility.
export type { CrawlStatus, CrawlType, CrawlRun } from './crawl';

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


export interface AnalystDashboard { role: 'analyst'; tracked_companies: number; total_news: number; corrections_count: number; } export interface ViewerDashboard { role: 'viewer'; tracked_companies: number; total_news: number; companies?: Company[]; } export interface DashboardSummary { tracked_companies: number; total_news: number; total_trading_days: number; total_floorsheet_transactions: number; market_volume: number; market_turnover: number; positive_news: number; negative_news: number;
     neutral_news: number; }
