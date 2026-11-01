-- News provenance / duplicate checks (PostgreSQL). Read-only.
-- psql -d <db> -f apps/news/sql/verify_news_integrity.sql
-- Every "should be 0" query returning rows means something bypassed
-- apps/news/services/ingest.py; `manage.py dedupe_news` reports and fixes it.

-- 1. Articles per source, with duplicate signals.
SELECT s.slug,
       s.is_active,
       count(a.id)                                           AS articles,
       count(a.id) FILTER (WHERE a.duplicate_of_id IS NOT NULL) AS also_reported_elsewhere,
       count(a.id) - count(DISTINCT a.normalized_url)          AS same_url_dupes,      -- should be 0
       count(a.id) - count(DISTINCT a.content_hash)            AS identical_text_dupes -- should be 0
FROM news_newssource s
LEFT JOIN news_newsarticle a ON a.news_source_id = s.id
GROUP BY s.id
ORDER BY articles DESC;

-- 2. Same-source groups sharing a normalized URL or identical text (should be 0 rows).
SELECT news_source_id, 'normalized_url' AS kind, normalized_url AS value, count(*) AS n, array_agg(id ORDER BY id) AS ids
FROM news_newsarticle GROUP BY news_source_id, normalized_url HAVING count(*) > 1
UNION ALL
SELECT news_source_id, 'content_hash', content_hash, count(*), array_agg(id ORDER BY id)
FROM news_newsarticle GROUP BY news_source_id, content_hash HAVING count(*) > 1;

-- 3. Cross-source stories: one root, "also reported by" the others.
SELECT root.id, rs.slug AS first_reported_by, left(root.headline, 70) AS headline,
       array_agg(cs.slug || ':' || c.id ORDER BY c.published_at) AS also_reported_by
FROM news_newsarticle c
JOIN news_newsarticle root ON root.id = c.duplicate_of_id
JOIN news_newssource rs ON rs.id = root.news_source_id
JOIN news_newssource cs ON cs.id = c.news_source_id
GROUP BY root.id, rs.slug
ORDER BY root.published_at DESC
LIMIT 50;

-- 4. Articles missing source information (should be 0 rows).
SELECT a.id, a.data_provenance, a.news_source_id, a.url, a.normalized_url, a.ingest_run_id,
       CASE
         WHEN a.news_source_id IS NULL THEN 'no source'
         WHEN a.url = '' OR a.normalized_url = '' THEN 'no source URL'
         WHEN a.ingest_run_id IS NULL THEN 'no ingest run'
         WHEN r.id IS NULL THEN 'no raw article'
         WHEN a.source <> s.name THEN 'source label differs from news_source'
       END AS problem
FROM news_newsarticle a
LEFT JOIN news_newssource s ON s.id = a.news_source_id
LEFT JOIN news_rawarticle r ON r.id = a.raw_article_id
WHERE a.news_source_id IS NULL OR a.url = '' OR a.normalized_url = ''
   OR a.ingest_run_id IS NULL OR r.id IS NULL OR a.source <> s.name;

-- 5. Last ingest activity per source: last run that inserted an article, and
--    the last time any crawl saw one of its articles (re-seen rows only touch last_seen_at).
SELECT s.slug,
       last_insert.ingest_run_id AS last_inserting_run,
       cr.status                 AS run_status,
       cr.started_at             AS run_started_utc,
       cr.completed_at           AS run_completed_utc,
       cr.articles_created, cr.articles_updated, cr.articles_duplicate,
       (SELECT max(last_seen_at) FROM news_newsarticle WHERE news_source_id = s.id) AS last_seen_utc
FROM news_newssource s
LEFT JOIN LATERAL (
    SELECT ingest_run_id FROM news_newsarticle
    WHERE news_source_id = s.id AND ingest_run_id IS NOT NULL
    ORDER BY ingest_run_id DESC LIMIT 1
) last_insert ON true
LEFT JOIN crawler_runs_crawlrun cr ON cr.id = last_insert.ingest_run_id
ORDER BY s.slug;

-- 6. Recent news crawl runs and their counters.
SELECT id, source, sources, status, started_at, completed_at,
       articles_found, articles_created, articles_updated, articles_duplicate, errors
FROM crawler_runs_crawlrun
WHERE crawl_type IN ('news', 'all')
ORDER BY id DESC
LIMIT 20;

-- 7. Likes are one per user per article (should be 0 rows; enforced by a unique constraint).
SELECT article_id, user_id, count(*) FROM news_articlelike GROUP BY 1, 2 HAVING count(*) > 1;
