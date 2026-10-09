import { apiClient } from './client';
import type { PaginatedResponse, NewsArticle } from '../types';

// /api/market/ — the TRACKED COMPANIES dashboard (not the whole NEPSE market).
// The API returns raw numbers (NPR, shares, percent); format with components/market/format.ts.

export interface SparkPoint { date: string; close: number }

export type MoverBucket =
  | 'gainer' | 'loser' | 'unchanged'
  | 'not_traded' | 'missing_previous_session' | 'prev_close_zero' | 'possible_corporate_action';

export type ExclusionReason = 'not_traded' | 'missing_previous_session' | 'prev_close_zero' | 'possible_corporate_action';

/** One tracked company's change over the period (definition: Backend services/movers.py). */
export interface TrackedRow {
  company_id: number;
  symbol: string;
  name: string;
  sector: string;
  logo_url: string | null;
  bucket: MoverBucket;
  close: number | null;
  /** Reference price behind change_pct (source-adjusted when change_basis = 'source'). */
  prev_close: number | null;
  change: number | null;
  change_pct: number | null;
  /** Stored close on the base session, unadjusted. */
  raw_prev_close: number | null;
  close_to_close_change_pct: number | null;
  change_basis: 'source' | 'close_to_close';
  /** Source % differs from close-to-close by > 0.05 (e.g. bonus book closure). */
  adjusted: boolean;
  /** No source % for the whole period: plain close-to-close. */
  unadjusted: boolean;
  possible_corporate_action: boolean;
  volume: number | null;
  turnover: number | null;
  transactions: number | null;
  price_source: string | null;
  sparkline?: SparkPoint[];
}

export interface Provenance {
  table: string;
  price_source: string;
  change_source: string;
  latest_crawled_trade_date: string | null;
  last_price_crawl: { id: number; status: string; started_at: string | null; completed_at: string | null } | null;
}

export type MoverPeriod = '1D' | '5S' | '20S';

export interface MoversResponse {
  scope: 'tracked_companies';
  as_of: string | null;
  period: MoverPeriod;
  period_label: string;
  base_date: string | null;
  gainers: TrackedRow[];
  losers: TrackedRow[];
  unchanged: TrackedRow[];
  excluded: TrackedRow[];
  tracked_count: number;
  gainers_count?: number;
  losers_count?: number;
  unchanged_count?: number;
  not_traded_count?: number;
  excluded_counts?: Record<ExclusionReason, number>;
  provenance: Provenance;
  reason?: string;
  action?: string;
  note?: string;
}

export interface TrackedSummary {
  trade_date: string | null;
  previous_trade_date?: string | null;
  tracked_count: number;
  advanced: number;
  declined: number;
  unchanged: number;
  excluded_counts: Record<ExclusionReason, number>;
  adjusted_count?: number;
  positive_circuit: number;
  negative_circuit: number;
  total_turnover: number | null;
  total_traded_shares: number | null;
  total_transactions?: number | null;
  transactions_reported?: number;
  reason?: string;
  action?: string;
}

export interface BasketRow {
  date: string;
  level: number | null;
  daily_return_pct: number | null;
  equal_weight_level: number | null;
  equal_weight_return_pct: number | null;
  eligible_company_count: number;
}

export interface BasketIndex { label: string; base_level: number; rows: BasketRow[] }

interface Scoped { scope: 'tracked_companies'; units: Record<string, string> }

export type PublicMover = Pick<TrackedRow,
  'symbol' | 'name' | 'sector' | 'close' | 'prev_close' | 'change' | 'change_pct' | 'adjusted' | 'unadjusted' | 'volume' | 'turnover' | 'sparkline'>;

export interface PublicSnapshot extends Scoped {
  as_of: string | null;
  period_label: string;
  summary: Pick<TrackedSummary, 'tracked_count' | 'advanced' | 'declined' | 'unchanged' | 'excluded_counts'
    | 'positive_circuit' | 'negative_circuit' | 'total_turnover' | 'total_traded_shares'>;
  gainers: PublicMover[];
  losers: PublicMover[];
  basket: BasketIndex;
  provenance: Provenance;
  reason: string | null;
}

