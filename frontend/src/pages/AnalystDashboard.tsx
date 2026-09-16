import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle,
  ExternalLink,
  History,
  Newspaper,
  RefreshCw,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import { newsApi } from '../api/news';
import type { CategorizationCorrection, NewsArticle, NewsStats } from '../types';
import { useAuth } from '../contexts/AuthContext';
import CompaniesPage from '../pages/admin/CompaniesPage';


const AnalystDashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [stats, setStats] = useState<NewsStats | null>(null);
  const [needsReviewArticles, setNeedsReviewArticles] = useState<NewsArticle[]>([]);
  const [recentCorrections, setRecentCorrections] = useState<CategorizationCorrection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      newsApi.getStats().catch(() => null),
      newsApi.getNews({ needs_review: true, page: 1 }).catch(() => ({ results: [] })),
      newsApi.getCorrections().catch(() => ({ results: [] })),
    ])
      .then(([statsData, reviewData, corrData]) => {
        setStats(statsData);
        setNeedsReviewArticles(reviewData.results || []);
        setRecentCorrections(corrData.results || []);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analyst Dashboard"
        subtitle={`Welcome back, ${user?.first_name || user?.username || 'Analyst'}. Review AI auto-categorization and verify company news tags.`}
        actions={
          <button
            onClick={() => {
              setLoading(true);
              Promise.all([
                newsApi.getStats().catch(() => null),
                newsApi.getNews({ needs_review: true, page: 1 }).catch(() => ({ results: [] })),
                newsApi.getCorrections().catch(() => ({ results: [] })),
              ])
                .then(([statsData, reviewData, corrData]) => {
                  setStats(statsData);
                  setNeedsReviewArticles(reviewData.results || []);
                  setRecentCorrections(corrData.results || []);
                })
                .finally(() => setLoading(false));
            }}
            className="btn-ghost flex items-center gap-2"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        }
      />

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-4 space-y-1">
          <div className="flex items-center justify-between text-text-muted">
            <span className="text-xs font-semibold uppercase tracking-wider">Total Articles</span>
            <Newspaper size={16} className="text-accent-light" />
          </div>
          <p className="text-2xl font-bold text-text-primary">
            {stats?.total_articles ?? '—'}
          </p>
          <span className="text-[11px] text-text-muted">Crawled from all news portals</span>
        </div>

        <div className="card p-4 space-y-1">
          <div className="flex items-center justify-between text-text-muted">
            <span className="text-xs font-semibold uppercase tracking-wider">Categorized (Auto/Manual)</span>
            <CheckCircle size={16} className="text-up" />
          </div>
          <p className="text-2xl font-bold text-up">
            {stats?.categorized ?? '—'}
          </p>
          <span className="text-[11px] text-text-muted">
            {stats?.multi_company_articles ? `${stats.multi_company_articles} multi-company` : 'Matched companies'}
          </span>
        </div>

        <div className="card p-4 space-y-1">
          <div className="flex items-center justify-between text-text-muted">
            <span className="text-xs font-semibold uppercase tracking-wider">Needs Review</span>
            <AlertCircle size={16} className="text-yellow-400" />
          </div>
          <p className="text-2xl font-bold text-yellow-400">
            {stats?.uncategorized ?? needsReviewArticles.length}
          </p>
          <span className="text-[11px] text-text-muted">&lt; 65% confidence or unassigned</span>
        </div>

        <div className="card p-4 space-y-1">
          <div className="flex items-center justify-between text-text-muted">
            <span className="text-xs font-semibold uppercase tracking-wider">Corrections Audited</span>
            <History size={16} className="text-accent" />
          </div>
          <p className="text-2xl font-bold text-accent-light">
            {recentCorrections.length}
          </p>
          <span className="text-[11px] text-text-muted">Analyst corrections logged</span>
        </div>
      </div>

      {/* Companies Section */}
      <div className="mt-8">
        <CompaniesPage trackedOnly={false} />
      </div>

      {/* Main Grid: Needs Review Queue & Recent Corrections Audit Trail */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Needs Review Queue */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between border-b border-bg-border pb-3">
            <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wide flex items-center gap-2">
              <AlertCircle size={16} className="text-yellow-400" />
              Articles Needing Review
            </h2>
            <button
              onClick={() => navigate('/analyst/news')}
              className="text-xs text-accent-light hover:underline font-medium"
            >
              View All News
            </button>
          </div>

          {loading ? (
            <p className="text-xs text-text-secondary py-4">Loading queue...</p>
          ) : needsReviewArticles.length === 0 ? (
            <div className="p-6 text-center text-xs text-text-muted">
              <CheckCircle size={24} className="mx-auto text-up mb-2" />
              All crawled news articles are categorized above threshold.
            </div>
          ) : (
            <div className="space-y-3">
              {needsReviewArticles.slice(0, 6).map((art) => (
                <div
                  key={art.id}
                  onClick={() => navigate(`/news/${art.id}`)}
                  className="p-3 rounded-lg bg-bg-elevated/40 border border-bg-border hover:border-accent/30 cursor-pointer transition-colors space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-xs font-semibold text-text-primary line-clamp-2 hover:text-accent-light">
                      {art.headline}
                    </h3>
                    <ExternalLink size={12} className="shrink-0 text-text-muted" />
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-text-muted pt-1 border-t border-bg-border/60">
                    <span>{art.source}</span>
                    <span className="text-yellow-400 font-medium">Click to categorize</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Audit Trail of Corrections */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between border-b border-bg-border pb-3">
            <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wide flex items-center gap-2">
              <History size={16} className="text-accent-light" />
              Recent Categorization Corrections
            </h2>
            <span className="text-xs text-text-muted">{recentCorrections.length} total</span>
          </div>

          {loading ? (
            <p className="text-xs text-text-secondary py-4">Loading audit trail...</p>
          ) : recentCorrections.length === 0 ? (
            <div className="p-6 text-center text-xs text-text-muted">
              No manual corrections recorded yet.
            </div>
          ) : (
            <div className="space-y-3">
              {recentCorrections.slice(0, 6).map((c) => (
                <div
                  key={c.id}
                  onClick={() => navigate(`/news/${c.article}`)}
                  className="p-3 rounded-lg bg-bg-elevated/40 border border-bg-border hover:border-accent/30 cursor-pointer transition-colors space-y-1.5"
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={c.action === 'add' ? 'green' : c.action === 'remove' ? 'red' : 'yellow'}
                        size="xs"
                      >
                        {c.action.toUpperCase()}
                      </Badge>
                      <span className="font-mono font-bold text-accent-light">{c.company_symbol}</span>
                    </div>
                    <span className="text-[10px] text-text-muted">
                      {c.corrected_at ? format(new Date(c.corrected_at), 'MMM d · HH:mm') : ''}
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary truncate">
                    Reason: {c.reason || '—'}
                  </p>
                  <div className="text-[10px] text-text-muted flex items-center justify-between pt-1">
                    <span>By: {c.corrected_by_username || 'Analyst'}</span>
                    <span className="text-accent-light">Article #{c.article}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* =====================================================
          QUICK ACTIONS
          ====================================================== */}

      <div
        className="
          bg-bg-secondary
          border
          border-bg-border
          rounded-xl
          p-5
        "
      >
        <div className="flex items-center gap-2 mb-1">
          <Newspaper
            size={17}
            className="text-accent-light"
          />
          <h2 className="text-base font-semibold text-text-primary">
            Quick Actions
          </h2>
        </div>

        <p className="text-sm text-text-secondary mb-5">
          Common analyst tasks for news categorization.
        </p>

        <div className="space-y-3">
          {/* Review News */}
          <button
            onClick={() => navigate('/analyst/news')}
            className="
              w-full
              flex
              items-center
              justify-between
              p-3
              rounded-lg
              border
              border-bg-border
              bg-bg-primary
              hover:border-accent-light/40
              transition-colors
            "
          >
            <span className="flex items-center gap-3">
              <span
                className="
                  w-8
                  h-8
                  rounded-lg
                  bg-purple-500/10
                  flex items-center
                  justify-center
                "
              >
                <Newspaper
                  size={16}
                  className="text-purple-400"
                />
              </span>
              <span className="text-sm font-medium text-text-primary">
                Review News
              </span>
            </span>
            <ArrowRight
              size={15}
              className="text-text-secondary"
            />
          </button>

          {/* Needs Review Queue */}
          <button
            onClick={() => navigate('/analyst/news?needs_review=true')}
            className="
              w-full
              flex
              items-center
              justify-between
              p-3
              rounded-lg
              border
              border-bg-border
              bg-bg-primary
              hover:border-yellow-500/40
              transition-colors
            "
          >
            <span className="flex items-center gap-3">
              <span
                className="
                  w-8
                  h-8
                  rounded-lg
                  bg-yellow-500/10
                  flex items-center
                  justify-center
                "
              >
                <AlertCircle
                  size={16}
                  className="text-yellow-400"
                />
              </span>
              <span className="text-sm font-medium text-text-primary">
                Needs Review Queue
              </span>
            </span>
            <ArrowRight
              size={15}
              className="text-text-secondary"
            />
          </button>

          {/* Corrections Audit Trail */}
          <button
            onClick={() => navigate('/analyst/news')}
            className="
              w-full
              flex
              items-center
              justify-between
              p-3
              rounded-lg
              border
              border-bg-border
              bg-bg-primary
              hover:border-accent-light/40
              transition-colors
            "
          >
            <span className="flex items-center gap-3">
              <span
                className="
                  w-8
                  h-8
                  rounded-lg
                  bg-accent/10
                  flex items-center
                  justify-center
                "
              >
                <History
                  size={16}
                  className="text-accent-light"
                />
              </span>
              <span className="text-sm font-medium text-text-primary">
                Corrections Audit Trail
              </span>
            </span>
            <ArrowRight
              size={15}
              className="text-text-secondary"
            />
          </button>
        </div>
      </div>

    </div>
  );
};

export default AnalystDashboard;
