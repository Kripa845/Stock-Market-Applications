import { apiClient } from './client';

export interface IndexRow {
  code: string; name: string; sector: string; date: string; previous_date: string | null;
  open: number | null; high: number | null; low: number | null; close: number;
  prev_close: number | null; ch: number | null; ch_pct: number | null;
  turnover: number | null; tu_ch: number | null; tu_ch_pct: number | null;
  /** Share of the NEPSE Index (whole-market) turnover on the same session. */
  turnover_share_pct: number | null;
  volume: number | null; vol_ch: number | null; vol_ch_pct: number | null;
  transactions: number | null; trans_ch: number | null; trans_ch_pct: number | null;
}
export interface SectorShare {
  sector: string;
  turnover_share_pct: number | null; volume_share_pct: number | null; transactions_share_pct: number | null;
  tu_ch_pct: number | null; vol_ch_pct: number | null; trans_ch_pct: number | null;
}
export interface MarketAnalysis {
  scope: 'whole_market' | 'tracked_companies';
  as_of: string | null; base_date: string | null; rows: SectorShare[];
}

export interface IndexTable {
  scope: 'whole_market';
  as_of: string | null;
  /** Today's session is still open: turnover / volume / transactions are not final. */
  market_open: boolean;
  rows: IndexRow[];
}

export const getIndices = (date?: string) =>
  apiClient.get<IndexTable>('/market-indices/indices/', { params: { date } }).then(r => r.data);
export const getSubIndices = (date?: string) =>
  apiClient.get<IndexTable>('/market-indices/sub-indices/', { params: { date } }).then(r => r.data);
export const getAnalysis = () => apiClient.get<MarketAnalysis>('/market-indices/analysis/').then(r => r.data);
export const getTop = (by: 'turnover' | 'volume' | 'transactions') =>
  apiClient.get('/market-indices/top/', { params: { by } }).then(r => r.data);