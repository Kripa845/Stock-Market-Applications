# File index

Every source file in the repo with line count and what it contains (auto-generated 2026-10-12).
Python: module docstring + public classes/functions. TypeScript: exported names.
Omitted: empty `__init__.py`, migrations, data dumps (*.json, *.csv, *.backup), images, lockfiles.

## (repository root)

- `.env.example` (74 lines)
- `.gitignore` (38 lines)
- `README.md` (124 lines)
- `docker-compose.yml` (160 lines)

## Backend

- `Backend/.gitignore` (111 lines)
- `Backend/Dockerfile` (55 lines)
- `Backend/companies.txt` (0 lines)
- `Backend/crawl_company_logos.py` (60 lines)
- `Backend/manage.py` (22 lines) — Django's command-line utility for administrative tasks.; main
- `Backend/pytest.ini` (4 lines)
- `Backend/requirements.txt` (104 lines)

## Backend/apps

- `Backend/apps/README.md` (58 lines)

## Backend/apps/analysis

- `Backend/apps/analysis/admin.py` (3 lines)
- `Backend/apps/analysis/apps.py` (5 lines) — AnalysisConfig
- `Backend/apps/analysis/models.py` (205 lines) — DailyAnalysis, VolumeAnomaly, NewsPriceCorrelation
- `Backend/apps/analysis/serializers.py` (232 lines) — VolumeAnomalySerializer, NewsPriceCorrelationSerializer, ForwardCorrelationMetricSerializer, NewsSentimentItemSerializer, NewsSentimentDailySerializer, NewsSentimentCorrelationSummarySerializer, NewsSentimentForwardResponseSerializer, NewsSentimentCorrelationQuerySerializer, DailyAnalysisSerializer, BrokerActivitySerializer
- `Backend/apps/analysis/tasks.py` (161 lines) — rebuild_company_analysis_task, rebuild_all_analysis
- `Backend/apps/analysis/urls.py` (48 lines)
- `Backend/apps/analysis/views.py` (1126 lines) — DailyAnalysisListAPIView, CompanyBehaviorSummaryAPIView, CompanyBrokerActivityAPIView, BrokerAnalysisAPIView, BrokerDetailAPIView, CompanyCategorizedNewsAPIView, CompanyNewsPriceCorrelationAPIView, CrossCompanyAnalysisAPIView, DashboardSummaryAPIView, get_queryset

## Backend/apps/analysis/management

- `Backend/apps/analysis/management/commands/backfill_market_analysis.py` (26 lines) — Command

## Backend/apps/analysis/services

- `Backend/apps/analysis/services/brokers.py` (304 lines) — build_broker_activity, sampled_floorsheet_dates, build_top_stock_by_broker
- `Backend/apps/analysis/services/daily_metrics.py` (553 lines) — detect_volume_anomalies, calculate_daily_vwap, calculate_period_vwap, calculate_volume_baseline, calculate_pressure, calculate_daily_return_pct, build_analysis_rows, rebuild_company_analysis
- `Backend/apps/analysis/services/news_market_reaction.py` (237 lines) — News-event reactions aligned to the company's observed trading sessions.; build_exploratory_news_reaction, build_news_market_reaction
- `Backend/apps/analysis/services/news_price_correlation.py` (117 lines) — Persisted exploratory correlations between categorized news and future moves.; calculate_news_price_correlations, rebuild_company_news_price_correlation
- `Backend/apps/analysis/services/news_sentiment_forward.py` (149 lines) — Exploratory forward market comparisons for categorized company news.; build_news_sentiment_forward_series, get_company_news_sentiment_forward
- `Backend/apps/analysis/services/volume_anomaly.py` (64 lines) — Persisted rolling volume anomaly calculations over crawled trading sessions.; detect_volume_anomalies, rebuild_company_volume_anomalies

## Backend/apps/analysis/tests

- `Backend/apps/analysis/tests/test_broker_api.py` (185 lines) — BrokerAnalysisApiTests
- `Backend/apps/analysis/tests/test_brokers.py` (338 lines) — Broker net buy/sell analysis over FloorsheetTransaction. Gross activity and net position are different questions and must not be conflated.; BrokerTestBase, BrokerCoverageTests, BrokerValueTests, TopMetricTests, FilteringTests, DataQualityTests, OrderingAndQueryTests
- `Backend/apps/analysis/tests/test_integration.py` (225 lines) — End-to-end: DailyPrice -> analysis task -> DailyAnalysis -> API. Verifies the pieces agree with each other, and that the dashboard reads stored state rather tha…; AnalysisPipelineTests
- `Backend/apps/analysis/tests/test_persisted_market_features.py` (62 lines) — VolumeAnomalyTests, NewsPriceCorrelationTests
- `Backend/apps/analysis/tests/test_pressure.py` (244 lines) — OHLCV pressure proxy (method: OHLCV_PRICE_VOLUME). score = 50*D + vwap_weight*V + 20*D*C D = price direction, V = close vs daily VWAP, C = volume conviction vwa…; PressureDirectionTests, PressureMissingInputTests, PressureContractTests
- `Backend/apps/analysis/tests/test_volume_baseline.py` (286 lines) — Volume baseline: mean of the PREVIOUS 20 TRADING SESSIONS. Not calendar days, and never including the day being scored.; VolumeBaselineTests, BaselineExcludesTodayTests, NonTradingDayTests, DuplicateDateTests, DeterminismTests
- `Backend/apps/analysis/tests/test_vwap.py` (143 lines) — Daily VWAP: turnover / volume, per trading day.; FakePrice, DailyVWAPTests, PeriodVWAPTests, VWAPInAnalysisRowsTests

## Backend/apps/companies

