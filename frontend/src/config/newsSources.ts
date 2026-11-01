export interface NewsSource {
  id: string;
  /** Also the value sent as `?source=` to /api/news/ (matched case-insensitively). */
  name: string;
  logoUrl: string;
  brandColor: string;
}

export const ALL_NEWS_ID = 'all';

// Portals with crawled articles in NewsArticle.source. The spiders live in
// Backend/crawlers/crawlers/spiders/ (MeroLagani news came from an older crawler).
// Brand colours are approximations of each site's logo.
export const NEWS_SOURCES: NewsSource[] = [
  { id: ALL_NEWS_ID, name: 'All News', logoUrl: '', brandColor: '#d1d5db' },
  { id: 'share-sansar', name: 'ShareSansar', logoUrl: 'https://www.sharesansar.com/favicon.ico', brandColor: '#1d4ed8' },
  { id: 'mero-lagani', name: 'MeroLagani', logoUrl: 'https://merolagani.com/favicon.ico', brandColor: '#dc2626' },
  { id: 'fiscal-nepal', name: 'Fiscal Nepal', logoUrl: 'https://www.fiscalnepal.com/favicon.ico', brandColor: '#0ea5e9' },
  { id: 'bizmandu', name: 'Bizmandu', logoUrl: 'https://www.bizmandu.com/favicon.ico', brandColor: '#f59e0b' },
  { id: 'arthakhabar', name: 'Arthakhabar', logoUrl: 'https://www.arthakhabar.com/favicon.ico', brandColor: '#16a34a' },
  { id: 'nepse-alpha', name: 'NepseAlpha', logoUrl: 'https://www.nepsealpha.com/favicon.ico', brandColor: '#8b5cf6' },
];
