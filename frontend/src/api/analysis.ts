/**
 * analysis.ts
 *
 * All interfaces in this file are derived directly from the live backend
 * response shapes verified in the Django views.  Do not modify field names
 * without first confirming the change in the backend serializer/view.
 *
 * Relevant backend views:
 *   CompanyBehaviorSummaryAPIView   → /api/companies/<pk>/behavior/
 *   CompanyBrokerActivityAPIView    → /api/analysis/companies/<pk>/brokers/
 *   CompanyNewsPriceCorrelationAPIView → /api/companies/<pk>/news-correlation/
 *   CrossCompanyAnalysisAPIView     → /api/analysis/cross-company/
 *   DashboardSummaryAPIView         → /api/analysis/dashboard-summary/
 *   DailyAnalysisListAPIView        → /api/analysis/daily/
 */

import { apiClient } from './client';

// ─────────────────────────────────────────────────────────────────────────────
// Shared primitives
// ─────────────────────────────────────────────────────────────────────────────

export type PressureLabel = 'buying' | 'selling' | 'neutral';

// ─────────────────────────────────────────────────────────────────────────────
// DailyAnalysis
// Matches DailyAnalysisSerializer (apps/analysis/serializers.py)
// ─────────────────────────────────────────────────────────────────────────────

export interface PressureExplanation {
  method: string;
  score: number | null;
  score_range: [number, number];
  classification_band: number;
  inputs: {
    close: number | null;
    previous_close: number | null;
    daily_vwap: number | null;
    volume_ratio: number | null;
    volume_avg_20d: number | null;
  };
  missing_inputs: string[];
  is_complete: boolean;
  baseline_sessions_required: number;
  baseline_sessions_used: number;
  anomaly_threshold: number;
  disclaimer: string;
}

export interface DailyAnalysis {
  id: number;
  company: number;
  company_symbol: string;
  company_name: string;
  date: string;

  // VWAP — daily and 30-day aggregate are DISTINCT metrics
  vwap: string | null;          // daily VWAP = daily turnover / daily volume
  vwap_30d: string | null;      // rolling 30-day aggregate VWAP

  close_price: string;
  previous_close: string | null;
  daily_return_pct: string | null;  // (close - prev_close) / prev_close * 100

  // Volume — baseline is previous 20 TRADING SESSIONS, not calendar days
  volume: number;
  volume_average: string | null;    // mean of previous 20 sessions
  volume_avg_20d: string | null;    // alias for volume_average
  volume_ratio: string | null;      // today / prior 20-session SMA; anomaly ≥ 2.5
  volume_anomaly: boolean;
  volume_baseline_sessions: number;
  has_sufficient_history: boolean;
  pressure: PressureLabel;
  pressure_score: string | null;    // OHLCV proxy, -100..+100
  pressure_method: string;          // e.g. "OHLCV_PRICE_VOLUME"
  pressure_explanation: PressureExplanation;

  news_count: number;
  created_at: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Broker activity
// Matches BrokerActivitySerializer (apps/analysis/serializers.py)
// ─────────────────────────────────────────────────────────────────────────────

export interface BrokerActivity {
  broker: string;
  broker_code: string;
  broker_name?: string;
  name: string;
  short_name: string;
  logo_url: string | null;
  buy_quantity: number;
  sell_quantity: number;
  net_quantity: number;         // buy_quantity - sell_quantity
  buy_value: string;            // DecimalField 30/4
  sell_value: string;
  net_value: string;            // buy_value - sell_value
  total_quantity: number;
  total_value: string;
  buy_trades: number;
  sell_trades: number;
  trades: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Behavior Summary
// Matches CompanyBehaviorSummaryAPIView response (apps/analysis/views.py)
//
// Accessible at THREE equivalent URLs — use /api/companies/<pk>/behavior/
// ─────────────────────────────────────────────────────────────────────────────

export interface BehaviorSummary {
  company_id: number;
  symbol: string;
  name: string;
  sector: string;

