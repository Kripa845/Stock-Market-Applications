import { apiClient } from './client';
import type { IndexRow } from './marketIndices';
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

export type DividendStatus = 'proposed' | 'agm_approved' | 'sebon_approved' | 'distributed';

export type DividendFlag =
  | 'missing_symbol' | 'missing_fiscal_year' | 'no_price' | 'no_face_value' | 'no_eps';

/** One proposed dividend of a tracked company (definitions: Backend services/dividends.py). */
export interface DividendRow {
  id: number;
  /** '' when the crawled row had no symbol (flags has 'missing_symbol'). */
  symbol: string;
  name: string;
  logo_url: string | null;
  /** '' when the crawled row had no fiscal year (flags has 'missing_fiscal_year'). */
  fiscal_year: string;
  status: DividendStatus;
  bonus_pct: number;
  cash_pct: number;
  total_pct: number;
  announcement_date: string | null;
  book_closure_date: string | null;
  distribution_date: string | null;
  bonus_listing_date: string | null;
  face_value: number | null;
  /** Latest crawled close and its session date. */
  price: number | null;
  price_date: string | null;
  /** Full-year (Q4) EPS of the same fiscal year. */
  eps: number | null;
  cash_dps: number | null;
  dividend_yield_pct: number | null;
  cash_payout_pct: number | null;
  payout_pct: number | null;
  /** Null when there is no bonus, no price, or the price is already ex-bonus. */
  ex_bonus_price: number | null;
  flags: DividendFlag[];
  scraped_at: string | null;
}

export interface DividendsResponse {
  scope: 'tracked_companies';
  fiscal_year: string;
  fiscal_years: string[];
  statuses: { value: DividendStatus; label: string }[];
  status_note: string;
  last_scraped_at: string | null;
  last_crawl: { id: number; status: string; started_at: string | null; completed_at: string | null } | null;
  rows: DividendRow[];
}

export type WatchlistRow = Partial<TrackedRow> & {
  watchlist_id: number;
  company_id: number;
  symbol: string;
  name: string;
  bucket: MoverBucket | 'not_tracked';
};

/** A named watchlist ("Primary", "Banks", ...); the starred one is the default. */
export interface NamedWatchlist {
  id: number;
  name: string;
  is_default: boolean;
  item_count: number | null;
  created_at: string;
}

/** A saved company: its latest crawled session plus the user's holding (Backend services/watchlist.py). */
export interface WatchlistItemRow {
  id: number;
  watchlist_id: number;
  company_id: number;
  symbol: string;
  name: string;
  sector: string;
  logo_url: string | null;
  /** Session behind ltp/high/low/volume/turnover; null when the company was never crawled. */
  trade_date: string | null;
  ltp: number | null;
  high: number | null;
  low: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number | null;
  turnover: number | null;
  sparkline: SparkPoint[];
  units: number;
  wacc: number;
  current_value: number | null;
  investment: number;
  profit: number | null;
  profit_pct: number | null;
}

export interface WatchlistSummary {
  total_units: number;
  average_wacc: number;
  current_value: number;
  investment: number;
  profit: number;
  profit_pct: number;
}

export interface WatchlistItemsResponse {
  watchlist: NamedWatchlist;
  rows: WatchlistItemRow[];
  summary: WatchlistSummary;
  price_source: string;
}

export interface WatchlistHolding { units?: number; wacc?: number }

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

// --- Top Gainers / Losers pages (/api/market/top-gainers/) -------------------------------------

export type TopMoversSide = 'gainers' | 'losers';
export type TopMoversPeriod = 'today' | '2d' | '3d' | '5d' | '7d' | '1w' | '1m' | '3m' | '4m' | '6m' | '1y';

export interface TopMoversRow {
  symbol: string;
  name: string;
  logo_url: string | null;
  sector: string;
  /** Last traded price (live) or the session close. */
  ltp: number;
  change: number;
  change_pct: number;
  /** % measured against an exchange-adjusted previous close (bonus / right shares). */
  adjusted: boolean;
  /** ISO time in Nepal time of the last trade; null when not known for that session. */
  last_updated: string | null;
}

export interface TopMoversParams {
  type: TopMoversSide;
  period: TopMoversPeriod;
  sector?: string;
  adjusted: boolean;
  page: number;
  page_size: number;
}

export interface TopMoversResponse {
  side: TopMoversSide;
  period: TopMoversPeriod;
  period_label: string;
  adjusted: boolean;
  sectors: string[];
  /** Today from NEPSE's live feed (unofficial until the close). */
  live: boolean;
  stale?: boolean;
  market_open: boolean;
  as_of: string | null;
  base_date: string | null;
  total: number;
  page: number;
  page_size: number;
  pages: number;
  rows: TopMoversRow[];
  reason?: string;
  action?: string;
}

// --- Top Turnover / Volume / Transactions pages (/api/market/top-activity/) -------------------

export type ActivityMetric = 'turnover' | 'volume' | 'transactions';

export interface TopActivityRow {
  symbol: string;
  name: string;
  logo_url: string | null;
  sector: string;
  /** Close on the latest session; null when the company did not trade that day. */
  ltp: number | null;
  /** Price change over the period; null when it cannot be measured (no trade, new listing). */
  change_pct: number | null;
  /** The metric summed over the period's sessions. */
  value: number;
  sessions_traded: number;
  /** False when some traded sessions have no trade count yet (transactions only). */
  complete: boolean;
}

