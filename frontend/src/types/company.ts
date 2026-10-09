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
  /** null when the company has no crawled price -- never 0. */
  latest_price: number | null;
  latest_price_date: string | null;
  price_change: number | null;
  /** Latest-session change % (same definition as /api/market/movers/); null when not ranked. */
  price_change_percent: number | null;

  volume_24h: number | null;
  turnover_24h: number | null;
  high_24h: number | null;
  low_24h: number | null;

  // ── News & sentiment ─────────────────────────────────────────────────
  news_count: number;
  sentiment_score: number | null;

  // ── Sparkline (last 10 close prices) ─────────────────────────────────
  sparkline: number[];

  // ── Crawl status (optional — not always returned) ────────────────────
  last_crawl?: string | null;
  last_crawl_status?: string | null;
}
