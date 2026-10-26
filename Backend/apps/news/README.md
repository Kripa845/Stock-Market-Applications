# news

Crawled news articles, categorization and sentiment.

| Where | What |
|---|---|
| `models.py` | RawArticle, NewsArticle, ArticleCompanyTag, CategorizationCorrection |
| `api/` | /api/news/ |
| `services/` | categorizer and its classifiers, keyword_matcher, sentiment, article_images |
| `management/commands/` | categorize_news, backfill_news_images, repair_news_dates |

Tests: `tests/`. Layout and the page map: `Backend/docs/architecture.md`.
