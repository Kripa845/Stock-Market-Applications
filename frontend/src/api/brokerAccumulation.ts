/**
 * brokerAccumulation.ts
 *
 * Broker accumulation / distribution for one stock.  Shapes mirror
 * apps/analysis/serializers.py (Accumulation*Serializer, BrokerFlowPointSerializer)
 * and the payloads built in apps/analysis/views.py:
 *
 *   BrokerSummaryAPIView → /api/analysis/broker-summary/
 *   BrokerSignalAPIView  → /api/analysis/broker-signal/
 *   BrokerFlowAPIView    → /api/analysis/broker-flow/
 *
 * Money, prices, ratios and percentages arrive as numbers; dates as YYYY-MM-DD.
 */

import { apiClient } from './client';

export type AccumulationWindow = '1d' | '1w' | '1m' | '3m';
export type AccumulationSignal = 'accumulation' | 'distribution' | 'neutral' | 'no_data';

/** A preset window, or a custom range (end defaults to the latest session). */
export type AccumulationRange =
  | { window: AccumulationWindow }
  | { start_date: string; end_date?: string };

export interface AccumulationQuery {
  symbol: string;
  range: AccumulationRange;
  excludeSelfTrades?: boolean;
}

export interface ResolvedWindow {
  key: AccumulationWindow | 'custom';
  start_date: string | null;
  end_date: string | null;
  /** Floorsheet sessions inside the window. */
  sessions: number;
}

interface AccumulationEnvelope {
  company_id: number;
  symbol: string;
  window: ResolvedWindow;
}

interface WindowTotals {
  total_qty: number;
  total_amount: number;
  trade_count: number;
  /** Quantity traded where buyer broker == seller broker (0 when excluded). */
  self_trade_qty: number;
  exclude_self_trades: boolean;
}

export interface BrokerRow {
  broker: string;
  name: string;
  short_name: string;
  logo_url: string | null;
  buy_qty: number;
  sell_qty: number;
  net_qty: number;
  buy_amount: number;
  sell_amount: number;
  net_amount: number;
  avg_buy: number | null;
  avg_sell: number | null;
  net_pct_of_volume: number | null;
  buy_trades: number;
  sell_trades: number;
}

export interface BrokerStreak {
  direction: 'buying' | 'selling' | null;
  days: number;
}

export interface TopBroker extends BrokerRow {
  /** (latest close - avg buy) / avg buy, in %. */
  close_vs_avg_buy_pct: number | null;
  close_vs_avg_sell_pct: number | null;
  streak: BrokerStreak;
}

export interface BrokerSummary extends AccumulationEnvelope, WindowTotals {
  broker_count: number;
  results: BrokerRow[];
}

export interface BrokerSignal extends AccumulationEnvelope, WindowTotals {
  signal: AccumulationSignal;
  /** top5_buy_net / |top5_sell_net|; null when nobody net sold. */
  ratio: number | null;
  thresholds: { accumulation: number; distribution: number };
  top5_buy_net: number;
  top5_sell_net: number;
  accumulators: TopBroker[];
  distributors: TopBroker[];
  latest_close: number | null;
  latest_close_date: string | null;
  broker_count: number;
}

export interface FlowPoint {
  date: string;
  close: number | null;
  top5_buy_net: number;
  top5_sell_net: number;
  net_flow: number;
  ratio: number | null;
  signal: Exclude<AccumulationSignal, 'no_data'>;
  volume: number;
}

export interface BrokerFlow extends AccumulationEnvelope {
  points: FlowPoint[];
  /** Days whose bought quantity did not equal the sold quantity. */
  warnings: string[];
}

function params({ symbol, range, excludeSelfTrades }: AccumulationQuery) {
  return {
    symbol,
    ...range,
    ...(excludeSelfTrades === undefined ? {} : { exclude_self: excludeSelfTrades ? '1' : '0' }),
  };
}

export const brokerAccumulationApi = {
  summary: (query: AccumulationQuery) =>
    apiClient.get<BrokerSummary>('/analysis/broker-summary/', { params: params(query) }).then((r) => r.data),
  signal: (query: AccumulationQuery) =>
    apiClient.get<BrokerSignal>('/analysis/broker-signal/', { params: params(query) }).then((r) => r.data),
  flow: (query: AccumulationQuery) =>
    apiClient.get<BrokerFlow>('/analysis/broker-flow/', { params: params(query) }).then((r) => r.data),
};