- `Backend/apps/companies/admin.py` (4 lines)
- `Backend/apps/companies/apps.py` (5 lines) — CompaniesConfig
- `Backend/apps/companies/models.py` (48 lines) — Company, TrackedCompany
- `Backend/apps/companies/selection.py` (29 lines) — tracked_active_companies, parse_symbols, select_crawl_companies
- `Backend/apps/companies/serializers.py` (140 lines) — CompanySerializer
- `Backend/apps/companies/test_selection.py` (60 lines) — CrawlSelectionTests, SeedCompaniesTests
- `Backend/apps/companies/tests.py` (55 lines) — CrawledPricePresentationTests
- `Backend/apps/companies/update_prices.py` (57 lines) — to_decimal, Command
- `Backend/apps/companies/urls.py` (96 lines)
- `Backend/apps/companies/utils.py` (5 lines) — normalize_symbol, validate_symbol
- `Backend/apps/companies/views.py` (445 lines) — CompanyListCreateAPIView, CompanyDetailUpdateDestroyAPIView, CompanyToggleTrackAPIView, CompanyPricesAPIView, CompanyIntradayBarsAPIView, CompanyVolumeAnomaliesAPIView, CompanyRvolAPIView, CompanyNewsSentimentCorrelationAPIView, CompanyFloorsheetAPIView, CompanySectorsAPIView, get_queryset, top_gainers …

## Backend/apps/companies/management

- `Backend/apps/companies/management/commands/import_company_logos.py` (79 lines) — Command
- `Backend/apps/companies/management/commands/seed_admin.py` (54 lines) — Command
- `Backend/apps/companies/management/commands/seed_companies.py` (283 lines) — Command

## Backend/apps/crawler_runs

- `Backend/apps/crawler_runs/admin.py` (3 lines)
- `Backend/apps/crawler_runs/apps.py` (5 lines) — CrawlerRunsConfig
- `Backend/apps/crawler_runs/models.py` (227 lines) — CrawlRun
- `Backend/apps/crawler_runs/serializers.py` (149 lines) — CrawlRunSerializer, TriggerCrawlRequestSerializer
- `Backend/apps/crawler_runs/tasks.py` (557 lines) — run_crawl, crawl_all_news, crawl_daily_prices, crawl_brokers, crawl_floorsheet, crawl_floorsheet_sample, run_full_crawl_pipeline, recover_stale_crawls
- `Backend/apps/crawler_runs/tests.py` (994 lines) — TradingDataSpider: date-driven rolling window and pagination. These tests drive the spider's callbacks directly with synthetic DataTables payloads, so no networ…; make_row, make_response, sessions, SpiderHarness, ParsingTests, WindowAnchoringTests, PaginationTests, DateFilteringTests, DuplicateAndMissingDataTests, IncompleteDatasetTests, FormDataTests, CompanySymbolMappingTests
- `Backend/apps/crawler_runs/urls.py` (35 lines)
- `Backend/apps/crawler_runs/views.py` (400 lines) — CrawlRunListCreateAPIView, CrawlRunDetailAPIView, CrawlRunCancelAPIView, CrawlRunRetryAPIView

## Backend/apps/crawler_runs/management

- `Backend/apps/crawler_runs/management/commands/backfill_floorsheet.py` (40 lines) — Command
- `Backend/apps/crawler_runs/management/commands/recover_crawls.py` (121 lines) — Management command: recover_crawls Marks genuinely *stale* RUNNING/PENDING CrawlRuns as FAILED. A run is considered stale when: - Its ``started_at`` is older th…; Command
- `Backend/apps/crawler_runs/management/commands/run_crawl.py` (73 lines) — Command

## Backend/apps/crawler_runs/services

- `Backend/apps/crawler_runs/services/keyword_matcher.py` (0 lines)

## Backend/apps/dashboard

