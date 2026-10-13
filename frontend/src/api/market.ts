import { apiClient } from './client';
import type { PaginatedResponse, NewsArticle } from '../types';

// /api/market/ — the TRACKED COMPANIES dashboard (not the whole NEPSE market).
// The API returns raw numbers (NPR, shares, percent); format with components/market/format.ts.

export interface SparkPoint { date: string; close: number }

export type MoverBucket =
  | 'gainer' | 'loser' | 'unchanged'
  | 'missing_price' | 'not_traded' | 'missing_previous_session' | 'prev_close_zero' | 'possible_corporate_action';

export type ExclusionReason = 'missing_price' | 'not_traded' | 'missing_previous_session' | 'prev_close_zero' | 'possible_corporate_action';

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
  /** Tracked companies with no crawled row on as_of. */
  missing_price_count?: number;
  excluded_counts?: Record<ExclusionReason, number>;
  provenance: Provenance;
  reason?: string;
  /** Set when some tracked companies have no crawled price on as_of. */
  warning?: string;
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
  warning?: string;
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

/** One tracked company's intraday move from NEPSE's live feed (Backend services/live_prices.py). */
export interface LiveMoverRow {
  company_id: number;
  symbol: string;
  name: string;
  sector: string;
  logo_url: string | null;
  /** Last traded price. */
  close: number;
  prev_close: number;
  change: number;
  change_pct: number;
  last_traded_at: string;
}

export interface LiveMoversResponse {
  live: true;
  source: string;
  /** Time of the latest trade seen in the feed. */
  as_of: string | null;
  session_date: string | null;
  /** When the server last fetched and saved the feed successfully. */
  last_successful_fetch: string | null;
  /** Market open, but no successful fetch in the last 10 minutes. */
  stale: boolean;
  tracked_count: number;
  gainers_count: number;
  losers_count: number;
  unchanged_count: number;
  gainers: LiveMoverRow[];
  losers: LiveMoverRow[];
  /** Tracked companies with no trade yet in this session. */
  not_traded: string[];
  reason?: string;
  action?: string;
}

export type TopMetric = 'turnover' | 'volume' | 'transactions';

// --- Market Overview card (/api/market/overview/) ---------------------------------------------

export type OverviewRange = '1D' | '1W' | '1M' | '3M' | '6M' | '1Y' | '5Y' | 'ALL';
export type MarketStatus = 'OPEN' | 'CLOSE';

export interface OverviewInstrument { symbol: string; name: string; kind: 'index' | 'company' }

export interface OverviewQuote extends OverviewInstrument {
  /** True when the value comes from today's live feed rather than the last stored session. */
  live: boolean;
  value: number | null;
  change: number | null;
  change_pct: number | null;
  as_of: string | null;
}

/** Session stats for the tracked companies (same buckets as /market/summary/). */
export interface OverviewStats {
  advanced: number;
  declined: number;
  unchanged: number;
  positive_circuit: number;
  negative_circuit: number;
  not_ranked: number;
  total_turnover: number | null;
  /** Nepali digit grouping, e.g. "4,46,52,46,360.73". */
  total_turnover_display: string | null;
  total_traded_shares: number | null;
  total_transactions: number | null;
  transactions_reported: number;
  total_scrips_traded: number;
  tracked_count: number;
  circuit_threshold_pct: number;
}

export interface MarketOverview {
  instrument: OverviewQuote;
  status: MarketStatus;
  timestamp: string | null;
  stats_label: string;
  trade_date: string | null;
  stats: OverviewStats | null;
  instruments: OverviewInstrument[];
  reason: string | null;
}

export interface ChartPoint {
  t: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number | null;
}

export interface OverviewChart {
  symbol: string;
  range: OverviewRange;
  interval: 'intraday' | 'daily';
  date?: string | null;
  available_ranges: OverviewRange[];
  points: ChartPoint[];
  reason?: string;
}

export type TechnicalSignal = 'Buy' | 'Sell' | 'Neutral';
export type OverallSignal = TechnicalSignal | 'Strong Buy' | 'Strong Sell';

export interface TechnicalIndicator {
  key: string;
  name: string;
  value: number | null;
  signal: TechnicalSignal | null;
  /** False for ATR: shown, but not counted in the summary. */
  votes: boolean;
  values: Record<string, number | null>;
}

export interface TechnicalAnalysis {
  symbol: string;
  kind: 'index' | 'company';
  as_of: string | null;
  sessions_used: number;
  history_start: string | null;
  adjusted_sessions: string[];
  corporate_action_cutoff: string | null;
  close: number | null;
  indicators: TechnicalIndicator[];
  pivots: { session: string; based_on: string; method: string; levels: Record<'p' | 'r1' | 's1' | 'r2' | 's2' | 'r3' | 's3', number | null> } | null;
  summary: { buy: number; neutral: number; sell: number; total: number; signal: OverallSignal | null };
  disclaimer: string;
}

const get = <T,>(url: string, params?: Record<string, unknown>) =>
  apiClient.get<T>(url, { params }).then((response) => response.data);

export const marketApi = {
  summary: (date?: string) =>
    get<Scoped & { summary: TrackedSummary; circuit_threshold_pct: number; provenance: Provenance; note: string }>('/market/summary/', { date }),
  movers: (period: MoverPeriod = '1D', limit = 5, date?: string) =>
    get<Scoped & MoversResponse>('/market/movers/', { period, limit, date }),
  liveMovers: (limit = 10) => get<Scoped & LiveMoversResponse>('/market/movers/live/', { limit }),
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
  overview: (symbol: string) => get<Scoped & MarketOverview>('/market/overview/', { symbol }),
  overviewChart: (symbol: string, range: OverviewRange) => get<Scoped & OverviewChart>('/market/overview/chart/', { symbol, range }),
  overviewTechnical: (symbol: string) => get<Scoped & TechnicalAnalysis>('/market/overview/technical/', { symbol }),
};
