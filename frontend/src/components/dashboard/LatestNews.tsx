
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, ExternalLink } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

import Badge from '../common/Badge';
import { newsApi } from '../../api/news';
import type { NewsArticle, SentimentLabel } from '../../types';

function SentimentBadge({ label }: { label: SentimentLabel }) {
  if (!label) return null;

  const map = {
    positive: 'green',
    negative: 'red',
    neutral: 'gray',
  } as const;

  return <Badge variant={map[label]}>{label}</Badge>;
}

function CompanyTag({ symbol }: { symbol: string }) {
  return <Badge variant="purple">{symbol}</Badge>;
}

export default function LatestNews() {
  const navigate = useNavigate();

  const [news, setNews] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchNews = async () => {
      try {
        setLoading(true);
        setError('');

        const response = await newsApi.getNews();

        setNews(response.results);
      } catch (err) {
        console.error('Failed to fetch latest news:', err);
        setError('Unable to load latest news.');
      } finally {
        setLoading(false);
      }
    };

    fetchNews();
  }, []);

  return (
    <div className="card flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">
          Latest Market News
        </h3>

        <button
          onClick={() => navigate('/news')}
          className="text-xs text-accent-light hover:text-accent transition-colors"
        >
          View all
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((item) => (
            <div
              key={item}
              className="p-3 rounded-lg bg-bg-elevated border border-bg-border animate-pulse"
            >
              <div className="h-4 bg-bg-border rounded w-3/4" />

              <div className="h-3 bg-bg-border rounded w-1/2 mt-3" />
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="p-3 rounded-lg bg-bg-elevated border border-bg-border">
          <p className="text-sm text-down">
            {error}
          </p>
        </div>
      )}

      {/* No news */}
      {!loading && !error && news.length === 0 && (
        <div className="p-3 rounded-lg bg-bg-elevated border border-bg-border">
          <p className="text-sm text-text-muted">
            No news articles available.
          </p>
        </div>
      )}

      {/* Real backend news */}
      {!loading && !error && news.length > 0 && (
        <div className="space-y-3">
          {news.slice(0, 4).map((article) => (
            <div
              key={article.id}
              onClick={() => navigate(`/news/${article.id}`)}
              className="p-3 rounded-lg bg-bg-elevated border border-bg-border hover:border-accent/30 cursor-pointer transition-all group"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium text-text-primary group-hover:text-accent-light transition-colors leading-snug line-clamp-2">
                  {article.headline}
                </p>

                <ExternalLink
                  size={12}
                  className="text-text-muted shrink-0 mt-0.5"
                />
              </div>

              <div className="flex flex-wrap items-center gap-2 mt-2">

                {/* Company tags */}
                {article.company_tags?.map((tag) => (
                  <CompanyTag
                    key={tag.id}
                    symbol={tag.company_symbol ?? tag.symbol ?? ''}
                  />
                ))}

                {/* Sentiment */}
                <SentimentBadge
                  label={article.sentiment_label}
                />

                {/* Published time + source */}
                <span className="text-xs text-text-muted ml-auto flex items-center gap-1">
                  <Clock size={10} />

                  {article.published_at
                    ? formatDistanceToNow(
                        new Date(article.published_at),
                        { addSuffix: true }
                      )
                    : 'Unknown time'}

                  <span className="text-bg-border">
                    ·
                  </span>

                  {article.source}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

