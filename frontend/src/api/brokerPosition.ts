/**
 * brokerPosition.ts
 *
 * One broker's running net (bought - sold) in one stock: per minute (1D) / 5 minutes (2D)
 * or per session (1W ... 1Y), with the stock's price.  Shapes mirror build_broker_position()
 * in apps/analysis/services/broker_position.py (view: BrokerPositionAPIView).
 *
 * Numbers arrive as numbers; dates as YYYY-MM-DD, intraday times as ISO datetimes.
 */

import { apiClient } from './client';

export const POSITION_RANGES = ['1D', '2D', '1W', '2W', '1M', '3M', '6M', '1Y'] as const;
export type PositionRange = (typeof POSITION_RANGES)[number];

export interface PositionPoint {
  /** Session date (daily) or bucket start (intraday). */
  time: string;
  date: string;
  /** Daily close or intraday candle close; null when not stored. */
  price: number | null;
  bought: number;
  sold: number;
  buy_value: number;
  sell_value: number;
  trades: number;
  net: number;
  /** Running net from the start of the range. */
  position: number;
}

export interface PositionTotals {
  bought: number;
  sold: number;
  net: number;
  buy_value: number;
  sell_value: number;
  avg_buy_price: number | null;
  avg_sell_price: number | null;
  last_price: number | null;
  trades: number;
  active_sessions: number;
  /** Share of all the stock's traded shares this broker was on either side of. */
  share_of_volume_pct: number | null;
  stock_volume: number;
  self_trades: number;
}

export interface PositionTopBroker {
  broker: string;
  bought: number;
  sold: number;
  net: number;
}

export interface BrokerPosition {
  symbol: string;
  /** The requested broker, or the stock's most active one when none was given. */
  broker: string;
  range: PositionRange;
  mode: 'intraday' | 'daily';
  bucket_minutes: number | null;
  exclude_self: boolean;
  sessions: number;
  start_date: string | null;
  end_date: string | null;
  points: PositionPoint[];
  totals: PositionTotals | null;
  top_brokers: PositionTopBroker[];
  warnings: string[];
  broker_metadata: Record<string, { name: string; short_name: string; logo_url: string | null }>;
}

export const brokerPositionApi = {
  get: (params: { symbol: string; broker?: string; range: PositionRange; excludeSelf: boolean }) =>
    apiClient
      .get<BrokerPosition>('/analysis/broker-position/', {
        params: {
          symbol: params.symbol,
          broker: params.broker || undefined,
          range: params.range,
          exclude_self: params.excludeSelf ? 1 : 0,
        },
      })
      .then((r) => r.data),
};

/** One stock's flows for the selected broker, one value per entry in BrokerActivity.times. */
export interface ActivitySeries {
  symbol: string;
  name: string;
  bought: number[];
  sold: number[];
  totals: {
    bought: number;
    sold: number;
    net: number;
    buy_value: number;
    sell_value: number;
    avg_buy_price: number | null;
    avg_sell_price: number | null;
    trades: number;
  };
}

/** One broker in up to MAX_ACTIVITY_STOCKS stocks on a shared time axis (BrokerActivityAPIView). */
export interface BrokerActivity {
  broker: string;
  range: PositionRange;
  mode: 'intraday' | 'daily';
  bucket_minutes: number | null;
  exclude_self: boolean;
  sessions: number;
  start_date: string | null;
  end_date: string | null;
  /** Session dates (daily) or every 1- / 5-minute bucket start of the sessions (intraday). */
  times: string[];
  series: ActivitySeries[];
  /** Most active brokers across the selected stocks, for quick picking. */
  top_brokers: PositionTopBroker[];
  warnings: string[];
  broker_metadata: BrokerPosition['broker_metadata'];
}

export const MAX_ACTIVITY_STOCKS = 8;

export const brokerActivityApi = {
  get: (params: { symbols: string[]; broker?: string; range: PositionRange; excludeSelf: boolean }) =>
    apiClient
      .get<BrokerActivity>('/analysis/broker-activity/', {
        params: {
          symbols: params.symbols.join(','),
          broker: params.broker || undefined,
          range: params.range,
          exclude_self: params.excludeSelf ? 1 : 0,
        },
      })
      .then((r) => r.data),
};
