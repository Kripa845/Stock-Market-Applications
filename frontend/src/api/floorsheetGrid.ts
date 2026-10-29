/**
 * floorsheetGrid.ts
 *
 * Floor Sheet Summary: one session's trades for the tracked companies in N-minute buckets,
 * plus the server's validation checks.  Shapes mirror serialize_grid() in
 * apps/analysis/services/floorsheet_grid.py (view: FloorsheetGridAPIView).
 *
 * Numbers arrive as numbers; a missing figure is null, never 0.
 */

import { apiClient } from './client';

export const BUCKET_MINUTES = [1, 5, 10, 15, 30, 45] as const;
export type BucketMinutes = (typeof BUCKET_MINUTES)[number];

export interface GridCell {
  /** Bucket index: 0 starts at the 11:00 open (pre-open fills are counted in it). */
  i: number;
  open: number;
  high: number;
  low: number;
  /** Rate of the bucket's last trade. */
  close: number;
  vwap: number | null;
  /** vs the previous bucket that traded; the first vs the previous session's close. */
  change_pct: number | null;
  quantity: number;
  trades: number;
  turnover: number;
}

export interface GridCompany {
  company_id: number;
  symbol: string;
  name: string;
  sector: string;
  quantity: number;
  trades: number;
  turnover: number;
  prev_close: number | null;
  /** Crawled daily close; null until the day's prices are crawled. */
  official_close: number | null;
  published_change_pct: number | null;
  /** Close by the exchange's rule (round lots only), from the trades. */
  session_close: number | null;
  last_trade_close: number | null;
  day_change_pct: number | null;
  cells: GridCell[];
}

export interface GridMismatch {
  symbol: string;
  bucket: string | null;
  field: string;
  expected: string | null;
  actual: string | null;
  source: string;
}

export interface GridCheck {
  key: string;
  label: string;
  status: 'pass' | 'fail' | 'n/a';
  compared: number;
  mismatch_count: number;
  mismatches: GridMismatch[];
  note: string;
}

export interface FloorsheetGrid {
  date: string | null;
  minutes: BucketMinutes;
  status: 'live' | 'stored';
  /** Bucket start times, HH:MM Nepal time. */
  buckets: string[];
  pre_open_trades: number;
  companies: GridCompany[];
  checks: GridCheck[];
  /** Sessions with trade times, newest first. */
  dates: string[];
}

export const floorsheetGridApi = {
  get: (params: { date?: string; minutes: BucketMinutes }) =>
    apiClient
      .get<FloorsheetGrid>('/analysis/floorsheet-grid/', { params: { minutes: params.minutes, date: params.date || undefined } })
      .then((res) => res.data),
};
