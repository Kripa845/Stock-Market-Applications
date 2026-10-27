/**
 * accDist.ts
 *
 * Stocks being accumulated / distributed, as (stock, broker) pairs ranked by
 * absolute net amount over a period.  Signed numbers: distribution rows carry negative
 * netQty / netAmount.
 *
 * Every call is served from data/accDistMock.ts for now.  To switch to the backend, replace
 * each body with an apiClient call that returns the same shape, e.g.
 *
 *   snapshot: (period) => apiClient.get<AccDistSnapshot>('/analysis/acc-dist/', { params: { period } }).then((r) => r.data)
 */

import { MOCK_WATCHLIST, mockAccDist } from '../data/accDistMock';

export const ACC_DIST_PERIODS = ['1D', '2D', '1W', '2W', '1M', '3M', '6M', '1Y', '2Y', '3Y'] as const;
export type AccDistPeriod = (typeof ACC_DIST_PERIODS)[number];
export type AccDistSide = 'accumulation' | 'distribution';

export interface AccDistRow {
  symbol: string;
  sector: string;
  /** Broker number: the net buyer on the accumulation side, net seller on distribution. */
  broker: number;
  netQty: number;
  netAmount: number;
  avgRate: number;
  /** Net quantity as % of the stock's free-float shares. */
  floatQtyPct: number;
  /** 1 = largest |netAmount| for the period. */
  rank: number;
}

export interface AccDistSnapshot {
  period: AccDistPeriod;
  accumulation: AccDistRow[];
  distribution: AccDistRow[];
}

const mockLatency = <T,>(value: T, ms = 350 + Math.random() * 250) =>
  new Promise<T>((resolve) => { setTimeout(() => resolve(value), ms); });

export const accDistApi = {
  snapshot: (period: AccDistPeriod): Promise<AccDistSnapshot> => mockLatency(mockAccDist(period)),
  watchlistSymbols: (): Promise<string[]> => mockLatency(MOCK_WATCHLIST, 150),
};
