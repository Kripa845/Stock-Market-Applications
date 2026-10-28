# News categorization

Every crawled article is tagged with the tracked companies it is about. An article can get several tags (multi-label) or none.

Code: `Backend/apps/news/services/categorization.py` (scoring, thresholds), `keyword_matcher.py` / `confidence.py` (lexical matching), `corrections.py` (manual tags). Celery: `news.tasks.categorize_unprocessed_news_task` every 10 minutes.

## Scoring

Each tracked company is scored independently against the article:

```
confidence = 0.60 × embedding cosine + 0.40 × lexical score
```

* **Embedding:** `sentence-transformers` `all-MiniLM-L6-v2` (384-dim, CPU). Article vs. a cached company profile, cosine clipped to [0, 1]. With ~20 companies an exact NumPy comparison is sub-millisecond, so there is no vector database.
* **Lexical:** ticker (`NABIL`), canonical name, and `Company.aliases`, matched with word-boundary regex `(?<!\w)term(?!\w)`. The evidence type also sets a floor on the stored confidence: symbol 0.95, company name 0.93, alias 0.85, body mention 0.70, semantic-only 0.65 (`MATCH_STRENGTH`).
* The score is a ranking heuristic, **not** a calibrated probability.

## Thresholds (settings / env)

| Setting | Default | Meaning |
| :--- | :--- | :--- |
| `CATEGORIZATION_EMBEDDING_WEIGHT` / `CATEGORIZATION_KEYWORD_WEIGHT` | 0.60 / 0.40 | Hybrid weights (sum to 1) |
| `CATEGORIZATION_THRESHOLD` | 0.65 | Tag when confidence ≥ this |
| `CATEGORIZATION_SEMANTIC_ONLY_THRESHOLD` | 0.75 | With no lexical evidence, cosine must clear this. Higher on purpose, so a generic "market closes higher" article doesn't tag every company |
| `CATEGORIZATION_SEMANTIC_REVIEW_FLOOR` | 0.60 | Semantic-only matches between this and the threshold above go to review instead of being tagged or dropped |

The news list's `?needs_review=true` filter returns articles with no tags or a tag below 0.65.

## Manual corrections

Analysts and admins add, update or remove tags via `POST /api/news/:id/recategorize/` (permission `correct_categories`, plus company access to the target company) or the News page.

* Manual tags are stored with `is_manual=True` and are **never** overwritten or removed by automatic runs.
* Every manual change writes a `CategorizationCorrection` row: article, company, action (`add` / `remove` / `update`), previous and new confidence and method, mandatory `reason`, `corrected_by`, `corrected_at`.

## Not implemented

`embedding_classifier.py`, `llm_classifier.py` and `ner_classifier.py` in `apps/news/services/` are empty placeholders.

## Tests

Tests stub the model with `FakeEmbeddingModel` (`apps/news/tests/test_news_api.py`), because Windows Smart App Control blocks loading the real one locally.

```powershell
cd Backend
venv\Scripts\python.exe -m pytest apps/news
```
