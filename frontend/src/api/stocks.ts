
import { apiClient } from './client';
import type {
  Company,
  DailyPrice,
  FloorsheetTransaction,
} from '../types';

export const stocksApi = {
  getCompanies: (params?: {
    tracked_only?: boolean;
    sector?: string;
    search?: string;
  }) =>
    apiClient
      .get<Company[] | { results: Company[] }>('/companies/', {
        params,
      })
      .then((response) => Array.isArray(response.data) ? response.data : response.data.results),

  getCompany: (id: number) =>
    apiClient
      .get<Company>(`/companies/${id}/`)
      .then((response) => response.data),

  toggleTrack: (
    id: number,
    is_tracked?: boolean
  ) =>
    apiClient
      .post(`/companies/${id}/toggle-track/`, {
        is_tracked,
      })
      .then((response) => response.data),

  getPrices: (
    id: number,
    range = '30d'
  ) =>
    apiClient
      .get<{
        company_id: number;
        symbol: string;
        name: string;
        range: string;
        count: number;
        prices: DailyPrice[];
      }>(
        `/companies/${id}/prices/`,
        {
          params: {
            range,
          },
        }
      )
      .then((response) => response.data),

  getIntradayBars: (id: number, days = 5) =>
    apiClient
      .get<{
        bars: Array<{
          time: string;
          open: number;
          high: number;
          low: number;
          close: number;
          volume: number;
        }>;
      }>(`/companies/${id}/intraday/`, { params: { days } })
      .then((response) => response.data.bars),

  // Stored candles for one trading day (default: latest), oldest first.
  getIntradayCandles: (
    symbol: string,
    interval: '1m' | '5m' | '15m' | '30m' | '1h' = '5m',
    date?: string
  ) =>
    apiClient
      .get<{
        company_id: number;
        symbol: string;
        name: string;
        interval: string;
        date: string | null;
        count: number;
        candles: Array<{
          time: string;
          open: string;
          high: string;
          low: string;
          close: string;
          volume: number;
          turnover: string;
          trade_count: number;
        }>;
      }>(`/stocks/${encodeURIComponent(symbol)}/intraday/`, {
        params: date ? { interval, date } : { interval },
      })
      .then((response) => response.data),

  getFloorsheet: (
    id: number,
    date?: string
  ) =>
    apiClient
      .get<{
        company_id: number;
        symbol: string;
        date: string | null;
        count: number;
        transactions: FloorsheetTransaction[];
      }>(
        `/companies/${id}/floorsheet/`,
        {
          params: date
            ? { date }
            : undefined,
        }
      )
      .then((response) => response.data),

  searchFloorsheet: (params?: {
    company?: number;
    date?: string;
    buyer_broker?: string;
    seller_broker?: string;
    page?: number;
  }) =>
    apiClient
      .get<{
        count: number;
        next: string | null;
        previous: string | null;
        results: FloorsheetTransaction[];
      }>('/market-data/floorsheet/', { params })
      .then((response) => response.data),
};

