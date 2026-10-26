import { apiClient } from './client';

// Market -> Quarterly Report (/api/market/quarterly-report/).  Every ratio is calculated by the
// backend (services/quarterly_metrics.py); null means "not meaningful" and is shown as n/m.

export const SECTOR_CODES = [
  'BANKING', 'DEVBANK', 'FINANCE', 'HOTELS', 'HYDROPOWER', 'INVESTMENT', 'LIFEINSU',
  'MANUFACTURE', 'MICROFINANCE', 'NONLIFEINSU', 'OTHERS', 'TRADING',
] as const;
export type SectorCode = (typeof SECTOR_CODES)[number];

export type Quarter = 1 | 2 | 3 | 4;

export interface QuarterlyReportMeta {
  sector: SectorCode;
  sector_name: string;
  /** "2082/2083"; null when the sector has no filings yet. */
  fiscal_year: string | null;
  quarter: Quarter | null;
  reported_count: number;
  total_companies: number;
  /** Years in the DPPS average window; the column labels follow it. */
  avg_window: number;
  avg_min_years: number;
}

export interface QuarterlyReportRow {
  symbol: string;
  name: string;
  logo_url: string | null;
  reported_on: string | null;
  /** Latest crawled close and its date. */
  ltp: number | null;
  price_date: string | null;
  eps: number | null;
  bv: number | null;
  pe: number | null;
  pb: number | null;
  dpps: number | null;
  dpps_yield: number | null;
  avg_dpps: number | null;
  avg_years_used: number;
  avg_yield: number | null;
  previous_eps: number | null;
  yoy: number | null;
}

export interface QuarterlyReportResponse {
  meta: QuarterlyReportMeta;
  results: QuarterlyReportRow[];
}

export interface QuarterlyReportPeriod {
  fiscal_year: string;
  quarters: Quarter[];
}

export interface QuarterlyReportPeriodsResponse {
  sector: SectorCode;
  periods: QuarterlyReportPeriod[];
}

export interface QuarterlyReportQuery {
  sector: SectorCode;
  fiscal_year?: string;
  quarter?: Quarter;
}

export const quarterlyReportApi = {
  report: ({ sector, fiscal_year, quarter }: QuarterlyReportQuery) =>
    apiClient
      .get<QuarterlyReportResponse>('/market/quarterly-report/', { params: { sector, fiscal_year, quarter } })
      .then((response) => response.data),
  periods: (sector: SectorCode) =>
    apiClient
      .get<QuarterlyReportPeriodsResponse>('/market/quarterly-report/periods/', { params: { sector } })
      .then((response) => response.data),
};

/** "2082/2083" -> "2082/83". */
export const shortFiscalYear = (fiscalYear: string) => fiscalYear.replace(/^(\d{4})\/\d{2}(\d{2})$/, '$1/$2');
