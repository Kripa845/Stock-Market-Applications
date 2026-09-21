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
  volume_ratio: string | null;      // today / 20-session avg; anomaly ≥ 1.5
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
}

// ─────────────────────────────────────────────────────────────────────────────
// Cross-Company Analysis
// Matches CrossCompanyAnalysisAPIView response
// ─────────────────────────────────────────────────────────────────────────────

export interface CompanyStat {
  id: number;
  symbol: string;
  name: string;
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

export interface PricesResponse {
  company_id: number;
  symbol: string;
  name: string;
  range: string;
  count: number;
  prices: PricePoint[];
}

export interface FloorsheetTx {
  id: number;
  date: string;
  transaction_id: string;
  buyer_broker: string;
  seller_broker: string;
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

  // ── News-price correlation (60-day rolling window) ───────────────────────
  getNewsCorrelation: (companyId: number) =>
    apiClient
      .get<NewsPriceCorrelation>(`/companies/${companyId}/news-correlation/`)
      .then((r) => r.data),

  // ── Historical prices ────────────────────────────────────────────────────
  // range: '7d' | '30d' | '31d' | '90d' | '180d' | '1y' | 'all'
  getPrices: (companyId: number, range = '31d') =>
    apiClient
      .get<PricesResponse>(`/companies/${companyId}/prices/`, {
        params: { range },
      })
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
