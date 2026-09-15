import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Clock } from 'lucide-react';
import { format } from 'date-fns';
import Badge from '../components/common/Badge';
import EmptyState from '../components/common/EmptyState';
import { newsApi } from '../api/news';
import type { NewsArticle } from '../types';
import type { SentimentLabel } from '../types';

function SentimentBadge({ label }: { label: SentimentLabel }) {
  if (!label) return null;
  const m = { positive:'green', negative:'red', neutral:'gray' } as const;
  return <Badge variant={m[label]}>{label}</Badge>;
}

export default function NewsDetail() {
  const { id }    = useParams<{ id: string }>();
  const navigate  = useNavigate();
  const [article, setArticle] = useState<NewsArticle | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    newsApi.getNewsById(Number(id))
      .then(setArticle)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="text-text-secondary">Loading article...</p>;
  if (!article) return <EmptyState title="Article not found" />;

  return (
    <div className="max-w-3xl space-y-5">
      <button onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors">
        <ArrowLeft size={14}/> Back to News
      </button>

      <div className="card space-y-4">
        <h1 className="text-xl font-bold text-text-primary leading-snug">{article.headline}</h1>

        <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted border-b border-bg-border pb-4">
          <span className="text-accent-light font-medium">{article.source}</span>
          <span className="flex items-center gap-1">
            <Clock size={11}/>
            {format(new Date(article.published_at), 'MMM d, yyyy · h:mm a')}
          </span>
          <a href={article.url} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1 text-accent-light hover:underline ml-auto">
            <ExternalLink size={11}/> Source
          </a>
        </div>

        <div className="flex flex-wrap gap-2">
          {article.company_tags.map(t => (
            <Badge key={t.id} variant="purple">{t.company_symbol ?? t.symbol}</Badge>
          ))}
          <SentimentBadge label={article.sentiment_label}/>
        </div>

        <p className="text-sm text-text-secondary leading-relaxed">
          {article.body ?? 'Full article body not available.'}
        </p>

        {/* Categorization confidence */}
        {article.company_tags.length > 0 && (
          <div className="border-t border-bg-border pt-4">
            <p className="text-xs font-semibold text-text-muted mb-3 uppercase tracking-wide">
              Categorization Confidence
            </p>
            <div className="space-y-2">
              {article.company_tags.map(t => (
                <div key={t.id} className="flex items-center gap-3 text-xs">
                  <span className="w-16 font-mono font-bold text-accent-light text-[11px]">{t.company_symbol ?? t.symbol}</span>
                  <div className="flex-1 h-1.5 bg-bg-elevated rounded-full overflow-hidden">
                    <div className="h-full bg-accent rounded-full" style={{width:`${t.confidence*100}%`}}/>
                  </div>
                  <span className="text-text-muted w-8 text-right">{(t.confidence*100).toFixed(0)}%</span>
                  <Badge variant={t.is_manual ? 'yellow' : 'gray'} size="xs">
                    {t.is_manual ? 'manual' : t.method}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