  // Rolling window metadata (anchored to latest available trading date)
  window_start_date: string | null;
  window_end_date: string | null;
  latest_trading_date: string | null;
  unique_trading_dates: number;

  // Price anchors
  latest_price: string | null;        // close_price of latest session
  previous_close: string | null;
  daily_return_pct: string | null;

  // VWAP — daily and rolling 30-day are different numbers
  vwap: string | null;                // daily VWAP of latest session
  vwap_30d: string | null;            // 30-day rolling aggregate
  price_to_vwap_spread_pct: number | null;

  // Pressure — OHLCV proxy, not order-book evidence
  pressure: PressureLabel;
  pressure_score: string | null;      // -100..+100
  pressure_method: string;            // methodology identifier

  // Volume — baseline is 20 TRADING SESSIONS
  current_volume: number;
  volume_avg_20d: string | null;      // mean of previous 20 sessions
  volume_ratio: string | null;        // anomaly threshold ≥ 1.5
  volume_anomaly: boolean;
  volume_baseline_sessions: number;
  has_sufficient_history: boolean;
  volume_anomalies: {
    summary_count: number;
    results: Array<{
      date: string;
      volume: number;
      rolling_mean: number | null;
      rolling_std: number | null;
      z_score: number | null;
      pct_of_avg: number | null;
      is_anomaly: boolean;
      insufficient_data: boolean;
      reason: 'zscore' | 'multiplier' | 'both' | '';
    }>;
  };

  // Broker activity — from floorsheet sample, NOT a continuous series
  brokers: BrokerActivity[];          // top 10 by net_quantity
  most_active_buyer: string | null;   // broker id/name
  most_active_seller: string | null;
  top_net_buyer: string | null;
  top_net_seller: string | null;
  floorsheet_sampled_dates: string[];

  // News
  news_sentiment_score: number;       // average sentiment in window
  news_count_30d: number;

