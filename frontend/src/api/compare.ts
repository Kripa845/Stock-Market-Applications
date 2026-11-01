import { apiClient } from './client';

// Stock comparison (/api/compare/).  Every figure is computed by the backend
// (apps/comparison/services/compare.py); null always comes with a reason in
// data_quality.null_fields and is shown as "—", never 0.
//
// Dev only: VITE_COMPARE_MOCK=1 under `npm run dev` swaps in generated payloads
// (api/compareMock.ts) so the page can be worked on without the backend.  The page
// shows a banner while it is on; production builds never include the generator.

export type Num = number | string | null;

export interface PricePoint { date: string; close: Num }
export interface VolumePoint { date: string; volume: number }
export interface BrokerRow { broker_no: number | string; broker_name: string | null; quantity: number; pct_of_day_volume: Num }
export interface SmaBlock { value: Num; above: boolean }

export interface CompareGeneral {
  ltp: Num;
  ltp_source: 'daily_price' | 'company_live_feed' | null;
  previous_close: Num;
  change_pct: Num;
  price_trend_3m: PricePoint[] | null;
  week52_low: Num;
  week52_high: Num;
  listed_shares: number | null;
  face_value: Num;
  face_value_source: 'dividend_announcement' | 'default_100' | null;
  market_cap: Num;
  paid_up_capital: Num;
  reserve_surplus: Num;
  eps_ttm: Num;
  eps_reported: Num;
  eps_reported_flag: string | null;
  brokers_date: string | null;
  top_buy_brokers: BrokerRow[] | null;
  top_sell_brokers: BrokerRow[] | null;
}

export interface CompareDividend {
  fiscal_year: string;
  cash_pct: Num;
  bonus_pct: Num;
  total_pct: Num;
  status: string;
  book_closure_date: string | null;
}

export interface CompareFundamentals {
  report_period: string | null;
  pe: Num;
  pb: Num;
  roe: Num;
  dividend: CompareDividend | null;
  dividend_yield: Num;
  yoy_profit_growth: Num;
  /** Oldest first once quarterly history exists; null until then. */
  earning_trend_5q: Num[] | null;
  peg: Num;
  ps: Num;
  roa: Num;
  debt_equity: Num;
}

export interface CompareTechnicals {
  volume_trend: VolumePoint[] | null;
  rsi: Num;
  macd: Num;
  macd_signal: Num;
  macd_hist: Num;
  macd_label: 'Bullish' | 'Bearish' | null;
  sma50: SmaBlock | null;
  sma200: SmaBlock | null;
}

export interface NullField { field: string; reason: string; note?: string }
export interface QualityWarning { code: string; detail: string; sessions?: { date: string; fields: string[] }[] }

export interface CompareProfile {
  symbol: string;
  name: string;
  sector: string;
  /** Set (with detail) instead of the sections when this company's profile failed. */
  error?: string;
  detail?: string;
  general: CompareGeneral;
  fundamentals: CompareFundamentals;
  technicals: CompareTechnicals;
  data_quality: {
    price_as_of: string | null;
    expected_latest_session: string | null;
    snapshot_as_of: string | null;
    report_period: string | null;
    brokers_as_of: string | null;
    null_fields: NullField[];
    warnings: QualityWarning[];
  };
}

export interface CompareResponse { results: CompareProfile[]; universe_label: string }
export interface CompareCompany { symbol: string; name: string; sector: string }
export interface CompareCompaniesResponse { results: CompareCompany[]; sectors: string[] }

export interface CoverageRow {
  symbol: string;
  sector: string;
  error?: string;
  price_sessions: number;
  snapshot_sessions: number;
  quarters_in_quarterly_report: number;
  eps_present: boolean;
  book_value_present: boolean;
  listed_shares_present: boolean;
  dividend_rows: number;
  price_as_of: string | null;
  snapshot_as_of: string | null;
  null_fields: string[];
  problems: string[];
  sanity_checks_failed: string[];
}

export interface CoverageResponse {
  as_of: string;
  expected_latest_session: string;
  tracked_count: number;
  companies: CoverageRow[];
}

/** Body of 400 / 403 responses. */
export interface CompareError { detail: string; code: string; invalid_symbols?: string[]; denied_symbols?: string[]; duplicate_symbols?: string[] }

export const MIN_SYMBOLS = 2;
export const MAX_SYMBOLS = 5;

export const COMPARE_MOCK = import.meta.env.DEV && import.meta.env.VITE_COMPARE_MOCK === '1';
const mock = () => import('./compareMock');

export const compareApi = {
  compare: async (symbols: string[], date?: string) => {
    if (COMPARE_MOCK) return (await mock()).mockCompare(symbols, date);
    const params: Record<string, string> = { symbols: symbols.join(',') };
    if (date) params.date = date;
    return apiClient.get<CompareResponse>('/compare/', { params }).then((response) => response.data);
  },
  companies: async () => {
    if (COMPARE_MOCK) return (await mock()).mockCompanies();
    return apiClient.get<CompareCompaniesResponse>('/compare/companies/').then((response) => response.data);
  },
  coverage: async () => {
    if (COMPARE_MOCK) return (await mock()).mockCoverage();
    return apiClient.get<CoverageResponse>('/compare/coverage/').then((response) => response.data);
  },
};

/** Human labels for the backend's null reason codes; unknown codes are shown humanized. */
export const NULL_REASON_LABELS: Record<string, string> = {
  no_data: 'No data',
  insufficient_history: 'Not enough price history',
  needs_more_quarterly_data: 'Needs more quarterly reports',
  no_source_column: 'Not available from the data sources',
  no_dividend_history: 'No dividend record',
  negative_eps: 'EPS is negative, so P/E is not meaningful',
  no_price: 'No price',
  possible_corporate_action: 'Possible corporate action on this session',
  not_computed: 'Not computed yet',
  no_price_movement: 'No price movement in the lookback',
  non_positive_book_value: 'Book value is zero or negative',
  missing_price: 'No price for the session',
  missing_previous_session: 'No previous session',
  not_traded: 'Not traded',
};

export const humanize = (code: string) => code.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
export const reasonLabel = (code: string) => NULL_REASON_LABELS[code] ?? humanize(code);
