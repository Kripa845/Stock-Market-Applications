import { apiClient } from './client';

// ─── Behavior Summary ────────────────────────────────────────────────────────

export interface BrokerConcentration {
  buyer_broker?: string;
  seller_broker?: string;
  total_qty: number;
  total_amt: number;
}

export interface BehaviorSummary {
  company_id: number;
  symbol: string;
  name: string;
  sector: string;
  latest_price: number;
  vwap: number;
  price_to_vwap_spread_pct: number;
  pressure: 'buying' | 'selling' | 'neutral';
  pressure_score: number;
  volume_anomaly: boolean;
  current_volume: number;
  volume_30d_avg: number;
  volume_ratio: number;
  buyer_broker_concentration: BrokerConcentration[];
  seller_broker_concentration: BrokerConcentration[];
  news_sentiment_score: number;
  news_count_30d: number;
  summary_text: string;
}

// ─── News-Price Correlation ───────────────────────────────────────────────────

export interface CorrelationDataPoint {
  date: string;
  close: number;
  price_change_pct: number;
  volume: number;
  news_count: number;
  sentiment_score: number;
}

export interface NewsPriceCorrelation {
  company_id: number;
  symbol: string;
  correlation_coefficient: number | null;
  correlation_label: string;
  lead_lag_days: number;
  analysis_note: string;
  data_points: CorrelationDataPoint[];
}

// ─── Prices (re-export shape for use here) ───────────────────────────────────

export interface PricePoint {
  id: number;
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
  turnover: string;
}

export interface PricesResponse {
  company_id: number;
  symbol: string;
  name: string;
  range: string;
  count: number;
  prices: PricePoint[];
}

// ─── Floorsheet broker aggregate (for net buy/sell table) ────────────────────

export interface FloorsheetTx {
  id: number;
  date: string;
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

// ─── API calls ───────────────────────────────────────────────────────────────

export const analysisApi = {
  /** Behavior summary: VWAP, pressure, anomaly, broker concentration, sentiment */
  getBehavior: (companyId: number): Promise<BehaviorSummary> =>
    apiClient
      .get<BehaviorSummary>(`/companies/${companyId}/behavior/`)
      .then((r) => r.data),

  /** News-price correlation data points */
  getNewsCorrelation: (companyId: number): Promise<NewsPriceCorrelation> =>
    apiClient
      .get<NewsPriceCorrelation>(`/companies/${companyId}/news-correlation/`)
      .then((r) => r.data),

  /** Historical prices — default 30d */
  getPrices: (companyId: number, range = '30d'): Promise<PricesResponse> =>
    apiClient
      .get<PricesResponse>(`/companies/${companyId}/prices/`, {
        params: { range },
      })
      .then((r) => r.data),

  /** Latest floorsheet (most recent available date) */
  getFloorsheet: (companyId: number): Promise<FloorsheetResponse> =>
    apiClient
      .get<FloorsheetResponse>(`/companies/${companyId}/floorsheet/`)
      .then((r) => r.data),
};
