export type RouteRule = { permissions: string[]; mode: 'any' | 'all' };

// A legacy permission and its page-level counterpart are alternatives, so roles
// created before page permissions keep opening the same routes.
export const ROUTE_RULES: Record<string, RouteRule> = {
  '/dashboard': { permissions: ['view_dashboard', 'view_market_data', 'view_news', 'view_companies'], mode: 'any' },
  '/market': { permissions: ['view_market_data', 'view_top_gainer', 'view_top_losers', 'view_top_turnover', 'view_top_volume', 'view_top_transactions'], mode: 'any' },
  '/market/indices': { permissions: ['view_market_data', 'view_indices'], mode: 'any' },
  '/market/dividends': { permissions: ['view_market_data', 'view_dividends'], mode: 'any' },
  '/market/calendar': { permissions: ['view_market_data', 'view_calendar'], mode: 'any' },
  '/market/weekdays': { permissions: ['view_market_data', 'view_weekday_summary'], mode: 'any' },
  '/market/day-by-day': { permissions: ['view_market_data', 'view_nepse_day_by_day'], mode: 'any' },
  '/market/month-by-month': { permissions: ['view_market_data', 'view_nepse_month_by_month'], mode: 'any' },
  '/market/quarterly-report': { permissions: ['view_market_data', 'view_latest_reports'], mode: 'any' },
  '/market/gainers': { permissions: ['view_market_data', 'view_top_gainer'], mode: 'any' },
  '/market/losers': { permissions: ['view_market_data', 'view_top_losers'], mode: 'any' },
  '/market/turnover': { permissions: ['view_market_data', 'view_top_turnover'], mode: 'any' },
  '/market/volume': { permissions: ['view_market_data', 'view_top_volume'], mode: 'any' },
  '/market/transactions': { permissions: ['view_market_data', 'view_top_transactions'], mode: 'any' },
  '/companies': { permissions: ['view_companies'], mode: 'any' },
  '/companies/:symbol': { permissions: ['view_companies', 'view_news', 'view_stock_details', 'view_market_data', 'view_price_history', 'view_trading_volume', 'view_analysis'], mode: 'any' },
  '/company-analysis': { permissions: ['view_analysis', 'view_companies', 'view_price_history', 'view_market_data', 'view_charts', 'view_stock_comparison', 'view_broker_explorer'], mode: 'any' },
  '/financial-reports': { permissions: ['view_financial_reports', 'view_market_data', 'view_reports'], mode: 'any' },
  '/floorsheet': { permissions: ['view_trading_volume', 'view_floorsheet'], mode: 'any' },
  '/floorsheet/summary': { permissions: ['view_trading_volume', 'view_floorsheet_summary', 'view_floorsheet'], mode: 'any' },
  '/technical-charts': { permissions: ['view_analysis', 'view_companies', 'view_price_history', 'view_market_data', 'view_charts'], mode: 'any' },
  '/broker-analysis': { permissions: ['view_analysis', 'view_broker_explorer'], mode: 'any' },
  '/top-brokers': { permissions: ['view_analysis', 'view_top_broker'], mode: 'any' },
  '/brokers': { permissions: ['view_analysis', 'view_broker_list'], mode: 'any' },
  '/broker-acc-dist': { permissions: ['view_analysis', 'view_broker_acc_dist_chart'], mode: 'any' },
  '/broker-position': { permissions: ['view_analysis', 'view_broker_explorer'], mode: 'any' },
  '/watchlist': { permissions: ['view_watchlist'], mode: 'any' },
  '/live-trading': { permissions: ['view_watchlist', 'view_companies', 'view_live_trading'], mode: 'any' },
  '/watchlist-comparison': { permissions: ['view_analysis', 'view_companies', 'view_watchlist_comparison'], mode: 'any' },
  '/compare': { permissions: ['view_analysis', 'view_stock_comparison'], mode: 'any' },
  '/news': { permissions: ['view_news'], mode: 'any' },
  '/announcements': { permissions: ['view_news', 'view_announcements'], mode: 'any' },
  '/crawl': { permissions: ['view_crawl_runs'], mode: 'any' },
  '/reports': { permissions: ['view_reports', 'export_reports', 'export_floorsheet', 'export_broker_analysis'], mode: 'any' },
  '/users': { permissions: ['view_users'], mode: 'any' },
  '/roles-permissions': { permissions: ['view_roles'], mode: 'any' },
};

// Ordered by the routes in App.tsx, with parameterized routes excluded.
export const LANDING_ROUTES = [
  '/dashboard', '/market', '/market/indices', '/market/dividends', '/market/calendar',
  '/market/weekdays', '/market/day-by-day', '/market/month-by-month', '/market/quarterly-report',
  '/market/gainers', '/market/losers', '/market/turnover', '/market/volume', '/market/transactions',
  '/companies', '/financial-reports', '/floorsheet', '/floorsheet/summary', '/technical-charts',
  '/broker-analysis', '/top-brokers', '/brokers', '/broker-acc-dist', '/broker-position',
  '/watchlist', '/live-trading', '/watchlist-comparison', '/compare', '/news', '/announcements',
  '/crawl', '/reports', '/users', '/roles-permissions',
];
