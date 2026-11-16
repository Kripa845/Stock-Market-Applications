# Roles & Permissions page-level mapping

Page-level permissions are alternatives to the legacy key on the same backend view. Each row below gives the URL registered in Django, its view class, the existing key, and the added page key(s). Where one endpoint is shared by multiple sidebar pages, its page keys are accepted together. Gainers and losers select their page key from the route/query so one does not authorize the other.

## Existing broad keys

| Endpoint | View class | Existing key | Added page key(s) |
|---|---|---|---|
| `/api/market/summary/` | `TrackedSummaryAPIView` | `view_market_data` | `view_dashboard`, all five Market Overview keys |
| `/api/market/movers/`, `/api/market/movers/live/` | `TrackedMoversAPIView`, `LiveTrackedMoversAPIView` | `view_market_data` | `view_top_gainer`, `view_top_losers` |
| `/api/market/heatmap/` | `HeatmapAPIView` | `view_market_data` | all five Market Overview keys |
| `/api/market/top-gainers/?type=gainers\|losers` | `TopMoversAPIView` | `view_market_data` | `view_top_gainer` for gainers; `view_top_losers` for losers |
| `/api/market/top-activity/` | `TopActivityAPIView` | `view_market_data` | `view_top_turnover`, `view_top_volume`, `view_top_transactions` |
| `/api/market/top-turnover/`, `/api/market/top-volume/`, `/api/market/top-transactions/` | `TrackedTopAPIView` | `view_market_data` | the matching turnover, volume, or transactions key |
| `/api/market/overview/`, `/api/market/overview/chart/`, `/api/market/overview/technical/` | `MarketOverviewAPIView`, `MarketOverviewChartAPIView`, `MarketOverviewTechnicalAPIView` | `view_market_data` | all five Market Overview keys |
| `/api/market-intelligence/breadth/`, `/heatmap/`, `/rankings/`, `/sectors/rotation/` | `MarketBreadthAPIView`, `MarketHeatmapAPIView`, `MarketRankingsAPIView`, `SectorRotationAPIView` | `view_market_data` | all five Market Overview keys |
| `/api/companies/top-gainers/`, `/api/companies/top-losers/` | `_TrackedMoversSideAPIView` (`TopGainersAPIView`, `TopLosersAPIView`) | `view_market_data` | matching gainer or loser key only |
| `/api/market-indices/{indices,sub-indices,analysis,top,tracked-sectors,history,intraday}/`; GET `/verify/` | `_MarketIndicesView` subclasses; `IndexVerificationAPIView` | `view_market_data` | `view_indices` |
| POST `/api/market-indices/verify/` | `IndexVerificationAPIView` | `run_crawler` (unchanged) | none |
| `/api/market-indices/support-resistance/` | `IndexSupportResistanceAPIView` | `view_analysis` | `view_indices` |
| `/api/market-indices/indicators/` | `IndexIndicatorSeriesAPIView` | `view_analysis` | `view_indices`, `use_indicators` |
| `/api/market-calendar/{month,day}/` | `_CalendarView` (`CalendarMonthAPIView`, `CalendarDayAPIView`) | `view_market_data` | `view_calendar` |
| `/api/market-calendar/weekdays/` | `WeekdaySummaryAPIView` | `view_market_data` | `view_weekday_summary` |
| `/api/market-calendar/months/` | `MonthSummaryAPIView` | `view_market_data` | `view_nepse_day_by_day` |
| `/api/market-calendar/monthly/` | `MonthlyReturnsAPIView` | `view_market_data` | `view_nepse_month_by_month` |
| `/api/market/dividends/` | `DividendListAPIView` | `view_market_data` | `view_dividends` |
| `/api/market/quarterly-report/`, `/api/market/quarterly-report/periods/` | `QuarterlyReportAPIView`, `QuarterlyReportPeriodsAPIView` | `view_market_data` | `view_latest_reports` |
| `/api/analysis/dashboard-summary/` | `DashboardSummaryAPIView` (`apps.analysis`) | `view_market_data` | `view_dashboard` |
| `/api/companies/{id}/floorsheet/` | `CompanyFloorsheetAPIView` | `view_market_data` | `view_floorsheet`, `view_stock_details` |
| `/api/companies/{id}/valuation/`, `/api/market/{id}/valuation/` | `CompanyValuationAPIView` (`apps.companies`, `apps.reports`) | `view_market_data` | `view_stock_details`, `view_latest_reports` |
| `/api/companies/{id}/financials/` | `CompanyFinancialsAPIView` | `view_market_data` | `view_stock_details`, `view_financial_reports` |
| `/api/market-data/` | `CompanyPriceList` | `view_price_history` | `view_charts` |
| `/api/companies/{symbol}/quote/`, `/{id}/prices/`, `/{id}/intraday/`, `/{id}/performance/`, `/{id}/technicals/` | `TrackedCompanyQuoteAPIView`, `CompanyPricesAPIView`, `CompanyIntradayBarsAPIView`, `CompanyPerformanceAPIView`, `CompanyTechnicalsAPIView` | `view_price_history` | `view_charts`, `view_stock_details`; technicals also accept `use_indicators` |
| `/api/stocks/{symbol}/intraday/` | `StockIntradayCandlesAPIView` | `view_price_history` | `view_floorsheet`, `view_charts` |
| `/api/companies/{symbol}/volume-anomalies/`, `/{symbol}/rvol/` | `CompanyVolumeAnomaliesAPIView`, `CompanyRvolAPIView` | `view_trading_volume` | `view_floorsheet`, `view_stock_details`, `view_charts` |
| `/api/floorsheet/` | `FloorsheetListAPIView` | `view_trading_volume` | `view_floorsheet` |
| `/api/floorsheet/summary/` | `FloorsheetSummaryAPIView` (inherits list behavior) | `view_trading_volume` | `view_floorsheet`, `view_floorsheet_summary` |
| `/api/analysis/floorsheet-grid/` | `FloorsheetGridAPIView` | `view_trading_volume` | `view_floorsheet`, `view_floorsheet_summary` |
| `/api/market-intelligence/relative-strength/` | `RelativeStrengthAPIView` | `view_analysis` | `view_charts` |
| `/api/market-intelligence/companies/{id}/technicals/` | `CompanyTechnicalsAPIView` | `view_analysis` | `view_charts`, `view_stock_details`, `use_indicators` |
| `/api/market-intelligence/companies/{id}/support-resistance/` | `CompanySupportResistanceAPIView` | `view_analysis` | `view_charts`, `view_stock_details` |
| `/api/market-intelligence/indicators/registry/` | `IndicatorRegistryAPIView` | `view_analysis` | `view_charts`, `use_indicators` |
| `/api/market-intelligence/companies/{id}/indicators/` | `CompanyIndicatorSeriesAPIView` | `view_analysis` | `view_charts`, `view_stock_details`, `use_indicators` |
| `/api/market/brokers/{symbol}/` | `CompanyBrokerActivityAPIView` (`apps.market_data`) | `view_analysis` | broker analysis keys and `view_charts` (used by the Technical Charts terminal) |
| `/api/analysis/companies/{id}/brokers/` | `CompanyBrokerActivityAPIView` (`apps.analysis`) | `view_analysis` | `view_broker_explorer` |
| `/api/analysis/brokers/` | `BrokerAnalysisAPIView` | `view_analysis` | `view_broker_explorer`, `view_broker_accumulation`, `view_broker_acc_dist_chart` |
| `/api/analysis/brokers/top/` | `TopBrokerAPIView` | `view_analysis` | `view_top_broker` |
| `/api/analysis/brokers/list/` | `BrokerListAPIView` | `view_analysis` | `view_broker_list` |
| `/api/analysis/brokers/{broker_id}/` | `BrokerDetailAPIView` | `view_analysis` | `view_broker_explorer` |
| `/api/analysis/broker-summary/`, `/broker-signal/`, `/broker-flow/` | `BrokerSummaryAPIView`, `BrokerSignalAPIView`, `BrokerFlowAPIView` | `view_analysis` | `view_broker_accumulation` |
| `/api/analysis/acc-dist/`, `/broker-activity/` | `AccDistAPIView`, `BrokerActivityAPIView` | `view_analysis` | `view_broker_acc_dist_chart` |
| `/api/analysis/broker-position/` | `BrokerPositionAPIView` | `view_analysis` | `view_broker_explorer` |
| `/api/analysis/cross-company/` | `CrossCompanyAnalysisAPIView` | `view_analysis` | `view_watchlist_comparison` |
| `/api/compare/`, `/api/compare/companies/`, `/api/compare/coverage/` | `CompareAPIView`, `CompareCompaniesAPIView`, `CompareCoverageAPIView` | `view_analysis` | `view_stock_comparison` |
| `/api/companies/{id}/behavior/`, `/{id}/behavior-summary/` | `CompanyBehaviorSummaryAPIView` (`apps.companies`, `apps.analysis`) | `view_analysis` | `view_stock_details` |
| `/api/companies/{symbol}/news-correlation/`, `/api/analysis/companies/{id}/news-pricecorrelation/` | `CompanyNewsSentimentCorrelationAPIView`, `CompanyNewsPriceCorrelationAPIView` | `view_analysis` | `view_stock_details` |
| `/api/companies/{id}/master-score/` | `CompanyMasterScoreAPIView` | `view_analysis` | `view_stock_details` |
| `/api/analysis/companies/{id}/categorized-news/` | `CompanyCategorizedNewsAPIView` | `view_analysis` | `view_stock_details` |

