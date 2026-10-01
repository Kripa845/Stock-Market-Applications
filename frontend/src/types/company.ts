/**
 * Single canonical Company type — re-exported from types/index.ts
 * for backwards compatibility.
 *
 * All fields mirror the CompanySerializer response from the Django backend.
 */
export interface Company {
  id: number;
  symbol: string;
  name: string;
  logo_url: string | null;
  sector: string;
  aliases: string[];

  is_active: boolean;
  /** Always present in API responses from CompanySerializer */
  is_tracked: boolean;

  // ── Latest daily price (SerializerMethodField) ──────────────────────
  latest_price: number;
  price_change: number;
  price_change_percent: number;

  volume_24h: number;
  turnover_24h: number;
  high_24h: number;
  low_24h: number;

  // ── News & sentiment ─────────────────────────────────────────────────
  news_count: number;
  sentiment_score: number;

  // ── Sparkline (last 10 close prices) ─────────────────────────────────
  sparkline: number[];

  // ── Crawl status (optional — not always returned) ────────────────────
  last_crawl?: string | null;
  last_crawl_status?: string | null;
}
