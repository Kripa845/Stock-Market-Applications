/**
 * exports.ts
 *
 * API client for the Export Data / Reports feature.
 *
 * All requests are made through the shared apiClient instance, which
 * automatically attaches the JWT Bearer token and handles 401/403 responses.
 *
 * Permission enforced by backend: export_reports
 */

import { apiClient } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ExportCompany {
  id: number;
  symbol: string;
  name: string;
  sector: string;
}

export type ExportDataType = 'news' | 'trading' | 'floorsheet' | 'broker_analysis' | 'report';
export type ExportFormat = 'csv' | 'xlsx' | 'pdf';
export type SentimentFilter = '' | 'positive' | 'neutral' | 'negative';

export interface ExportParams {
  company_ids?: number[];
  date_from?: string;
  date_to?: string;
  sentiment?: SentimentFilter;
  format: ExportFormat;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Trigger a file download from a Blob.
 * Creates a temporary anchor tag, clicks it, then cleans up.
 */
function _downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Build a safe download filename.
 * e.g. news_export_NABIL_2026-09-01_to_2026-09-21.csv
 */
function _buildFilename(
  prefix: string,
  params: ExportParams,
  companies: ExportCompany[],
): string {
  const parts = [prefix];
  if (params.company_ids?.length) {
    const symbols = params.company_ids
      .map((cid) => companies.find((c) => c.id === cid)?.symbol)
      .filter(Boolean) as string[];
    if (symbols.length) parts.push(...symbols);
  }
  if (params.date_from) parts.push(params.date_from);
  if (params.date_to) parts.push(`to_${params.date_to}`);
  return parts.join('_') + '.' + params.format;
}

const MIME: Record<ExportFormat, string> = {
  csv: 'text/csv',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  pdf: 'application/pdf',
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const exportsApi = {
  /**
   * Fetch the list of active companies for the company selector dropdown.
   * Requires: export_reports permission.
   */
  getCompanies(): Promise<ExportCompany[]> {
    return apiClient
      .get<ExportCompany[]>('/reports/export/companies/')
      .then((r) => r.data);
  },

  /**
   * Export news data and trigger a browser file download.
   * Returns true on success, throws on error.
   */
  async exportNews(params: ExportParams, companies: ExportCompany[]): Promise<void> {
    const response = await apiClient.get('/reports/export/news/', {
      params: _cleanParams(params),
      responseType: 'blob',
    });
    _downloadBlob(
      new Blob([response.data], { type: MIME[params.format] }),
      _buildFilename('news_export', params, companies),
    );
  },

  /**
   * Export trading (daily price) data and trigger a browser file download.
   */
  async exportTrading(params: ExportParams, companies: ExportCompany[]): Promise<void> {
    const response = await apiClient.get('/reports/export/trading/', {
      params: _cleanParams(params),
      responseType: 'blob',
    });
    _downloadBlob(
      new Blob([response.data], { type: MIME[params.format] }),
      _buildFilename('trading_export', params, companies),
    );
  },

  /**
   * Export floorsheet transaction data and trigger a browser file download.
   * Note: floorsheet only supports csv and xlsx.
   */
  async exportFloorsheet(params: ExportParams, companies: ExportCompany[]): Promise<void> {
    const response = await apiClient.get('/reports/export/floorsheet/', {
      params: _cleanParams(params),
      responseType: 'blob',
    });
    _downloadBlob(
      new Blob([response.data], { type: MIME[params.format] }),
      _buildFilename('floorsheet_export', params, companies),
    );
  },

  async exportBrokerAnalysis(params: ExportParams, companies: ExportCompany[]): Promise<void> {
    const response = await apiClient.get('/reports/export/brokers/', {
      params: _cleanParams(params),
      responseType: 'blob',
    });
    _downloadBlob(
      new Blob([response.data], { type: MIME[params.format] }),
      _buildFilename('broker_activity_export', params, companies),
    );
  },

  /**
   * Generate a combined analysis report (PDF or XLSX) and trigger download.
   * Note: report only supports pdf and xlsx.
   */
  async exportReport(params: ExportParams, companies: ExportCompany[]): Promise<void> {
    const response = await apiClient.get('/reports/export/report/', {
      params: _cleanParams(params),
      responseType: 'blob',
    });
    _downloadBlob(
      new Blob([response.data], { type: MIME[params.format] }),
      _buildFilename('analysis_report', params, companies),
    );
  },
};

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Strip empty/undefined values so they don't appear as blank query params. */
export function _cleanParams(params: ExportParams): URLSearchParams {
  const usp = new URLSearchParams();
  usp.set("format", params.format);
  if (params.company_ids?.length) {
    for (const cid of params.company_ids) {
      usp.append("company_id", String(cid));
    }
  }
  if (params.date_from) usp.set("date_from", params.date_from);
  if (params.date_to) usp.set("date_to", params.date_to);
  if (params.sentiment) usp.set("sentiment", params.sentiment);
  return usp;
}