The Dashboard API also uses `User.has_any_app_permission()` for the old inline gates in `DashboardSummaryAPIView` (`apps.dashboard`), `AnalystDashboardAPIView`, and `ViewerDashboardAPIView`; the new dashboard key unlocks the market summary data sections. The Market Calendar's broker section now accepts any broker page key as well as `view_analysis`.

The page-only additions are `/api/announcements/` and `/api/announcements/filters/` (`AnnouncementList`, `AnnouncementFilterOptions`: `view_news` or `view_announcements`), and `/api/financial-reports/` plus `/filters/` (`financial_reports_api`, `financial_reports_filters`: `view_market_data`, `view_reports`, or `view_financial_reports`). The page-only export keys apply to `/api/reports/export/floorsheet/` (`ExportFloorsheetAPIView`: `export_reports` or `export_floorsheet`) and `/api/reports/export/brokers/` (`ExportBrokerActivityAPIView`: `export_reports` or `export_broker_analysis`).

## Needs a page assignment

The current frontend does not call `/api/analysis/daily/` (`DailyAnalysisListAPIView`), `/api/market/signals/{symbol}/` (`CompanySignalsAPIView`), or `/api/market/basket-index/` (`BasketIndexAPIView`). Those endpoints retain their existing broad permission key and have no new page key until their sidebar page is confirmed.

## Skipped because the backend feature is missing

No checkbox is exposed for calendar event create/edit/delete, announcement create/edit/delete, dividend export, stock or watchlist comparison export, chart layout saving, or financial-report upload/export. There is no corresponding backend endpoint for these actions.