export interface BrokerRow {
  broker: string;
  broker_name: string;
  buy_quantity: number;
  buy_amount: number;
  sell_quantity: number;
  sell_amount: number;
  turnover: number;
  net_quantity: number;
  net_amount: number;
  share_pct: number | null;
  volume_share_pct: number | null;
}

export interface BrokerWindow {
  sessions: number;
  sessions_available: number;
  start_date: string | null;
  end_date: string | null;
  total_amount: number | null;
  total_quantity: number | null;
  total_trades: number;
  brokers: BrokerRow[];
  top_buyers: BrokerRow[];
  top_sellers: BrokerRow[];
  concentration: { top_n: number; brokers: string[]; volume_share_pct: number } | null;
}

interface WindowedValue { value: number | null; sessions: number; required_sessions: number }

export interface Signals {
  symbol: string;
  trade_date: string;
  close: number;
  volume: number;
  volume_vs_20d_avg: { average_volume: number | null; ratio: number | null; sessions: number; required_sessions: number };
  moving_averages: { ma5: WindowedValue; ma20: WindowedValue; close_vs_ma5_pct: number | null; close_vs_ma20_pct: number | null };
  range_52w: {
    high: number | null; low: number | null; sessions: number; first_date: string | null;
    distance_from_high_pct: number | null; distance_from_low_pct: number | null;
  };
}

export interface DividendRow {
  id: number;
  symbol: string;
  name: string;
  logo_url: string | null;
  fiscal_year: string;
  bonus_pct: number;
  cash_pct: number;
  total_pct: number;
  book_closure_date: string | null;
}

export type WatchlistRow = Partial<TrackedRow> & {
  watchlist_id: number;
  company_id: number;
  symbol: string;
  name: string;
  bucket: MoverBucket | 'not_tracked';
};

export type TopMetric = 'turnover' | 'volume' | 'transactions';

const get = <T,>(url: string, params?: Record<string, unknown>) =>
  apiClient.get<T>(url, { params }).then((response) => response.data);

export const marketApi = {
  publicSnapshot: () => get<PublicSnapshot>('/market/public/snapshot/'),
  summary: (date?: string) =>
    get<Scoped & { summary: TrackedSummary; circuit_threshold_pct: number; provenance: Provenance; note: string }>('/market/summary/', { date }),
  movers: (period: MoverPeriod = '1D', limit = 5, date?: string) =>
    get<Scoped & MoversResponse>('/market/movers/', { period, limit, date }),
  top: (metric: TopMetric, limit = 10) =>
    get<Scoped & { trade_date: string | null; rows: TrackedRow[]; reason?: string }>(`/market/top-${metric}/`, { limit }),
  brokers: (symbol: string) => get<Scoped & { symbol: string; windows: BrokerWindow[]; share_denominator: string }>(`/market/brokers/${symbol}/`),
  signals: (symbol: string) => get<Scoped & { signals: Signals | null }>(`/market/signals/${symbol}/`),
  basket: (days?: number) => get<Scoped & BasketIndex>('/market/basket-index/', { days }),
  dividends: () => get<Scoped & { rows: DividendRow[] }>('/market/dividends/'),
  watchlist: () => get<Scoped & { as_of: string | null; rows: WatchlistRow[]; provenance: Provenance }>('/market/watchlist/'),
  addToWatchlist: (symbol: string) => apiClient.post<WatchlistRow>('/market/watchlist/', { symbol }).then((r) => r.data),
  removeFromWatchlist: (symbol: string) => apiClient.delete(`/market/watchlist/${symbol}/`),
  companyNews: (symbol: string) => get<PaginatedResponse<NewsArticle>>(`/market/news/${symbol}/`),
};
