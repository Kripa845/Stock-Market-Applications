export interface Company {
  id: number;
  symbol: string;
  name: string;
  sector: string;

  is_active: boolean;
  is_tracked: boolean;

  latest_price: number;
  price_change: number;
  price_change_percent: number;

  volume_24h: number;
  turnover_24h: number;

  high_24h: number;
  low_24h: number;

  news_count: number;
  sentiment_score: number;

  sparkline: number[];

  last_crawl: string | null;
  last_crawl_status: string | null;
}