export interface TopActivityResponse {
  metric: ActivityMetric;
  period: TopMoversPeriod;
  period_label: string;
  sectors: string[];
  market_open: boolean;
  as_of: string | null;
  base_date: string | null;
  /** First session included in the sum. */
  first_session: string | null;
  total: number;
  page: number;
  page_size: number;
  pages: number;
  rows: TopActivityRow[];
  reason?: string;
  warning?: string;
}


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
  /** 1D only: the Nepal-time session the ticks belong to, and whether it is trading right now. */
  session_date?: string | null;
  is_live?: boolean;
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

/** One ranked row on the public landing page (GET /market/public/snapshot/, no login needed). */
export type PublicMarketRow = Pick<TrackedRow, 'symbol' | 'name' | 'close' | 'change' | 'change_pct' | 'turnover' | 'volume' | 'transactions'>;

export interface PublicMarketSnapshot {
  scope: 'tracked_companies';
  nepse: OverviewQuote;
  status: MarketStatus;
  stats: OverviewStats | null;
  stats_label: string;
  indices: { as_of: string | null; rows: IndexRow[] };
  sub_indices: { as_of: string | null; rows: IndexRow[] };
  /** Latest crawled session behind the ranked lists. */
  as_of: string | null;
  gainers: PublicMarketRow[];
  losers: PublicMarketRow[];
  top_turnover: PublicMarketRow[];
  top_volume: PublicMarketRow[];
  top_transactions: PublicMarketRow[];
}

const get = <T,>(url: string, params?: Record<string, unknown>) =>
  apiClient.get<T>(url, { params }).then((response) => response.data);

export const marketApi = {
  publicSnapshot: () => get<PublicMarketSnapshot>('/market/public/snapshot/'),
  publicChart: (range: OverviewRange) => get<OverviewChart>('/market/public/chart/', { range }),
  summary: (date?: string) =>
    get<Scoped & { summary: TrackedSummary; circuit_threshold_pct: number; provenance: Provenance; note: string }>('/market/summary/', { date }),
  movers: (period: MoverPeriod = '1D', limit = 5, date?: string) =>
    get<Scoped & MoversResponse>('/market/movers/', { period, limit, date }),
  liveMovers: (limit = 10) => get<Scoped & LiveMoversResponse>('/market/movers/live/', { limit }),
  topMovers: ({ sector, ...params }: TopMoversParams) =>
    get<Scoped & TopMoversResponse>('/market/top-gainers/', { ...params, sector: sector || undefined }),
  topActivity: (params: { metric: ActivityMetric; period: TopMoversPeriod; sector?: string; page: number; page_size: number }) =>
    get<Scoped & TopActivityResponse>('/market/top-activity/', { ...params, sector: params.sector || undefined }),
  top: (metric: TopMetric, limit = 10) =>
    get<Scoped & { trade_date: string | null; rows: TrackedRow[]; reason?: string }>(`/market/top-${metric}/`, { limit }),
  brokers: (symbol: string) => get<Scoped & { symbol: string; windows: BrokerWindow[]; share_denominator: string }>(`/market/brokers/${symbol}/`),
  signals: (symbol: string) => get<Scoped & { signals: Signals | null }>(`/market/signals/${symbol}/`),
  basket: (days?: number) => get<Scoped & BasketIndex>('/market/basket-index/', { days }),
  dividends: (params: { fiscal_year?: string; status?: string } = {}) =>
    get<DividendsResponse>('/market/dividends/', { fiscal_year: params.fiscal_year || undefined, status: params.status || undefined }),
  watchlist: () => get<Scoped & { as_of: string | null; rows: WatchlistRow[]; provenance: Provenance }>('/market/watchlist/'),
  addToWatchlist: (symbol: string) => apiClient.post<WatchlistRow>('/market/watchlist/', { symbol }).then((r) => r.data),
  removeFromWatchlist: (symbol: string) => apiClient.delete(`/market/watchlist/${symbol}/`),
  watchlists: () => get<{ results: NamedWatchlist[] }>('/market/watchlists/').then((d) => d.results),
  createWatchlist: (name: string) =>
    apiClient.post<NamedWatchlist>('/market/watchlists/', { name }).then((r) => r.data),
  updateWatchlist: (id: number, changes: { name?: string; is_default?: boolean }) =>
    apiClient.patch<NamedWatchlist>(`/market/watchlists/${id}/`, changes).then((r) => r.data),
  deleteWatchlist: (id: number) => apiClient.delete(`/market/watchlists/${id}/`),
  watchlistItems: (id: number) => get<WatchlistItemsResponse>(`/market/watchlists/${id}/items/`),
  addWatchlistItem: (id: number, symbol: string, holding: WatchlistHolding = {}) =>
    apiClient.post<WatchlistItemRow>(`/market/watchlists/${id}/items/`, { symbol, ...holding }).then((r) => r.data),
  updateWatchlistItem: (id: number, itemId: number, holding: WatchlistHolding) =>
    apiClient.patch<WatchlistItemRow>(`/market/watchlists/${id}/items/${itemId}/`, holding).then((r) => r.data),
  removeWatchlistItem: (id: number, itemId: number) => apiClient.delete(`/market/watchlists/${id}/items/${itemId}/`),
  companyNews: (symbol: string) => get<PaginatedResponse<NewsArticle>>(`/market/news/${symbol}/`),
  overview: (symbol: string) => get<Scoped & MarketOverview>('/market/overview/', { symbol }),
  overviewChart: (symbol: string, range: OverviewRange) => get<Scoped & OverviewChart>('/market/overview/chart/', { symbol, range }),
  overviewTechnical: (symbol: string) => get<Scoped & TechnicalAnalysis>('/market/overview/technical/', { symbol }),
};
