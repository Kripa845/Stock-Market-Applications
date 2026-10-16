import { apiClient } from './client';
import type { SupportResistance } from './marketIntelligence';

export interface IndexRow {
  code: string; name: string; sector: string; date: string; previous_date: string | null;
  open: number | null; high: number | null; low: number | null; close: number;
  prev_close: number | null; ch: number | null; ch_pct: number | null;
  turnover: number | null; tu_ch: number | null; tu_ch_pct: number | null;
  /** Share of the NEPSE Index (whole-market) turnover on the same session. */
  turnover_share_pct: number | null;
  volume: number | null; vol_ch: number | null; vol_ch_pct: number | null;
  transactions: number | null; trans_ch: number | null; trans_ch_pct: number | null;
  /** Stored closes for the last 30 sessions, oldest first. */
  sparkline?: (number | string)[];
  /** "crawled" = NEPSE's own feed; "sharesansar" = the fallback used when NEPSE failed. */
  source?: string;
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

/** One stored NEPSE session; same row shape as the company price endpoint. Decimals arrive as strings. */
export interface IndexPricePoint {
  id: number; date: string;
  open: string | null; high: string | null; low: string | null; close: string;
  volume: number | null; turnover: string | null;
}
export interface IndexHistory {
  index_id: number; symbol: string; name: string; kind: 'main' | 'sub';
  range: string; count: number;
  prices: IndexPricePoint[];
  /** max(high) / min(low) over the 365 days up to the latest session (backend-computed). */
  fifty_two_week: {
    from: string; to: string;
    high: string | null; high_date: string | null; low: string | null; low_date: string | null;
  } | null;
  /** change_pct is NEPSE's own value; change = close minus the previous stored close. */
  latest: {
    date: string; close: string; previous_date: string | null; previous_close: string | null;
    change: string | null; change_pct: string | null;
  } | null;
}

export const getIndexHistory = (
  code = 'NEPSE',
  params: { range?: string; start_date?: string; end_date?: string } = {},
) => apiClient.get<IndexHistory>('/market-indices/history/', { params: { code, ...params } }).then(r => r.data);

export const getIndices = (date?: string) =>
  apiClient.get<IndexTable>('/market-indices/indices/', { params: { date } }).then(r => r.data);
export const getSubIndices = (date?: string) =>
  apiClient.get<IndexTable>('/market-indices/sub-indices/', { params: { date } }).then(r => r.data);
export const getAnalysis = () => apiClient.get<MarketAnalysis>('/market-indices/analysis/').then(r => r.data);
export const getTop = (by: 'turnover' | 'volume' | 'transactions') =>
  apiClient.get('/market-indices/top/', { params: { by } }).then(r => r.data);
/** Stored value vs NEPSE's feed for one index (GET /market-indices/verify/). */
export type IndexDataStatus = 'scraped' | 'missing' | 'mismatch';
export interface IndexFieldMismatch { field: string; stored: number | string; source: number | string }
export interface IndexVerificationRow {
  code: string; name: string; kind: 'main' | 'sub';
  status: IndexDataStatus;
  /** False when NEPSE's feed could not be checked: presence only. */
  verified: boolean;
  note: string | null;
  /** Empty fields; "previous_session" = no earlier session stored, so change columns are blank. */
  missing: string[];
  mismatches: IndexFieldMismatch[];
}
export interface IndexVerification {
  session: string | null;
  feed_ok: boolean;
  feed_error: string | null;
  source?: string;
  checked_at?: string;
  /** When the session's index rows were last written by the scraper. */
  last_updated: string | null;
  rows: IndexVerificationRow[];
  summary: Partial<Record<IndexDataStatus | 'total', number>>;
  sync?: {
    saved: number;
    /** NEPSE sync: count; ShareSansar fallback: the session dates. */
    sessions: number | string[];
    latest?: string | null;
    unmatched?: string[];
    /** Set when NEPSE failed and missing sessions were filled from ShareSansar. */
    fallback?: 'sharesansar';
    nepse_error?: string;
  };
}

export const verifyIndices = (date?: string) =>
  apiClient.get<IndexVerification>('/market-indices/verify/', { params: { date } }).then(r => r.data);
/** Re-scrape the session from NEPSE (needs run_crawler), then verify again. */
export const resyncIndices = (date?: string) =>
  apiClient.post<IndexVerification>('/market-indices/verify/', null, { params: { date } }).then(r => r.data);

/** Recorded 5-minute index values as one-point bars (only indices NEPSE's live feed covers). */
export const getIndexIntraday = (code: string, days: number) =>
  apiClient
    .get<{ code: string; bars: { time: string; open: number; high: number; low: number; close: number; volume: number }[] }>(
      '/market-indices/intraday/', { params: { code, days } },
    )
    .then(r => r.data.bars);
/** Support / resistance from stored daily index values (same algorithm and shape as for companies). */
export const getIndexSupportResistance = (code: string) =>
  apiClient
    .get<Omit<SupportResistance, 'company_id'> & { index_code: string }>('/market-indices/support-resistance/', { params: { code } })
    .then(r => r.data);
