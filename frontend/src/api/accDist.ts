/**
 * accDist.ts
 *
 * Market-wide accumulation / distribution: (stock, broker) pairs with the largest net buying
 * and net selling over a period.  Shapes mirror AccDistRowSerializer and AccDistAPIView in
 * apps/analysis/api/ (service: apps/analysis/services/acc_dist.py).
 *
 * Signed numbers: distribution rows carry negative net_qty / net_amount.  Money, prices and
 * percentages arrive as numbers; dates as YYYY-MM-DD.
 */

import { apiClient } from './client';

export const ACC_DIST_PERIODS = ['1D', '2D', '1W', '2W', '1M', '3M', '6M', '1Y', '2Y', '3Y'] as const;
export type AccDistPeriod = (typeof ACC_DIST_PERIODS)[number];
export type AccDistSide = 'accumulation' | 'distribution';

export interface AccDistRow {
  symbol: string;
  sector: string;
  /** Broker number: the net buyer on the accumulation side, net seller on distribution. */
  broker: string;
  net_qty: number;
  net_amount: number;
  /** Average buy price (accumulation) or sell price (distribution). */
  avg_rate: number | null;
  float_qty_pct: number | null;
  /** "public" = % of non-promoter shares; "listed" = % of all listed shares (public count unknown). */
  float_basis: 'public' | 'listed' | null;
  /** 1 = largest |net_amount| for the period. */
  rank: number;
}

export interface AccDistSnapshot {
  period: AccDistPeriod;
  /** Floorsheet sessions the period covered; fewer than asked when history is shorter. */
  sessions: number;
  start_date: string | null;
  end_date: string | null;
  accumulation: AccDistRow[];
  distribution: AccDistRow[];
}

export const accDistApi = {
  snapshot: (period: AccDistPeriod) =>
    apiClient.get<AccDistSnapshot>('/analysis/acc-dist/', { params: { period } }).then((r) => r.data),
};
