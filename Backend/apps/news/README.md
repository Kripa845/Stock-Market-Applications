# news

Crawled news articles, categorization and sentiment.

| Where | What |
|---|---|
| `models.py` | NewsSource, RawArticle, NewsArticle, ArticleCompanyTag, CategorizationCorrection, ArticleLike, ArticleComment |
| `api/` | /api/news/ |
| `services/` | `ingest` (the only write path for articles), `normalize` (URL/title/hash rules), `dedupe`, categorizer and its classifiers, keyword_matcher, sentiment, article_images |
| `management/commands/` | dedupe_news, categorize_news, backfill_news_images, repair_news_dates |
| `sql/verify_news_integrity.sql` | read-only checks: duplicates per source, articles missing provenance, last ingest per source |

Tests: `tests/` (`test_ingest.py` covers provenance and de-duplication). Layout and the page map: `ARCHITECTURE.md` (repo root).

## Provenance and duplicates

Every article has a `news_source` (PROTECT FK), the exact `url` it was taken from, the `ingest_run` (CrawlRun) that inserted it, and its raw HTML in `RawArticle`. `services/ingest.py::ingest_article(source_id, raw_item, ingest_run_id=...)` is the single write path; the Scrapy `NewsPipeline` calls it.

| Case | Rule | Result |
|---|---|---|
| Same source, same `external_id`, or same `normalized_url` | unique constraints in the DB | existing row: `last_seen_at` touched, changed title/body/image rewritten → `updated`, else `duplicate` |
| Same source, identical text under a new URL | `content_hash` | not inserted → `duplicate` |
| Other source, identical text, or same canonical title within 3 days | `content_hash` / `canonical_hash` | inserted, `duplicate_of` = the story's first article → `inserted` |
| Same source, same title only | none | separate articles: portals reuse headlines ("सुनचाँदीको मूल्य बढ्यो") on different days |

`normalized_url` lowercases the host, drops `www.`, `utm_*`/`fbclid`/…, the fragment and a trailing slash, but keeps path case and real query params (MeroLagani's `NewsDetail.aspx?newsID=…`). `canonical_hash` is empty for titles under 12 characters. Changing anything in `services/normalize.py` changes article identity: existing rows keep their old values until re-hashed.

`created_at` is the first-seen time; timestamps are stored in UTC and shown in NPT by the frontend.

Old data: `manage.py dedupe_news` (dry run) / `--apply` merges same-source duplicates into one row (company tags, manual ones winning, corrections, likes and comments move over) and links cross-source copies. It never merges across sources.

## Adding a news source

1. **Create the `NewsSource` row.** Its `slug` (kebab-case, e.g. `nepali-paisa`) is also the frontend's `?source=` id, so add the same entry to `frontend/src/config/newsSources.ts`. For a source every environment needs, write a data migration like `migrations/0010_backfill_news_sources.py` (`get_or_create` on the slug); for a local try-out the Django admin is enough.
2. **Write the spider** in `Backend/crawlers/crawlers/spiders/` (subclass `base_news.py` where it fits). Set `source = SOURCE = "<NewsSource.name>"`. The label is matched ignoring case, spaces and hyphens, and an unknown label is logged and skipped, never saved. Each yielded `NewsItem` needs `url` (absolute), `headline`, `body` and `published_at`. Set `external_id` when the portal has its own article id, and `raw_html` / `http_status` for debugging.
3. **Schedule it:** add the spider's `name` to `NEWS_SPIDERS` in `crawlers/runner.py` and to the news set in `crawlers/pipelines.py::update_crawl_metrics`.
4. **Check it:** `..\venv\Scripts\python -m scrapy crawl <name> -s CLOSESPIDER_ITEMCOUNT=5` twice from `Backend/crawlers/`. The second run must log only `duplicate` (or `updated` for edited articles). Then run `psql -f apps/news/sql/verify_news_integrity.sql`.

A source with articles cannot be deleted; set `is_active=False` to retire it.
