import { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  Building2,
  Clock,
  ExternalLink,
  Search,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';

import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import EmptyState from '../components/common/EmptyState';
import { newsApi } from '../api/news';
import { getCompanies } from '../api/companies';
import type { Company } from '../types/company';
import type { NewsArticle, SentimentLabel } from '../types';
import { useLiveRefresh } from '../hooks/useLiveRefresh';

function Sentiment({ label }: { label: SentimentLabel }) {
  if (!label) return null;
  const positive = label === 'positive';
  return (
    <Badge variant={positive ? 'green' : label === 'negative' ? 'red' : 'gray'}>
      <span className="flex items-center gap-1">
        {positive ? <TrendingUp size={10} /> : label === 'negative' ? <TrendingDown size={10} /> : null}
        {label}
      </span>
    </Badge>
  );
}

export default function NewsPage() {
  const navigate = useNavigate();
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [search, setSearch] = useState('');
  const [sentiment, setSentiment] = useState('');
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>('');
  const [needsReviewOnly, setNeedsReviewOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Fetch companies once for filter dropdown
  useEffect(() => {
    getCompanies({ status: 'active' })
      .then((data) => setCompanies(data.results || []))
      .catch(() => {});
  }, []);

  const loadNews = useCallback(() => {
    setLoading(true);
    setError('');
    newsApi
      .getNews({
        page,
        search: search || undefined,
        sentiment: sentiment || undefined,
        company_id: selectedCompanyId ? Number(selectedCompanyId) : undefined,
        needs_review: needsReviewOnly ? true : undefined,
      })
      .then((data) => {
        setArticles(data.results);
        setCount(data.count);
      })
      .catch(() => setError('Unable to load news articles.'))
      .finally(() => setLoading(false));
  }, [search, sentiment, selectedCompanyId, needsReviewOnly, page]);

  useEffect(() => {
    loadNews();
  }, [loadNews]);
  // useLiveRefresh(loadNews);

  const groupedArticles = articles.reduce<Record<string, NewsArticle[]>>((groups, article) => {
    const portal = article.source || 'Other portals';
    groups[portal] = [...(groups[portal] ?? []), article];
    return groups;
  }, {});

  return (
    <div className="space-y-6">
      <PageHeader
        title="News Feed & Auto-Categorization"
        subtitle="Multi-label stock news categorizer with embedding similarity & entity matching"
      />

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-56">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            value={search}
            onChange={(e) => {
              setPage(1);
              setSearch(e.target.value);
            }}
            placeholder="Search headlines or body content..."
            className="w-full bg-bg-card border border-bg-border rounded-lg pl-9 pr-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          />
        </div>

        {/* Company Filter */}
        <div className="flex items-center gap-1.5 bg-bg-card border border-bg-border rounded-lg px-2.5 py-1">
          <Building2 size={13} className="text-text-muted" />
          <select
            value={selectedCompanyId}
            onChange={(e) => {
              setPage(1);
              setSelectedCompanyId(e.target.value);
            }}
            className="bg-transparent text-sm text-text-primary focus:outline-none py-1"
          >
            <option value="" className="bg-bg-card">
              All Companies
            </option>
            {companies.map((c) => (
              <option key={c.id} value={c.id} className="bg-bg-card">
                {c.symbol} — {c.name}
              </option>
            ))}
          </select>
        </div>

        {/* Sentiment Filter */}
        <select
          value={sentiment}
          onChange={(e) => {
            setPage(1);
            setSentiment(e.target.value);
          }}
          className="bg-bg-card border border-bg-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none"
        >
          <option value="" className="bg-bg-card">
            All sentiment
          </option>
          <option value="positive" className="bg-bg-card">
            Positive
          </option>
          <option value="neutral" className="bg-bg-card">
            Neutral
          </option>
          <option value="negative" className="bg-bg-card">
            Negative
          </option>
        </select>

        {/* Needs Review Toggle */}
        <button
          onClick={() => {
            setPage(1);
            setNeedsReviewOnly(!needsReviewOnly);
          }}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
            needsReviewOnly
              ? 'bg-yellow-500/20 border-yellow-500 text-yellow-400'
              : 'bg-bg-card border-bg-border text-text-secondary hover:text-text-primary'
          }`}
        >
          <AlertCircle size={13} />
          Needs Review (&lt; 65% / Unassigned)
        </button>
      </div>

      {error && (
        <div className="text-sm text-down flex items-center gap-2">
          <span>{error}</span>
          <button onClick={loadNews} className="underline">
            Retry
          </button>
        </div>
      )}

      {loading && <p className="text-text-secondary">Loading news articles...</p>}

      {!loading && !error && articles.length === 0 && (
        <EmptyState
          title="No news articles found"
          description="Try changing the search, company, or needs-review filter."
        />
      )}

      {/* Grouped Articles */}
      <div className="space-y-8">
        {Object.entries(groupedArticles).map(([portal, portalArticles]) => (
          <section key={portal} className="space-y-3">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-accent-light">{portal}</h2>
              <span className="text-xs text-text-muted">{portalArticles.length} articles</span>
              <div className="h-px flex-1 bg-bg-border" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 items-start gap-4">
              {portalArticles.map((article) => (
                <article
                  key={article.id}
                  onClick={() => navigate(`/news/${article.id}`)}
                  className="card h-fit cursor-pointer hover:border-accent/40 transition-colors space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="font-semibold leading-snug text-text-primary line-clamp-2 hover:text-accent-light transition-colors">
                      {article.headline}
                    </h3>
                    <ExternalLink size={13} className="shrink-0 text-text-muted mt-1" />
                  </div>

                  <p className="text-xs text-text-secondary line-clamp-4 leading-relaxed">
                    {article.body || 'Article content unavailable.'}
                  </p>

                  <div className="pt-2 border-t border-bg-border space-y-2.5">
                    {/* Multi-Label Company Badges with Confidence */}
                    <div className="flex flex-wrap items-center gap-1.5">
                      {article.company_tags.length === 0 ? (
                        <span className="text-[11px] text-yellow-400/90 font-medium flex items-center gap-1">
                          <AlertCircle size={11} /> Needs Review
                        </span>
                      ) : (
                        article.company_tags.map((tag) => {
                          const pct = Math.round(tag.confidence * 100);
                          return (
                            <Badge
                              key={tag.id}
                              variant={tag.is_manual ? 'yellow' : 'purple'}
                              size="xs"
                              className="font-mono"
                            >
                              {tag.company_symbol ?? tag.symbol} {pct}%
                              {tag.is_manual ? ' (M)' : ''}
                            </Badge>
                          );
                        })
                      )}
                      <Sentiment label={article.sentiment_label} />
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-text-muted">
                      <span className="flex items-center gap-1">
                        <Clock size={11} />
                        {article.published_at
                          ? format(new Date(article.published_at), 'MMM d, yyyy · h:mm a')
                          : 'Date unavailable'}
                      </span>
                      <span className="text-accent-light font-medium">{portal}</span>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>

      {/* Pagination Footer */}
      {!loading && count > 0 && (
        <div className="flex items-center justify-between text-sm text-text-secondary pt-4 border-t border-bg-border">
          <span>{count} total articles</span>
          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
              className="btn-ghost text-xs disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={articles.length === 0}
              onClick={() => setPage(page + 1)}
              className="btn-ghost text-xs disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
