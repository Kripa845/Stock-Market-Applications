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

export interface MarketTile {
  id?: number;
  symbol?: string;
  name?: string;
  sector: string;
  close?: number | string;
  change_pct: number | string | null;
  turnover: number | string;
  company_count?: number;
  excluded_count?: number;
  possible_corporate_action?: boolean;
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

export const marketIntelligenceApi = {
  async getBreadth() {
    const { data } = await apiClient.get<MarketBreadth>('/market-intelligence/breadth/');
    return data;
  },
  async getHeatmap(group: 'sector' | 'company' = 'sector') {
    const { data } = await apiClient.get<{
      date: string | null; group: string; size_metric: string; color_metric: string;
      tiles: MarketTile[]; universe_label: string; computed_at: string | null;
    }>('/market-intelligence/heatmap/', { params: { group } });
    return data;
  },
  async getRankings(metric: RankingMetric) {
    const { data } = await apiClient.get<{
      date: string | null; metric: RankingMetric; results: RankedStock[];
      universe_label: string; computed_at: string | null;
    }>('/market-intelligence/rankings/', { params: { metric, limit: 20 } });
    return data;
  },
};
