import { apiClient } from './client';

export interface MarketBreadth {
  date: string;
  market_session_count: number;
  universe_label: string;
  advances: number;
  declines: number;
  unchanged: number;
  return_eligible_count: number;
  above_50_dma_count: number;
  valid_50_dma_count: number;
  above_50_dma_pct: number | string | null;
  above_200_dma_count: number;
  valid_200_dma_count: number;
  above_200_dma_pct: number | string | null;
  corporate_action_excluded_count: number;
  proxy_index: { level: number | string | null; methodology_version: string; computed_at: string | null };
  computed_at: string;
}

export type RankingMetric = 'gainers' | 'losers' | 'volume' | 'turnover';

export interface RankedStock {
  company_id: number;
  symbol: string;
  name: string;
  sector: string;
  close: number | string;
  change_pct: number | string | null;
  volume: number;
  turnover: number | string;
  volume_ratio: number | string | null;
  possible_corporate_action: boolean;
}

/** One clustered swing level (GET /market-intelligence/companies/:id/support-resistance/). Decimals arrive as strings. */
export interface SupportResistanceLevel {
  price: string;
  kind: 'support' | 'resistance';
  touches: number;
  strength: string;
  at_price: boolean;
  distance_pct: string | null;
  first_touch: string;
  last_touch: string;
}

export interface SupportResistance {
  company_id?: number;
  symbol: string;
  as_of: string;
  status: 'ok' | 'insufficient_history' | 'no_levels';
  latest_close: string | null;
  sessions_used: number;
  window_start: string | null;
  adjustment_cut: string | null;
  adjustments: { date: string; factor: number }[];
  params: Record<string, number>;
  levels: SupportResistanceLevel[];
  disclaimer: string;
  computed_at: string;
}

export const marketIntelligenceApi = {
  async getSupportResistance(companyId: number) {
    const { data } = await apiClient.get<SupportResistance>(
      `/market-intelligence/companies/${companyId}/support-resistance/`,
    );
    return data;
  },
  async getBreadth() {
    const { data } = await apiClient.get<MarketBreadth>('/market-intelligence/breadth/');
    return data;
  },
  async getRankings(metric: RankingMetric) {
    const { data } = await apiClient.get<{
      date: string | null; metric: RankingMetric; results: RankedStock[];
      universe_label: string; computed_at: string | null;
    }>('/market-intelligence/rankings/', { params: { metric, limit: 20 } });
    return data;
  },
  async getIndicatorRegistry() {
    const { data } = await apiClient.get<IndicatorRegistry>('/market-intelligence/indicators/registry/');
    return data;
  },
  async getIndicatorSeries(
    companyId: number,
    specs: { id: string; params: IndicatorParams }[],
    options: { start_date?: string; benchmark?: string } = {},
  ) {
    const { data } = await apiClient.get<IndicatorSeriesResponse>(
      `/market-intelligence/companies/${companyId}/indicators/`,
      { params: { specs: JSON.stringify(specs), ...options } },
    );
    return data;
  },
};

// ─── Indicator library (Backend/apps/market_intelligence/indicators) ─────────────
export type IndicatorParams = Record<string, number | string>;

export interface IndicatorParamDef {
  name: string;
  label: string;
  default: number | string;
  min: number;
  max: number;
  kind: 'int' | 'float' | 'choice';
  choices: string[];
}

export interface IndicatorDef {
  id: string;
  name: string;
  category: string;
  inputs: string[];
  params: IndicatorParamDef[];
  outputs: { key: string; label: string; kind: 'line' | 'bar' | 'dot' }[];
  display: 'overlay' | 'panel';
  ref_lines: number[];
  value_range: number[];
  fill: string[];
  color_by: string;
  scope: 'stock' | 'range' | 'market' | 'benchmark' | 'floorsheet';
  notes: string;
}

export interface IndicatorRegistry {
  indicators: IndicatorDef[];
  not_implemented: { name: string; reason: string }[];
}

export interface IndicatorResult {
  id: string;
  params?: IndicatorParams;
  // One value per date in IndicatorSeriesResponse.dates; null during warm-up.
  outputs?: Record<string, (number | null)[]>;
  extra?: { rows?: { low: number; high: number; volume: number }[] };
  error?: string;
}

export interface IndicatorSeriesResponse {
  company_id: number;
  symbol: string;
  benchmark: string | null;
  dates: string[];
  results: IndicatorResult[];
  disclaimer: string;
}