  // Human-readable summary from backend
  summary_text: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Broker Activity (standalone endpoint)
// Matches CompanyBrokerActivityAPIView response
// ─────────────────────────────────────────────────────────────────────────────

export interface BrokerActivityResponse {
  company_id: number;
  symbol: string;
  brokers: BrokerActivity[];
  broker_count: number;
  transaction_count: number;
  total_buy_quantity: number;
  total_sell_quantity: number;
  total_buy_value: string;
  total_sell_value: string;
  most_active_buyer: string | null;
  most_active_seller: string | null;
  top_net_buyer: string | null;
  top_net_seller: string | null;
  sampled_dates: string[];
  note: string;
}

export interface BrokerCompanyChoice {
  id: number;
  symbol: string;
  name: string;
}

export interface BrokerAnalysisResponse {
  count: number;
  page: number;
  page_size: number;
  next: number | null;
  previous: number | null;
  results: BrokerActivity[];
  broker_options: string[];
  broker_directory: Array<{ broker_code: string; name: string; short_name: string; logo_url: string | null }>;
  companies: BrokerCompanyChoice[];
  summary: {
    total_buy_quantity: number;
    total_sell_quantity: number;
    total_activity: number;
    total_buy_value: string;
    total_sell_value: string;
    total_turnover: string;
    active_brokers: number;
    sampled_trading_days: number;
    transaction_count: number;
  };
  most_active_buyers: BrokerActivity[];
  most_active_sellers: BrokerActivity[];
  top_net_buyers: BrokerActivity[];
  top_net_sellers: BrokerActivity[];
  sampled_dates: string[];
  note: string;
}

export interface BrokerDetailResponse {
  broker: string;
  company_options: BrokerCompanyChoice[];
  summary: BrokerActivity;
  daily_activity: Array<{
    date: string;
    buy_quantity: number;
    sell_quantity: number;
    buy_value: string;
    sell_value: string;
    net_value: string;
    net_quantity: number;
    high_rate: string | null;
    low_rate: string | null;
    largest_trade: string | null;
    trades: number;
  }>;
  companies: Array<{
    company_id: number;
    symbol: string;
    name: string;
    sector: string;
    buy_quantity: number;
    sell_quantity: number;
    buy_value: string;
    sell_value: string;
    net_value: string;
    net_quantity: number;
    trades: number;
  }>;
  sampled_dates: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// News-Price Correlation
// Matches CompanyNewsPriceCorrelationAPIView response
//
// NOTE: This is computed on-the-fly from DailyPrice + ArticleCompanyTag.
// There is no NewsPriceCorrelation database model.
// Window = last 60 calendar days anchored to today.
// ─────────────────────────────────────────────────────────────────────────────

export interface CorrelationDataPoint {
  date: string;
  close: number;
  price_change_pct: number;     // (close - prev_close) / prev_close * 100
  volume: number;
  news_count: number;           // articles tagged to this company on this date
  sentiment_score: number;      // avg sentiment of articles on this date (0 if none)
}

export interface NewsPriceCorrelation {
  company_id: number;
  symbol: string;
  // Pearson r between sentiment and next-day price change; null if < 3 observations
  correlation_coefficient: number | null;
  correlation_label: string;    // e.g. "Moderate-to-Strong Positive" or "Neutral"
  lead_lag_days: number;        // always 1 in current implementation
  analysis_note: string;
  data_points: CorrelationDataPoint[];  // one entry per trading day in window
  market_reaction: {
    minimum_observations: number;
    observations: number;
    events: Array<{
      news_date: string;
      article_count: number;
      positive_count: number;
      neutral_count: number;
      negative_count: number;
      sentiment_score: number | null;
      baseline_date: string | null;
      sessions: Array<{
        label: 'News Day' | 'T+1' | 'T+2';
        date: string;
        close: number;
        volume: number;
        price_return_pct: number | null;
        volume_change_pct: number | null;
      } | null>;
    }>;
    correlations: {
      sentiment_t1_return: { coefficient: number | null; observations: number };
      sentiment_t2_return: { coefficient: number | null; observations: number };
      news_volume_t1_change: { coefficient: number | null; observations: number };
      news_volume_t2_change: { coefficient: number | null; observations: number };
    };
    baseline_note: string;
    disclaimer: string;
  };
  method?: string;
  confidence_floor?: number;
  min_n_for_reliable?: number;
  lags_days?: number[];
  caveat?: string;
  computed_at?: string;
  by_lag?: Record<string, Record<string, {
    n: number;
    pearson_r: number | null;
    pearson_p: number | null;
    spearman_rho: number | null;
    spearman_p: number | null;
    reliable: boolean;
  }>>;
}

export interface ForwardCorrelationMetric {
  coefficient: number | null;
  observations: number;
}

export interface NewsSentimentDailyPoint {
  date: string;
  article_count: number;
  avg_sentiment: number | null;
  news_items: Array<{
    headline: string;
    category: 'Positive' | 'Neutral' | 'Negative' | 'Unscored' | string;
    sentiment_score: number | null;
  }>;
  positive_count: number;
  negative_count: number;
  t1_date: string | null;
  t2_date: string | null;
  return_t1_pct: number | null;
  return_t2_pct: number | null;
  volume_change_t1_pct: number | null;
  volume_change_t2_pct: number | null;
}

export interface NewsSentimentCorrelationSummary {
  observations: number;
  sentiment_return_t1: ForwardCorrelationMetric;
  sentiment_return_t2: ForwardCorrelationMetric;
  sentiment_volume_change_t1: ForwardCorrelationMetric;
  sentiment_volume_change_t2: ForwardCorrelationMetric;
}

export interface NewsSentimentForwardResponse {
  company_id: number;
  symbol: string;
  daily_data: NewsSentimentDailyPoint[];
  correlation_summary: NewsSentimentCorrelationSummary;
  disclaimer: string;
}

export interface CategorizedCompanyNews {
  id: number;
  headline: string;
  source: string;
  url: string;
  published_at: string | null;
  sentiment: number | null;
  sentiment_label: string;
  confidence: number;
  method: string;
  is_manual: boolean;
}

export interface CategorizedCompanyNewsResponse {
  company_id: number;
  symbol: string;
  count: number;
  page: number;
  page_size: number;
  next: number | null;
  previous: number | null;
  results: CategorizedCompanyNews[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Cross-Company Analysis
// Matches CrossCompanyAnalysisAPIView response
// ─────────────────────────────────────────────────────────────────────────────

export interface CompanyStat {
  id: number;
  symbol: string;
  name: string;
  logo_url: string | null;
  sector: string;
  latest_price: number;
  change_pct: number;
  volume_24h: number;
  turnover_24h: number;
  volatility: number;           // std dev of daily returns over 31d window
  vwap: number | null;          // from stored DailyAnalysis
  pressure: PressureLabel;
  pressure_score: number | null;
  pressure_method: string;
  volume_ratio: number | null;
  volume_anomaly: boolean;
  news_count: number;
}

export interface SectorStat {
  sector: string;
  companies_count: number;
  total_turnover: number;
  avg_change_pct: number;
}

export interface CrossCompanyAnalysis {
  watchlist_count: number;
  companies: CompanyStat[];
  most_volatile: CompanyStat[];        // top 5
  most_active_volume: CompanyStat[];   // top 5
  most_active_turnover: CompanyStat[]; // top 5
  most_in_news: CompanyStat[];         // top 5
  top_gainers: CompanyStat[];          // top 5
  top_losers: CompanyStat[];           // bottom 5
  sectors: SectorStat[];
  pressure_distribution: { buying: number; selling: number; neutral: number };
}

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard Summary
// Matches DashboardSummaryAPIView response (all hardcoded mock values removed)
// ─────────────────────────────────────────────────────────────────────────────

export interface DashboardSummary {
  market_turnover: number;
  market_volume: number;
  daily_change_pct: number;
  tracked_companies_count: number;
  companies_with_data: number;
  news_analyzed_count: number;
  volume_anomaly_count: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Prices / Floorsheet (kept here for convenience — also in stocks.ts)
// ─────────────────────────────────────────────────────────────────────────────

export interface PricePoint {
  id: number;
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
  turnover: string;
  company?: number;
  company_symbol?: string;
  company_name?: string;
}

export interface IntradayBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PricesResponse {
  company_id: number;
  symbol: string;
  name: string;
  range: string;
  count: number;
  prices: PricePoint[];
}

export interface VolumeAnomaly {
  date: string;
  volume: number;
  rolling_mean: number | null;
  average_volume_20d: number | null;
  rvol: number | null;
  anomaly_flag: 'Normal' | 'Anomaly' | null;
  is_anomaly: boolean | null;
  price_change_pct: number | null;
}

export interface RvolPoint {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number;
  rolling_avg: number | null;
  rolling_std: number | null;
  rvol: number | null;
  is_above_threshold: boolean;
}

export interface FloorsheetTx {
  id: number;
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

export interface FloorsheetResponse {
  company_id: number;
  symbol: string;
  date: string | null;
  count: number;
  transactions: FloorsheetTx[];
}

// ─────────────────────────────────────────────────────────────────────────────
// API functions
// ─────────────────────────────────────────────────────────────────────────────

export const analysisApi = {
  // ── Company behavior summary ─────────────────────────────────────────────
  // All three URLs are equivalent; use the shortest alias.
  getBehavior: (companyId: number) =>
    apiClient
      .get<BehaviorSummary>(`/companies/${companyId}/behavior/`)
      .then((r) => r.data),

  // ── Broker activity (detailed, with date range params) ───────────────────
  getBrokerActivity: (
    companyId: number,
    params?: { start_date?: string; end_date?: string; date?: string }
  ) =>
    apiClient
      .get<BrokerActivityResponse>(
        `/analysis/companies/${companyId}/brokers/`,
        { params }
      )
      .then((r) => r.data),

  getBrokerAnalysis: (params?: {
    start_date?: string;
    end_date?: string;
    company_id?: number;
    broker?: string;
    page?: number;
  }) => apiClient
    .get<BrokerAnalysisResponse>('/analysis/brokers/', { params })
    .then((r) => r.data),

  getBrokerDetail: (broker: string, params?: {
    start_date?: string;
    end_date?: string;
    company_id?: number;
  }) => apiClient
    .get<BrokerDetailResponse>(`/analysis/brokers/${encodeURIComponent(broker)}/`, { params })
    .then((r) => r.data),

  // ── News-price correlation (60-day rolling window) ───────────────────────
  getNewsCorrelation: (companyId: number) =>
    apiClient
      .get<NewsPriceCorrelation>(`/companies/${companyId}/news-correlation/`)
      .then((r) => r.data),

  getNewsSentimentForward: (symbol: string, params?: { start_date?: string; end_date?: string }) =>
    apiClient
      .get<NewsSentimentForwardResponse>(`/companies/${encodeURIComponent(symbol)}/news-correlation/`, { params })
      .then((r) => r.data),

  getCategorizedCompanyNews: (companyId: number, page = 1) =>
    apiClient
      .get<CategorizedCompanyNewsResponse>(`/analysis/companies/${companyId}/categorized-news/`, { params: { page } })
      .then((r) => r.data),

  // ── Historical prices ────────────────────────────────────────────────────
  // range: '7d' | '30d' | '31d' | '90d' | '180d' | '1y' | 'all'
  getPrices: (companyId: number, range = '31d', params?: { source?: 'crawled' }) =>
    apiClient
      .get<PricesResponse>(`/companies/${companyId}/prices/`, {
        params: { range, ...params },
      })
      .then((r) => r.data),

  getIntradayBars: (companyId: number, days = 1) =>
    apiClient
      .get<{ bars: IntradayBar[] }>(`/companies/${companyId}/intraday/`, { params: { days } })
      .then((r) => r.data.bars),

  getVolumeAnomalies: (symbol: string, params?: { start_date?: string; end_date?: string; lookback?: number }) =>
    apiClient
      .get<VolumeAnomaly[]>(`/companies/${encodeURIComponent(symbol)}/volume-anomalies/`, { params })
      .then((r) => r.data),

  getRvol: (symbol: string, params?: { start_date?: string; end_date?: string; ma_length?: number; ma_type?: 'SMA' | 'EMA'; threshold?: number }) =>
    apiClient
      .get<RvolPoint[]>(`/companies/${encodeURIComponent(symbol)}/rvol/`, { params })
      .then((r) => r.data),

  // ── Latest floorsheet (most recent date) ─────────────────────────────────
  getFloorsheet: (companyId: number, date?: string) =>
    apiClient
      .get<FloorsheetResponse>(`/companies/${companyId}/floorsheet/`, {
        params: date ? { date } : undefined,
      })
      .then((r) => r.data),

  // ── Daily analysis list (all stored rows, filterable by company) ─────────
  getDailyAnalysis: (companyId?: number) =>
    apiClient
      .get<{ count: number; results: DailyAnalysis[] }>('/analysis/daily/', {
        params: companyId ? { company_id: companyId } : undefined,
      })
      .then((r) => r.data),

  // ── Cross-company comparison ─────────────────────────────────────────────
  getCrossCompany: () =>
    apiClient
      .get<CrossCompanyAnalysis>('/analysis/cross-company/')
      .then((r) => r.data),

  // ── Dashboard summary (market-wide, no fake portfolio values) ───────────
  getDashboardSummary: () =>
    apiClient
      .get<DashboardSummary>('/analysis/dashboard-summary/')
      .then((r) => r.data),
};
