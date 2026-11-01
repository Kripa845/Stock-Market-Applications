import { apiClient } from './client';

// Stock comparison (/api/compare/).  Every figure is computed by the backend
// (apps/comparison/services/compare.py); null always comes with a reason in
// data_quality.null_fields and is shown as "—", never 0.

type Num = number | string | null;

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
  face_value_source: 'dividend_announcement' | 'default_100';
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
  earning_trend_5q: Num;
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
  /** Set instead of the sections when this company's profile failed. */
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

/** Error body for 400 / 403 responses. */
export interface CompareError { detail: string; code: string; invalid_symbols?: string[]; denied_symbols?: string[] }

export const MIN_SYMBOLS = 2;
export const MAX_SYMBOLS = 5;

export const compareApi = {
  compare: (symbols: string[]) =>
    apiClient
      .get<CompareResponse>('/compare/', { params: { symbols: symbols.join(',') } })
      .then((response) => response.data),
  companies: () =>
    apiClient.get<CompareCompaniesResponse>('/compare/companies/').then((response) => response.data),
};

/** Human labels for the backend's null reason codes. */
export const NULL_REASON_LABELS: Record<string, string> = {
  no_data: 'No data',
  insufficient_history: 'Not enough history',
  needs_more_quarterly_data: 'Needs more quarterly reports',
  no_source_column: 'No source data',
  no_dividend_history: 'No dividend record',
  negative_eps: 'EPS is negative',
  no_price: 'No price',
  possible_corporate_action: 'Possible corporate action',
  not_computed: 'Not computed yet',
  no_price_movement: 'No price movement',
  non_positive_book_value: 'Book value ≤ 0',
  missing_price: 'No price for the session',
  missing_previous_session: 'No previous session',
  not_traded: 'Not traded',
};
