import { apiClient } from './client';
import type { PaginatedResponse, NewsArticle } from '../types';

// /api/market/ — the TRACKED COMPANIES dashboard (not the whole NEPSE market).
// The API returns raw numbers (NPR, shares, percent); format with components/market/format.ts.

export interface SparkPoint { date: string; close: number }

export interface TrackedRow {
  company_id: number;
  symbol: string;
  name: string;
  sector: string;
  date: string;
  ltp: number | null;
  prev_close: number | null;
  change: number | null;
  change_pct: number | null;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  turnover: number;
  transactions: number | null;
  book_closure_in_window?: boolean;
  sparkline?: SparkPoint[];
}

export interface TrackedSummary {
  trade_date: string | null;
  tracked_count: number;
  advanced: number;
  declined: number;
  unchanged: number;
  no_prev_close: number;
  positive_circuit: number;
  negative_circuit: number;
  total_turnover: number | null;
  total_traded_shares: number | null;
  total_transactions?: number | null;
  transactions_reported?: number;
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

export interface PublicSnapshot extends Scoped {
  trade_date: string | null;
  summary: Omit<TrackedSummary, 'trade_date'>;
  movers: Pick<TrackedRow, 'symbol' | 'name' | 'sector' | 'ltp' | 'prev_close' | 'change' | 'change_pct' | 'volume' | 'turnover' | 'sparkline'>[];
  basket: BasketIndex;
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
  ltp: number;
  volume: number;
  volume_vs_20d_avg: { average_volume: number | null; ratio: number | null; sessions: number; required_sessions: number };
  moving_averages: { ma5: WindowedValue; ma20: WindowedValue; ltp_vs_ma5_pct: number | null; ltp_vs_ma20_pct: number | null };
  range_52w: {
    high: number | null; low: number | null; sessions: number; first_date: string | null;
    distance_from_high_pct: number | null; distance_from_low_pct: number | null;
  };
}

export interface DividendRow {
  id: number;
  symbol: string;
  name: string;
  fiscal_year: string;
  bonus_pct: number;
  cash_pct: number;
  total_pct: number;
  book_closure_date: string | null;
}

export interface WatchlistRow {
  id: number;
  company_id: number;
  symbol: string;
  name: string;
  trade_date: string | null;
  ltp: number | null;
  prev_close: number | null;
  change: number | null;
  change_pct: number | null;
}

export type TopMetric = 'turnover' | 'volume' | 'transactions';

const get = <T,>(url: string, params?: Record<string, unknown>) =>
  apiClient.get<T>(url, { params }).then((response) => response.data);

export const marketApi = {
  publicSnapshot: () => get<PublicSnapshot>('/market/public/snapshot/'),
  summary: (date?: string) => get<Scoped & { summary: TrackedSummary; circuit_threshold_pct: number; note: string }>('/market/summary/', { date }),
  movers: (date?: string) => get<Scoped & { trade_date: string | null; rows: TrackedRow[]; note: string }>('/market/movers/', { date }),
  top: (metric: TopMetric, limit = 10) => get<Scoped & { trade_date: string | null; rows: TrackedRow[] }>(`/market/top-${metric}/`, { limit }),
  brokers: (symbol: string) => get<Scoped & { symbol: string; windows: BrokerWindow[]; share_denominator: string }>(`/market/brokers/${symbol}/`),
  signals: (symbol: string) => get<Scoped & { signals: Signals | null }>(`/market/signals/${symbol}/`),
  basket: (days?: number) => get<Scoped & BasketIndex>('/market/basket-index/', { days }),
  dividends: () => get<Scoped & { rows: DividendRow[] }>('/market/dividends/'),
  watchlist: () => get<Scoped & { rows: WatchlistRow[] }>('/market/watchlist/'),
  addToWatchlist: (symbol: string) => apiClient.post<WatchlistRow>('/market/watchlist/', { symbol }).then((r) => r.data),
  removeFromWatchlist: (symbol: string) => apiClient.delete(`/market/watchlist/${symbol}/`),
  companyNews: (symbol: string) => get<PaginatedResponse<NewsArticle>>(`/market/news/${symbol}/`),
};