- `Backend/apps/dashboard/admin.py` (3 lines)
- `Backend/apps/dashboard/apps.py` (6 lines) — DashboardConfig
- `Backend/apps/dashboard/export_views.py` (1237 lines) — Export Data / Reports ===================== Permission gate: ``export_reports`` (existing key — wired through the existing dynamic role/permission system; no ro…; ExportContentNegotiation, ExportCompanyListAPIView, ExportNewsAPIView, ExportTradingAPIView, ExportBrokerActivityAPIView, ExportFloorsheetAPIView, ExportReportAPIView
- `Backend/apps/dashboard/models.py` (0 lines)
- `Backend/apps/dashboard/serializers.py` (17 lines) — DashboardSummarySerializer
- `Backend/apps/dashboard/tests.py` (3 lines)
- `Backend/apps/dashboard/urls.py` (91 lines)
- `Backend/apps/dashboard/views.py` (271 lines) — DashboardSummaryAPIView, AdminDashboardAPIView, AnalystDashboardAPIView, ViewerDashboardAPIView

## Backend/apps/market_data

- `Backend/apps/market_data/admin.py` (29 lines) — TradingHolidayAdmin, DividendAnnouncementAdmin, IntradayCandleAdmin
- `Backend/apps/market_data/apps.py` (5 lines) — MarketDataConfig
- `Backend/apps/market_data/market_urls.py` (31 lines)
- `Backend/apps/market_data/market_views.py` (311 lines) — /api/market/ -- the tracked-companies dashboard. Every number covers ONLY the tracked companies (see services.market_stats), so each response carries ``"scope":…; PublicTrackedSnapshotAPIView, TrackedSummaryAPIView, TrackedMoversAPIView, TrackedTopAPIView, CompanyBrokerActivityAPIView, CompanySignalsAPIView, BasketIndexAPIView, DividendListAPIView, WatchlistAPIView, CompanyNewsAPIView
- `Backend/apps/market_data/models.py` (253 lines) — DailyPrice, FloorsheetTransaction, IntradayCandle, Broker, TradingHoliday, DividendAnnouncement
- `Backend/apps/market_data/rvol_serializers.py` (29 lines) — RvolQuerySerializer, RvolPointSerializer
- `Backend/apps/market_data/serializers.py` (188 lines) — broker_metadata, broker_payload, BrokerMetadataListSerializer, DailyPriceSerializers, FloorsheetSerializer, IntradayCandleQuerySerializer, IntradayCandleSerializer
- `Backend/apps/market_data/stock_urls.py` (12 lines)
- `Backend/apps/market_data/tasks.py` (88 lines) — Kept for backward compatibility / discoverability from this app. The actual crawl orchestration (subprocess-based `scrapy crawl`, retry policy, beat schedule wi…; derive_price_fields_task, build_intraday_candles_live, finalize_intraday_candles
- `Backend/apps/market_data/test_intraday_candles.py` (383 lines) — Intraday candles: bucketing, dedupe, idempotent rebuilds, session boundaries and the API.; at, CandleTestCase, BucketingTests, SessionBoundaryTests, RebuildTests, ShareHubDedupeTests, FetchPagingTests, IntradayEndpointTests, NepalTimeTests, FixShareHubTimesCommandTests
- `Backend/apps/market_data/test_market_stats.py` (267 lines) — TrackedMarketFixture, DerivePriceFieldsTests, DividendRowsTests, BrokerActivityTests, SignalsTests, TradingDayTests, EqualWeightBasketTests, MarketApiTests, PublicSnapshotTests
- `Backend/apps/market_data/test_movers.py` (380 lines) — Tests for services.movers -- the one definition of a tracked company's session change.; trading_days, MoversFixture, OneSessionTests, RankingTests, SourceChangeTests, MultiSessionTests, EmptyDataTests, MoversApiTests, SpiderSourceChangeTests, PipelineSourceChangeTests
- `Backend/apps/market_data/tests.py` (644 lines) — Trading-calendar tests: sessions, not calendar days.; CalendarTestBase, LatestTradingDateTests, PreviousSessionTests, SampleDateTests, RollingWindowTests, TradingDatesTests, IntradayAggregationTests, BrokerDirectoryTests, PriceSourceParamTests
- `Backend/apps/market_data/urls.py` (19 lines)
- `Backend/apps/market_data/views.py` (187 lines) — FloorsheetFilter, CompanyPriceList, FloorsheetListAPIView, StockIntradayCandlesAPIView, TrackedMoversView, TrackedMoversListView
- `Backend/apps/market_data/volume_anomalies.py` (68 lines) — Calculation helpers for company volume anomaly history.; get_volume_anomalies
- `Backend/apps/market_data/volume_anomaly_serializers.py` (18 lines) — VolumeAnomalySerializer, VolumeAnomalyQuerySerializer

## Backend/apps/market_data/management

- `Backend/apps/market_data/management/commands/backfill_price_fields.py` (27 lines) — Fill DailyPrice.transactions (floorsheet trade count) for rows already stored. Usage: python manage.py backfill_price_fields python manage.py backfill_price_fie…; Command
- `Backend/apps/market_data/management/commands/check_brokers.py` (34 lines) — Command
- `Backend/apps/market_data/management/commands/fix_sharehub_trade_times.py` (84 lines) — is_shifted, Command
- `Backend/apps/market_data/management/commands/import_brokers.py` (42 lines) — Command
- `Backend/apps/market_data/management/commands/load_sharehub_floorsheet.py` (234 lines) — fetch, parse_trade_time, check_database_matches_model, Command
- `Backend/apps/market_data/management/commands/rebuild_intraday_candles.py` (78 lines) — Command

## Backend/apps/market_data/services

- `Backend/apps/market_data/services/import_prices.py` (32 lines) — import_daily_price
- `Backend/apps/market_data/services/intraday.py` (37 lines) — aggregate_intraday_trades
- `Backend/apps/market_data/services/intraday_candles.py` (201 lines) — session_bounds, bucket_start_for, minute_rows, roll_up, rebuild_day, rebuild_range, latest_candle_date
- `Backend/apps/market_data/services/market_stats.py` (298 lines) — Statistics for the tracked-companies dashboard. SCOPE: only the active, tracked companies (``Company.tracking.is_tracked``) and only crawled prices (``DailyPric…; tracked_companies, tracked_prices, broker_activity, signals, basket_index, dividend_rows
- `Backend/apps/market_data/services/movers.py` (443 lines) — normalize_period, corporate_action_threshold, resolve_sessions, annotated_companies, provenance, incomplete_session_warning, tracked_movers, tracked_movers_page, tracked_summary, top_by, company_rows
- `Backend/apps/market_data/services/price_fields.py` (39 lines) — Fill DailyPrice.transactions from floorsheet trades already stored. The ShareSansar price-history endpoint has no transaction count, so transactions = number of…; real_floorsheet, derive_price_fields
- `Backend/apps/market_data/services/price_source.py` (35 lines) — requested_price_source, with_crawled_price
- `Backend/apps/market_data/services/rvol.py` (80 lines) — Relative volume calculations for crawled company trading history.; calculate_rvol, get_company_rvol
- `Backend/apps/market_data/services/sharehub_floorsheet.py` (150 lines) — ShareHubError, fetch_page, fetch_company_day, build_transactions, save_transactions, sync_company_day, sync_day
- `Backend/apps/market_data/services/sharehub_time.py` (26 lines) — ShareHub trade-time parsing. ShareHub labels ``tradeTime`` with a trailing "Z" (UTC), but the clock values are already Nepal time: the last trades of a session …; parse_sharehub_time
- `Backend/apps/market_data/services/trading_calendar.py` (335 lines) — Trading-calendar helpers. NEPSE does not trade on weekends or public holidays, and the set of holidays is not derivable from a calendar rule. Rather than guessi…; trading_dates, latest_trading_date, previous_trading_sessions, select_sample_dates, rolling_window_bounds, is_trading_date
- `Backend/apps/market_data/services/trading_days.py` (57 lines) — Which calendar days NEPSE trades. Two inputs, nothing hardcoded elsewhere: * ``settings.NEPSE_TRADING_WEEKS``: the trading week in force on each date (Sunday-Th…; trading_weekdays, is_trading_weekday, is_market_day, market_closed_reason

## Backend/apps/market_intelligence

- `Backend/apps/market_intelligence/app_settings.py` (3 lines) — Defaults for the market intelligence app; project settings may override these.
- `Backend/apps/market_intelligence/apps.py` (7 lines) — MarketIntelligenceConfig
- `Backend/apps/market_intelligence/models.py` (103 lines) — MarketBreadthSnapshot, ProxyIndexSnapshot, CompanyTechnicalSnapshot, SectorRotationSnapshot
- `Backend/apps/market_intelligence/tasks.py` (25 lines) — build_daily_market_intelligence
- `Backend/apps/market_intelligence/urls.py` (23 lines)
- `Backend/apps/market_intelligence/views.py` (473 lines) — MarketBreadthAPIView, MarketHeatmapAPIView, MarketRankingsAPIView, SectorRotationAPIView, RelativeStrengthAPIView, CompanyTechnicalsAPIView, IndicatorRegistryAPIView, CompanyIndicatorSeriesAPIView

## Backend/apps/market_intelligence/indicators

- `Backend/apps/market_intelligence/indicators/__init__.py` (5 lines) — NEPSE technical indicator library. See registry.py for the full list and how to add one.
- `Backend/apps/market_intelligence/indicators/core.py` (185 lines) — Shared building blocks for the indicator library. Every series is a plain list (oldest first) the same length as the input. ``None`` marks "not enough data yet"…; to_floats, check_period, combine, rolling, rolling_multi, seeded, sma, ema, rma, wma, highest, lowest …
- `Backend/apps/market_intelligence/indicators/custom.py` (94 lines) — Standard versions of indicators NepseAlpha offers under its own names. NepseAlpha's exact formulas are unpublished; these follow the commonly published definiti…; inside_bar, ut_bot, zero_lag_ema, zero_lag_macd, tdi, weinstein_stage
- `Backend/apps/market_intelligence/indicators/market.py` (140 lines) — Indicators that need more than one stock's prices: breadth, relative strength and tick data. Breadth functions take ``universe``: one dict per company mapping d…; advance_decline, ad_volume_line, percent_above_ma, net_new_highs_lows, ratio, spread, relative_strength, mansfield_rs, correlation, log_correlation, tick_buy_sell
- `Backend/apps/market_intelligence/indicators/momentum.py` (207 lines) — Momentum indicators and oscillators (drawn in panels).; macd, rsi, stochastic, stoch_rsi, williams_r, typical, cci, momentum, roc, price_oscillator, awesome, accelerator …
- `Backend/apps/market_intelligence/indicators/moving_averages.py` (157 lines) — Moving averages (drawn over the price).; sma, ema, wma, dema, tema, hull_ma, smma, vwma, mcginley, alma, lsma, linreg_slope …
- `Backend/apps/market_intelligence/indicators/price.py` (83 lines) — Price transforms and levels.; average_price, median_price, typical_price, pivot_points, week_52_high_low, fractals
- `Backend/apps/market_intelligence/indicators/registry.py` (389 lines) — The indicator registry: what exists, what it needs, its parameters, outputs and how to draw it. Adding an indicator: 1. write a function in the matching categor…; Param, Output, Indicator, P, O, resolve_params, compute, registry_payload
- `Backend/apps/market_intelligence/indicators/trend.py` (231 lines) — Trend indicators.; adx, aroon, parabolic_sar, supertrend, vortex, ichimoku, alligator, choppiness, trend_strength, mass_index, chande_kroll, accumulative_swing_index …
- `Backend/apps/market_intelligence/indicators/volatility.py` (119 lines) — Volatility measures, bands and channels. "Standard deviation" is the population form throughout.; atr, bollinger, bollinger_percent_b, bollinger_width, keltner, donchian, envelopes, std_dev, standard_error, standard_error_bands, chaikin_volatility, log_returns …
- `Backend/apps/market_intelligence/indicators/volume.py` (199 lines) — Volume-based indicators.; volume_bars, volume_oscillator, obv, net_volume, clv, accumulation_distribution, chaikin_money_flow, chaikin_oscillator, money_flow_index, ease_of_movement, force_index, klinger …

## Backend/apps/market_intelligence/management

- `Backend/apps/market_intelligence/management/commands/backfill_market_intelligence.py` (40 lines) — Command

## Backend/apps/market_intelligence/services

- `Backend/apps/market_intelligence/services/sector_rotation.py` (105 lines) — Rolling sector returns/ranks using previous-session turnover weights.; compute_sector_rotation_snapshots
- `Backend/apps/market_intelligence/services/snapshots.py` (317 lines) — Deterministic daily market calculations sourced only from DailyPrice.; compute_market_snapshots
- `Backend/apps/market_intelligence/services/technicals.py` (190 lines) — Daily technical snapshots computed from observed, valid-market-session OHLCV.; compute_company_technical_snapshots

## Backend/apps/market_intelligence/tests

- `Backend/apps/market_intelligence/tests/test_api.py` (73 lines) — MarketIntelligenceApiTests
- `Backend/apps/market_intelligence/tests/test_indicator_library.py` (931 lines) — Indicator library tests. Every registry indicator has a ``test_<id>`` method. Most compare against an independent pandas reference (rolling windows, SMA-seeded …; seeded, r_ema, r_rma, r_wma, r_tr, r_rsi, r_linfit, out, IndicatorAssertions, MovingAverageTests, MomentumTests, TrendTests …
- `Backend/apps/market_intelligence/tests/test_snapshots.py` (201 lines) — MarketSnapshotTests
- `Backend/apps/market_intelligence/tests/test_technicals.py` (87 lines) — TechnicalSnapshotTests

## Backend/apps/news

- `Backend/apps/news/admin.py` (25 lines) — NewsArticleAdmin
- `Backend/apps/news/apps.py` (5 lines) — NewsConfig
- `Backend/apps/news/items.py` (8 lines) — NewsArticleItem
- `Backend/apps/news/models.py` (169 lines) — RawArticle, NewsArticle, ArticleCompanyTag, CategorizationCorrection
- `Backend/apps/news/selectors.py` (12 lines) — real_articles, real_tags
- `Backend/apps/news/serializers.py` (130 lines) — ArticleCompanyTagSerializer, CategorizationCorrectionSerializer, NewsArticleSerializer, PublicNewsSerializer, RecategorizeRequestSerializer
- `Backend/apps/news/tasks.py` (254 lines) — categorize_article_task, categorize_unprocessed_news_task, recategorize_all_news_task, analyze_article_sentiment_task, analyze_unscored_sentiment_task, rescore_all_sentiment_task
- `Backend/apps/news/urls.py` (48 lines)
- `Backend/apps/news/views.py` (390 lines) — NewsArticleListAPIView, NewsArticleDetailAPIView, NewsRecategorizeAPIView, NewsTriggerCategorizeAPIView, PublicLatestNewsAPIView, NewsStatsAPIView, CategorizationCorrectionListAPIView

## Backend/apps/news/management

- `Backend/apps/news/management/commands/backfill_news_images.py` (54 lines) — Management command to fill NewsArticle.image_url from HTML already stored in RawArticle. No network requests are made. Usage: python manage.py backfill_news_ima…; Command
- `Backend/apps/news/management/commands/categorize_news.py` (137 lines) — Management command to categorize existing news articles. Usage: python manage.py categorize_news python manage.py categorize_news --all python manage.py categor…; Command
- `Backend/apps/news/management/commands/repair_news_dates.py` (68 lines) — Repair news articles whose published_at is in the future because a Bikram Sambat date (e.g. "१२ श्रावण २०८३") was parsed as a Gregorian year. The real date is r…; header_text, Command

## Backend/apps/news/services

- `Backend/apps/news/services/article_images.py` (85 lines) — normalize_image_url, extract_image_url
- `Backend/apps/news/services/categorization.py` (764 lines) — normalize_text, build_article_text, build_company_profile, get_embedding_model, encode_text, calculate_cosine_similarity, invalidate_company_cache, get_company_profiles_cache, calculate_lexical_score, calculate_hybrid_score, classify_evidence, decide_company_match …
- `Backend/apps/news/services/categorizer.py` (4 lines)
- `Backend/apps/news/services/confidence.py` (260 lines) — normalize_text, find_company_candidates
- `Backend/apps/news/services/corrections.py` (236 lines) — get_correction_map, is_suppressed, is_pinned, apply_remove, apply_add, apply_update
- `Backend/apps/news/services/embedding_classifier.py` (0 lines)
- `Backend/apps/news/services/keyword_matcher.py` (298 lines) — normalize_text, find_company_candidates
- `Backend/apps/news/services/llm_classifier.py` (0 lines)
- `Backend/apps/news/services/ner_classifier.py` (0 lines)
- `Backend/apps/news/services/sentiment.py` (490 lines) — SentimentResult, clean_text, detect_language, tokenize, score_to_label, analyze_text, analyze_article, apply_sentiment

## Backend/apps/news/tests

- `Backend/apps/news/tests/test_article_images.py` (136 lines) — page, ExtractImageUrlTests, BackfillNewsImagesCommandTests
- `Backend/apps/news/tests/test_bs_dates.py` (30 lines) — BikramSambatDateTests
- `Backend/apps/news/tests/test_categorizations.py` (502 lines) — NewsFixtureMixin, EvidenceClassificationTests, DecisionTierTests, PatchedCategorizationMixin, MultiLabelTests, ManualCorrectionTests
- `Backend/apps/news/tests/test_news_api.py` (483 lines) — FakeEmbeddingModel, NewsCategorizationTests
- `Backend/apps/news/tests/test_no_synthetic_data.py` (72 lines) — Synthetic (seeded) data and made-up defaults must never reach an API response.; NoSyntheticDataTests
- `Backend/apps/news/tests/test_public_news.py` (73 lines) — PublicLatestNewsTests
- `Backend/apps/news/tests/test_sentiment.py` (381 lines) — Sentiment pipeline: clean -> detect language -> score -> label -> save.; CleanTextTests, LanguageDetectionTests, ScoringTests, LabelThresholdTests, MissingContentTests, UnsupportedLanguageTests, FailureHandlingTests, PersistenceTests

## Backend/apps/users

- `Backend/apps/users/admin.py` (3 lines)
- `Backend/apps/users/apps.py` (5 lines) — UsersConfig
- `Backend/apps/users/company_access.py` (392 lines) — is_unrestricted_user, get_accessible_company_ids, has_company_access, user_can_access_company, require_company_access, require_company_id_access, filter_company_queryset, filter_queryset_by_user_companies, accessible_company_queryset, require_permission, require_permission_and_company, validate_company_ids …
- `Backend/apps/users/company_permissions.py` (35 lines) — check_company_access
- `Backend/apps/users/managers.py` (5 lines) — CustomUserManager
- `Backend/apps/users/models.py` — RolePermissionConfig, CustomRole, User, UserCompanyAccess, Watchlist, WatchlistItem
- `Backend/apps/market_data/services/watchlist.py` — watchlist rows (latest crawled session, sparkline, holding value) and summary totals
- `Backend/apps/users/permissions.py` (127 lines) — IsAdminUserRole, IsAnalystUserRole, IsViewerUserRole, HasAppPermission, HasViewMethodPermissions, ReadOnlyOrAdmin, ReadOnlyOrAnalyst, is_admin_account, missing_grants
- `Backend/apps/users/serializers.py` (676 lines) — validate_permission_dependencies, CustomTokenObtainPairSerializer, UserRegistrationSerializer, UserCompanyAccessItemSerializer, UserCompanyAccessListSerializer, AdminUserCreateSerializer, UserSerializer, MeSerializer, AdminUserUpdateSerializer, CustomRoleSerializer, RolePermissionConfigSerializer, RolePermissionSerializer …
- `Backend/apps/users/test_permission_dependencies.py` (460 lines) — Tests for permission dependency validation — Users topic (Section 1.2 of spec). The dependency chain for the Users group is: view_users ↓ create_users ↓ edit_us…; ValidatePermissionDependenciesUnitTests, BuiltInRoleDependencyAPITests, CustomRoleDependencyAPITests
- `Backend/apps/users/test_rbac_matrix.py` (168 lines) — make_user, as_user, jwt_client, call, PermissionMatrixTests, EscalationTests
- `Backend/apps/users/tests.py` (424 lines) — RolePermissionAPITests, UserCompanyAccessHelperTests, UserCompanyAccessAPITests, NewsCategorizationCompanyAccessTests, CompanyScopedEndpointTests, AuthHardeningTests
- `Backend/apps/users/urls.py` (121 lines)
- `Backend/apps/users/views.py` (1079 lines) — assignment_escalation, CustomRoleListCreateAPIView, CustomRoleDetailAPIView, RolePermissionDefinitionsAPIView, CustomTokenObtainPairView, RegisterAPIView, MeAPIView, MePermissionsAPIView, AdminUserListCreateAPIView, AdminUserDetailAPIView, AnalystListAPIView, RolePermissionDetailAPIView …

## Backend/config

- `Backend/config/__init__.py` (5 lines)
- `Backend/config/asgi.py` (16 lines) — ASGI config for config project. It exposes the ASGI callable as a module-level variable named ``application``. For more information on this file, see https://do…
- `Backend/config/celery.py` (20 lines)
- `Backend/config/settings.py` (386 lines) — Django settings for config project.
- `Backend/config/settings_test.py` (6 lines)
- `Backend/config/urls.py` (35 lines)
- `Backend/config/wsgi.py` (16 lines) — WSGI config for config project. It exposes the WSGI callable as a module-level variable named ``application``. For more information on this file, see https://do…

## Backend/crawlers

- `Backend/crawlers/runner.py` (239 lines) — Scrapy subprocess runner. Each call to ``run_spider()`` launches a *new* ``scrapy crawl`` subprocess, waits for it (up to ``timeout`` seconds), and returns a ``…; SpiderRunResult, run_spider, run_spiders
- `Backend/crawlers/scrapy.cfg` (11 lines)

## Backend/crawlers/base

- `Backend/crawlers/base/client.py` (33 lines) — HTTPClient

## Backend/crawlers/crawlers

- `Backend/crawlers/crawlers/items.py` (53 lines) — NewsItem, DailyTradingDataItem, FloorsheetItem
- `Backend/crawlers/crawlers/middlewares.py` (100 lines) — CrawlersSpiderMiddleware, CrawlersDownloaderMiddleware
- `Backend/crawlers/crawlers/pipelines.py` (1476 lines) — parse_integer, parse_decimal, clean_text, clean_body, normalize_datetime, update_crawl_metrics, CrawlRunPipeline, NewsPipeline, TradingDataPipeline, FloorsheetPipeline, BrokerPipeline, MoneymitraBrokerPipeline
- `Backend/crawlers/crawlers/settings.py` (52 lines)

## Backend/crawlers/crawlers/spiders

- `Backend/crawlers/crawlers/spiders/__init__.py` (4 lines)
- `Backend/crawlers/crawlers/spiders/arthakhabar.py` (250 lines) — ArthakhabarSpider
- `Backend/crawlers/crawlers/spiders/base_news.py` (137 lines) — BaseNewsSpider
- `Backend/crawlers/crawlers/spiders/bizmandu.py` (270 lines) — BizmanduSpider
- `Backend/crawlers/crawlers/spiders/brokers.py` (52 lines) — BrokersSpider
- `Backend/crawlers/crawlers/spiders/fiscalnepal.py` (134 lines) — FiscalnepalSpider
- `Backend/crawlers/crawlers/spiders/floorsheet.py` (667 lines) — FloorsheetSpider
- `Backend/crawlers/crawlers/spiders/merolagani.py` (185 lines) — MerolaganiSpider
- `Backend/crawlers/crawlers/spiders/moneymitra_brokers.py` (45 lines) — MoneymitraBrokersSpider
- `Backend/crawlers/crawlers/spiders/nepalipaisa.py` (21 lines) — NepalipaisaSpider
- `Backend/crawlers/crawlers/spiders/nepsealpha.py` (181 lines) — NepseAlpha news spider. Listing: https://nepsealpha.com/all-news?page=home (also ?cid=<n> per category) Article: https://nepsealpha.com/<slug>; NepsealphaSpider
- `Backend/crawlers/crawlers/spiders/sharesansar.py` (825 lines) — SharesansarSpider
- `Backend/crawlers/crawlers/spiders/trading_data.py` (839 lines) — parse_trading_date, parse_number, TradingDataSpider

## Backend/crawlers/crawlers/utils

- `Backend/crawlers/crawlers/utils/dates.py` (118 lines) — parse_bikram_sambat, parse_datetime
- `Backend/crawlers/crawlers/utils/text.py` (10 lines) — clean_text
- `Backend/crawlers/crawlers/utils/urls.py` (46 lines) — canonicalize_url

## Backend/crawlers/utils

- `Backend/crawlers/utils/article_validator.py` (18 lines) — is_valid_article
- `Backend/crawlers/utils/date_parser.py` (204 lines) — parse_datetime
- `Backend/crawlers/utils/text.py` (10 lines) — clean_text
- `Backend/crawlers/utils/url_utils.py` (35 lines) — canonicalize_url

## frontend

- `frontend/.gitignore` (24 lines)
- `frontend/Dockerfile` (39 lines)
- `frontend/README.md` (32 lines)
- `frontend/index.html` (13 lines)
- `frontend/nginx.conf` (23 lines)
- `frontend/postcss.config.js` (6 lines)
- `frontend/tailwind.config.js` (36 lines)
- `frontend/vite.config.ts` (7 lines)

## frontend/public/broker-logos

- `frontend/public/broker-logos/README.md` (2 lines)

## frontend/src

- `frontend/src/App.css` (184 lines)
- `frontend/src/App.tsx` (517 lines) — App
- `frontend/src/index.css` (660 lines)
- `frontend/src/main.tsx` (13 lines)
- `frontend/src/vite-env.d.ts` (9 lines)

## frontend/src/api

- `frontend/src/api/admin.ts` (78 lines) — adminApi
- `frontend/src/api/analysis.ts` (660 lines) — PressureLabel, PressureExplanation, DailyAnalysis, BrokerActivity, BehaviorSummary, BrokerActivityResponse, BrokerCompanyChoice, BrokerAnalysisResponse, BrokerDetailResponse, CorrelationDataPoint, NewsPriceCorrelation, F
- `frontend/src/api/auth.ts` (76 lines) — LoginResponse, RegisterPayload, PermissionsResponse, authApi
- `frontend/src/api/client.ts` (68 lines) — apiClient
- `frontend/src/api/companies.ts` (86 lines) — CompanyQuery, PaginatedCompanies, getCompanies, getCompany, updateCompany, deleteCompany, setCompanyTracking, getCompanySectors
- `frontend/src/api/companyAccess.ts` (98 lines) — CompanyAccess, CompanyAccessResponse, SaveCompanyAccessPayload, getUserCompanyAccess, saveUserCompanyAccess
- `frontend/src/api/crawler.ts` (87 lines) — CrawlQuery, PaginatedCrawls, getCrawlRuns, getCrawlRun, triggerCrawl, cancelCrawl, retryCrawl
- `frontend/src/api/dashboard.ts` (56 lines) — RecentCrawlRun, AdminDashboard, dashboardApi
- `frontend/src/api/exports.ts` (186 lines) — ExportCompany, ExportDataType, ExportFormat, SentimentFilter, ExportParams, exportsApi, _cleanParams
- `frontend/src/api/market.ts` (212 lines) — SparkPoint, MoverBucket, ExclusionReason, TrackedRow, Provenance, MoverPeriod, MoversResponse, TrackedSummary, BasketRow, BasketIndex, PublicMover, PublicSnapshot, BrokerRow, BrokerWindow, Signals, DividendRow, Watchlist
- `frontend/src/api/marketIntelligence.ts` (136 lines) — MarketBreadth, MarketTile, RankingMetric, RankedStock, marketIntelligenceApi, IndicatorParams, IndicatorParamDef, IndicatorDef, IndicatorRegistry, IndicatorResult, IndicatorSeriesResponse
- `frontend/src/api/news.ts` (74 lines) — NewsQueryParams, PublicNewsArticle, newsApi
- `frontend/src/api/roles.ts` (164 lines) — BuiltInRole, PermissionDefinition, PermissionGroup, PermissionDefinitionsResponse, RolePermissionEntry, EditableRole, CustomRoleSummary, RolesResponse, CustomRole, CreateRolePayload, rolesApi
- `frontend/src/api/stocks.ts` (138 lines) — stocksApi
- `frontend/src/api/trading.ts` (38 lines) — tradingApi
- `frontend/src/api/users.ts` (203 lines) — BuiltInRole, AdminUser, UserPayload, usersApi, UserCompanyAccess, UserCompanyAccessResponse, getUserCompanyAccess, saveUserCompanyAccess

## frontend/src/components

- `frontend/src/components/PermissionRefreshOnRouteChange.tsx` (30 lines) — PermissionRefreshOnRouteChange
- `frontend/src/components/ThemeToggle.tsx` (17 lines) — ThemeToggle
- `frontend/src/components/UserCompanyAccess.tsx` (329 lines) — UserCompanyAccess

## frontend/src/components/admin

- `frontend/src/components/admin/StatCard.tsx` (44 lines) — StatCard
- `frontend/src/components/admin/StatusBadge.tsx` (44 lines) — StatCard

## frontend/src/components/analysis

- `frontend/src/components/analysis/NewsMarketReaction.tsx` (105 lines) — NewsMarketReaction
- `frontend/src/components/analysis/NewsSentimentScatter.tsx` (254 lines) — CorrelationSummaryTable, NewsSentimentScatter
- `frontend/src/components/analysis/VolumeAnomalyChart.tsx` (66 lines) — VolumeAnomalyChart

## frontend/src/components/brokers

- `frontend/src/components/brokers/BrokerAvatar.tsx` (30 lines) — BrokerAvatar
- `frontend/src/components/brokers/BrokerBadge.tsx` (28 lines) — BrokerBadgeProps, BrokerBadge

## frontend/src/components/charts

- `frontend/src/components/charts/IndicatorPicker.tsx` (327 lines) — ActiveIndicator, PICKER_TOGGLE_ATTR, IndicatorPicker
- `frontend/src/components/charts/KlinePriceChart.tsx` (602 lines) — MinuteBar, TradingChart
- `frontend/src/components/charts/RangeBar.tsx` (40 lines) — RangeBar
- `frontend/src/components/charts/TradingChart.tsx` (590 lines) — MinuteBar, IntradayInterval, IntradayCandles, TradingChart
- `frontend/src/components/charts/chartRanges.ts` (84 lines) — RangeId, RANGE_IDS, RANGE_TITLES, rangeStart, rangeAvailable, filterRange, rangeCalendarDays, formatDay, defaultRange, unavailableReason
- `frontend/src/components/charts/customIndicators.ts` (57 lines) — paneOf
- `frontend/src/components/charts/registryIndicators.ts` (144 lines) — RegistrySeries, templateName, outputColor, toSeries, ensureRegistered

## frontend/src/components/common

- `frontend/src/components/common/Badge.tsx` (29 lines) — Badge
- `frontend/src/components/common/EmptyState.tsx` (23 lines) — EmptyState
- `frontend/src/components/common/LoadingSkeleton.tsx` (27 lines) — Skeleton, CardSkeleton, TableSkeleton
- `frontend/src/components/common/NewsImage.tsx` (20 lines) — NewsImage
- `frontend/src/components/common/PageHeader.tsx` (17 lines) — PageHeader
- `frontend/src/components/common/PermissionGate.tsx` (35 lines) — PermissionGate, Can
- `frontend/src/components/common/Sparkline.tsx` (30 lines) — Sparkline

## frontend/src/components/companies

- `frontend/src/components/companies/CompanyLogo.tsx` (35 lines) — CompanyLogo

## frontend/src/components/dashboard

- `frontend/src/components/dashboard/DashboardCard.tsx` (105 lines) — DashboardCard
- `frontend/src/components/dashboard/LatestNews.tsx` (168 lines) — LatestNews
- `frontend/src/components/dashboard/MarketOverviewChart.tsx` (129 lines) — MarketOverviewChart
- `frontend/src/components/dashboard/NewsDistribution.tsx` (63 lines) — NewsDistribution
- `frontend/src/components/dashboard/QuickActionCard.tsx` (64 lines) — QuickActionCard
- `frontend/src/components/dashboard/RoleDashboard.tsx` (195 lines) — RoleDashboard
- `frontend/src/components/dashboard/SectionCard.tsx` (27 lines) — SectionCard
- `frontend/src/components/dashboard/StatCard.tsx` (78 lines) — StatCard
- `frontend/src/components/dashboard/SummaryCard.tsx` (38 lines) — SummaryCard
- `frontend/src/components/dashboard/TopStocks.tsx` (231 lines) — TopStocks
- `frontend/src/components/dashboard/dashboardConfig.ts` (307 lines) — DashboardCardType, DashboardCardData, DashboardSectionData, DashboardConfig, universalDashboardConfig, dashboardConfigs

## frontend/src/components/landing

- `frontend/src/components/landing/HeroIllustration.tsx` (139 lines) — HeroIllustration
- `frontend/src/components/landing/LandingNews.tsx` (90 lines) — LandingNews
- `frontend/src/components/landing/ParticleWave.tsx` (64 lines) — ParticleWave

## frontend/src/components/layout

- `frontend/src/components/layout/Header.tsx` (82 lines) — Header
- `frontend/src/components/layout/Layout.tsx` (22 lines) — Layout
- `frontend/src/components/layout/MarketTicker.tsx` (50 lines) — MarketTicker
- `frontend/src/components/layout/Sidebar.tsx` (234 lines) — Sidebar

## frontend/src/components/market

- `frontend/src/components/market/BasketChart.tsx` (74 lines) — BasketChart
- `frontend/src/components/market/format.ts` (47 lines) — formatNprCompact, formatCount, formatPrice, formatPct, changeTone, formatTradeDate

## frontend/src/components/market-intelligence

- `frontend/src/components/market-intelligence/MarketBreadthWidget.tsx` (51 lines) — MarketBreadthWidget
- `frontend/src/components/market-intelligence/MarketHeatmap.tsx` (69 lines) — MarketHeatmap
- `frontend/src/components/market-intelligence/MarketRankings.tsx` (67 lines) — MarketRankings

## frontend/src/config

- `frontend/src/config/routePermissions.ts` (17 lines) — RouteRule, ROUTE_RULES

## frontend/src/contexts

- `frontend/src/contexts/AuthContext.tsx` (550 lines) — useAuth, AuthProvider

## frontend/src/hooks

- `frontend/src/hooks/useDashboardData.ts` (237 lines) — DashboardStats, resolveDataPath, useDashboardData
- `frontend/src/hooks/useLiveRefresh.ts` (8 lines) — useLiveRefresh
- `frontend/src/hooks/usePermissions.ts` (175 lines) — UserPermissions, usePermissions
- `frontend/src/hooks/useTheme.ts` (24 lines) — useTheme

## frontend/src/pages

- `frontend/src/pages/AnalystDashboard.tsx` (3 lines)
- `frontend/src/pages/BrokerAnalysisPage.tsx` (143 lines) — BrokerAnalysisPage, BrokerDetailPage
- `frontend/src/pages/CompanyAnalysisDashboard.tsx` (984 lines) — CompanyAnalysisDashboard
- `frontend/src/pages/CrawlerStatus.tsx` (407 lines) — CrawlerStatusPage
- `frontend/src/pages/Dashboard.tsx` (38 lines) — Dashboard
- `frontend/src/pages/ExportPage.tsx` (509 lines) — ExportPage
- `frontend/src/pages/ForbiddenPage.tsx` (56 lines) — ForbiddenPage
- `frontend/src/pages/LandingPage.tsx` (308 lines) — LandingPage
- `frontend/src/pages/LoginPage.tsx` (328 lines)
- `frontend/src/pages/Market.tsx` (120 lines) — MarketPage
- `frontend/src/pages/News.tsx` (323 lines) — NewsPage
- `frontend/src/pages/NewsDetail.tsx` (521 lines) — NewsDetail
- `frontend/src/pages/NotFound.tsx` (42 lines) — NotFound
- `frontend/src/pages/RegistrationPage.tsx` (390 lines)
- `frontend/src/pages/ReportsComingSoon.tsx` (22 lines) — ReportsComingSoon
- `frontend/src/pages/StockDetail.tsx` (828 lines) — StockDetail
- `frontend/src/pages/TrackedCompanies.tsx` (737 lines) — TrackedCompaniesPage
- `frontend/src/pages/TrackedMoverCards.tsx` (133 lines) — Side, MoverRow, fmt, Logo, TrackedMoverCards
- `frontend/src/pages/TrackedMoversPage.tsx` (223 lines) — TrackedMoversPage
- `frontend/src/pages/ViewerDashboard.tsx` (3 lines)
- `frontend/src/pages/WatchlistComparison.tsx` (651 lines) — WatchlistComparison
- `frontend/src/pages/MyWatchlistPage.tsx` — MyWatchlistPage (/watchlist: named lists, holdings, add any company)
- `frontend/src/pages/WatchlistPage.tsx` (135 lines) — WatchlistPage

## frontend/src/pages/admin

- `frontend/src/pages/admin/CompaniesPage.tsx` (936 lines) — CompaniesPage
- `frontend/src/pages/admin/RolesPermissionPage.tsx` (1373 lines) — RolesPermissionsPage
- `frontend/src/pages/admin/UserManagementPage.tsx` (3163 lines) — UserManagementPage
- `frontend/src/pages/admin/WatchlistPage.tsx` (146 lines) — WatchlistPage

## frontend/src/types

- `frontend/src/types/company.ts` (42 lines) — Company
- `frontend/src/types/crawl.ts` (49 lines) — CrawlStatus, CrawlType, CrawlRun
- `frontend/src/types/index.ts` (148 lines) — DailyPrice, FloorsheetTransaction, SentimentLabel, CompanyTag, CategorizationCorrection, NewsArticle, NewsStats, UserRole, User, PaginatedResponse, AdminDashboard, AnalystDashboard, ViewerDashboard, DashboardSummary
