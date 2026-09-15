import { useCallback, useEffect, useState } from 'react';
import { Clock, ExternalLink, Search, TrendingDown, TrendingUp } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import EmptyState from '../components/common/EmptyState';
import { newsApi } from '../api/news';
import type { NewsArticle, SentimentLabel } from '../types';
import { useLiveRefresh } from '../hooks/useLiveRefresh';

function Sentiment({ label }: { label: SentimentLabel }) {
  if (!label) return null;
  const positive = label === 'positive';
  return <Badge variant={positive ? 'green' : label === 'negative' ? 'red' : 'gray'}><span className="flex items-center gap-1">{positive ? <TrendingUp size={10} /> : label === 'negative' ? <TrendingDown size={10} /> : null}{label}</span></Badge>;
}

export default function NewsPage() {
  const navigate = useNavigate();
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [search, setSearch] = useState('');
  const [sentiment, setSentiment] = useState('');
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadNews = useCallback(() => {
    setLoading(true); setError('');
    newsApi.getNews({ page, search: search || undefined, sentiment: sentiment || undefined })
      .then(data => { setArticles(data.results); setCount(data.count); })
      .catch(() => setError('Unable to load news articles.'))
      .finally(() => setLoading(false));
  }, [search, sentiment, page]);

  useEffect(() => { loadNews(); }, [loadNews]);
  useLiveRefresh(loadNews);

  const groupedArticles = articles.reduce<Record<string, NewsArticle[]>>((groups, article) => {
    const portal = article.source || 'Other portals';
    groups[portal] = [...(groups[portal] ?? []), article];
    return groups;
  }, {});

  return <div className="space-y-6">
    <PageHeader title="News Articles" subtitle="" />
    <div className="flex flex-wrap gap-3">
      <div className="relative flex-1 min-w-56">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
        <input value={search} onChange={e => { setPage(1); setSearch(e.target.value); }} placeholder="Search articles" className="w-full bg-bg-card border border-bg-border rounded-lg pl-9 pr-3 py-2 text-sm text-text-primary" />
      </div>
      <select value={sentiment} onChange={e => { setPage(1); setSentiment(e.target.value); }} className="bg-bg-card border border-bg-border rounded-lg px-3 py-2 text-sm text-text-primary">
        <option value="">All sentiment</option><option value="positive">Positive</option><option value="neutral">Neutral</option><option value="negative">Negative</option>
      </select>
    </div>
    {error && <div className="text-sm text-down">{error} <button onClick={loadNews} className="underline">Retry</button></div>}
    {loading && <p className="text-text-secondary">Loading news...</p>}
    {!loading && !error && articles.length === 0 && <EmptyState title="No news articles found" description="Try changing the search or sentiment filter." />}
    <div className="space-y-8">
      {Object.entries(groupedArticles).map(([portal, portalArticles]) => (
        <section key={portal} className="space-y-3">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-accent-light">{portal}</h2>
            <span className="text-xs text-text-muted">{portalArticles.length} articles</span>
            <div className="h-px flex-1 bg-bg-border" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 items-start gap-4">
            {portalArticles.map(article => (
              <article key={article.id} onClick={() => navigate(`/news/${article.id}`)} className="card h-fit cursor-pointer hover:border-accent/30 transition-colors">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-medium leading-snug text-text-primary line-clamp-3">{article.headline}</h3>
                  <ExternalLink size={14} className="shrink-0 text-text-muted" />
                </div>
                <p className="text-xs text-text-secondary mt-3 line-clamp-5">{article.body}</p>
                <div className="mt-4 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {article.company_tags.map(tag => <Badge key={tag.id} variant="purple">{tag.company_symbol ?? tag.symbol}</Badge>)}
                    <Sentiment label={article.sentiment_label} />
                  </div>
                  <div className="flex items-center gap-1 text-xs text-text-muted">
                    <Clock size={11} />
                    {article.published_at ? format(new Date(article.published_at), 'MMM d, yyyy, h:mm a') : 'Date unavailable'}
                    <span className="ml-auto text-accent-light">{portal}</span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
    {!loading && count > 0 && <div className="flex items-center justify-between text-sm text-text-secondary"><span>{count} articles</span><div className="flex gap-2"><button disabled={page === 1} onClick={() => setPage(page - 1)} className="btn-ghost disabled:opacity-40">Previous</button><button disabled={articles.length === 0} onClick={() => setPage(page + 1)} className="btn-ghost disabled:opacity-40">Next</button></div></div>}
  </div>;
}
