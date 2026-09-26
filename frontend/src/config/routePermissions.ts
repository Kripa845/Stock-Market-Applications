export type RouteRule = { permissions: string[]; mode: 'any' | 'all' };

export const ROUTE_RULES: Record<string, RouteRule> = {
  '/market':            { permissions: ['view_companies', 'view_market_data'], mode: 'all' },
  '/companies':         { permissions: ['view_companies'], mode: 'all' },
  '/companies/:symbol': { permissions: ['view_companies', 'view_price_history', 'view_market_data', 'view_news'], mode: 'all' },
  '/company-analysis':  { permissions: ['view_analysis', 'view_companies', 'view_price_history', 'view_market_data'], mode: 'all' },
  '/broker-analysis':   { permissions: ['view_analysis'], mode: 'all' },
  '/watchlist':             { permissions: ['view_watchlist', 'view_companies'], mode: 'all' },
  '/watchlist-comparison':  { permissions: ['view_analysis', 'view_companies'], mode: 'all' },
  '/news':              { permissions: ['view_news'], mode: 'all' },
  '/crawl':             { permissions: ['view_crawl_runs'], mode: 'all' },
  '/reports':           { permissions: ['view_reports', 'export_reports'], mode: 'all' },
  '/users':             { permissions: ['view_users'], mode: 'all' },
  '/roles-permissions': { permissions: ['view_roles'], mode: 'all' },
};
