import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ExternalLink,
  Clock,
  Edit3,
  PlusCircle,
  Trash2,
  RefreshCw,
  History,
  CheckCircle,
  AlertTriangle,
  Building2,
  X,
} from 'lucide-react';
import { format } from 'date-fns';
import Badge from '../components/common/Badge';
import EmptyState from '../components/common/EmptyState';
import { newsApi } from '../api/news';
import { getCompanies } from '../api/companies';
import type { Company } from '../types/company';
import type { NewsArticle, SentimentLabel, CompanyTag, CategorizationCorrection } from '../types';
import { useAuth } from '../contexts/AuthContext';

function SentimentBadge({ label }: { label: SentimentLabel }) {
  if (!label) return null;
  const m = { positive: 'green', negative: 'red', neutral: 'gray' } as const;
  return <Badge variant={m[label]}>{label}</Badge>;
}

export default function NewsDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { canCategorizeNews, canCorrectCategories } = useAuth();

  const [article, setArticle] = useState<NewsArticle | null>(null);
  const [corrections, setCorrections] = useState<CategorizationCorrection[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Correction Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalAction, setModalAction] = useState<'add' | 'update' | 'remove'>('add');
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | ''>('');
  const [confidenceInput, setConfidenceInput] = useState<number>(0.95);
  const [reasonInput, setReasonInput] = useState<string>('');
  const [modalError, setModalError] = useState<string>('');

  // Check if user can categorize news (admin, analyst, or has permission)
  const canCategorize = canCategorizeNews || canCorrectCategories;

  const loadData = () => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      newsApi.getNewsById(Number(id)),
      newsApi.getCorrections({ article_id: Number(id) }).catch(() => ({ results: [] })),
      getCompanies({ status: 'active' }).catch(() => ({ results: [] })),
    ])
      .then(([artData, corrData, compData]) => {
        setArticle(artData);
        setCorrections(corrData.results || []);
        setCompanies(compData.results || []);
      })
      .catch(() => {
        setToastMessage({ type: 'error', text: 'Failed to load article details.' });
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, [id]);

  const showToast = (type: 'success' | 'error', text: string) => {
    setToastMessage({ type, text });
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleOpenAddModal = () => {
    setModalAction('add');
    setSelectedCompanyId(companies[0]?.id || '');
    setConfidenceInput(0.95);
    setReasonInput('');
    setModalError('');
    setIsModalOpen(true);
  };

  const handleOpenUpdateModal = (tag: CompanyTag) => {
    setModalAction('update');
    setSelectedCompanyId(tag.company);
    setConfidenceInput(tag.confidence);
    setReasonInput('');
    setModalError('');
    setIsModalOpen(true);
  };

  const handleOpenRemoveModal = (tag: CompanyTag) => {
    setModalAction('remove');
    setSelectedCompanyId(tag.company);
    setConfidenceInput(0);
    setReasonInput('');
    setModalError('');
    setIsModalOpen(true);
  };

  const handleSubmitCorrection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!article || !selectedCompanyId) return;

    if (!reasonInput.trim()) {
      setModalError('Please provide a reason for the categorization correction audit log.');
      return;
    }

    setActionLoading(true);
    setModalError('');

    try {
      const response = await newsApi.recategorize(article.id, {
        company_id: Number(selectedCompanyId),
        action: modalAction,
        confidence: modalAction === 'remove' ? undefined : confidenceInput,
        reason: reasonInput.trim(),
      });

      setArticle(response.article);
      showToast('success', response.message || `Categorization updated (${modalAction}).`);
      setIsModalOpen(false);

      // Refresh audit trail
      newsApi.getCorrections({ article_id: article.id }).then((data) => {
        setCorrections(data.results || []);
      });
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.detail || 'Failed to submit correction.';
      setModalError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleTriggerCategorize = async () => {
    if (!article) return;
    setActionLoading(true);
    try {
      await newsApi.triggerCategorize(article.id);
      showToast('success', 'Categorization background task dispatched via Celery.');
      setTimeout(loadData, 2000);
    } catch (err: any) {
      showToast('error', 'Could not dispatch categorization task.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl space-y-4 py-8">
        <p className="text-text-secondary">Loading article & categorization signals...</p>
      </div>
    );
  }

  if (!article) return <EmptyState title="Article not found" />;

  return (
    <div className="max-w-4xl space-y-6 pb-12">
      {/* Toast Alert */}
      {toastMessage && (
        <div
          className={`flex items-center gap-2 p-3 rounded-lg text-sm border ${
            toastMessage.type === 'success'
              ? 'bg-green-500/10 border-green-500/30 text-up'
              : 'bg-red-500/10 border-red-500/30 text-down'
          }`}
        >
          {toastMessage.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          <span>{toastMessage.text}</span>
        </div>
      )}

      {/* Navigation Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft size={14} /> Back to News
        </button>

        {canCategorize && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleTriggerCategorize}
              disabled={actionLoading}
              className="flex items-center gap-1.5 text-xs bg-bg-elevated hover:bg-bg-border text-text-secondary hover:text-text-primary px-3 py-1.5 rounded-lg border border-bg-border transition-colors disabled:opacity-50"
              title="Run background ML categorization on this article"
            >
              <RefreshCw size={12} className={actionLoading ? 'animate-spin' : ''} />
              Re-run ML Auto-Categorization
            </button>
            <button
              onClick={handleOpenAddModal}
              className="flex items-center gap-1.5 text-xs bg-accent hover:bg-accent/90 text-white px-3 py-1.5 rounded-lg font-medium shadow-sm transition-colors"
            >
              <PlusCircle size={13} />
              Add Company Tag
            </button>
          </div>
        )}
      </div>

      {/* Main Article Card */}
      <div className="card space-y-6">
        <div className="space-y-3">
          <h1 className="text-2xl font-bold text-text-primary leading-snug">{article.headline}</h1>

          <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted border-b border-bg-border pb-4">
            <span className="text-accent-light font-medium">{article.source}</span>
            <span className="flex items-center gap-1">
              <Clock size={11} />
              {article.published_at ? format(new Date(article.published_at), 'MMM d, yyyy · h:mm a') : 'Date unavailable'}
            </span>
            <SentimentBadge label={article.sentiment_label} />
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-accent-light hover:underline ml-auto"
            >
              <ExternalLink size={11} /> View Original Source
            </a>
          </div>
        </div>

        {/* Article Body */}
        <div className="text-sm text-text-secondary leading-relaxed whitespace-pre-line">
          {article.body || 'Full article text is not available.'}
        </div>

        {/* Multi-Label Company Categorization Section */}
        <div className="border-t border-bg-border pt-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wide flex items-center gap-2">
                <Building2 size={15} className="text-accent-light" />
                Multi-Label Company Tags & Confidence
              </h2>
              <p className="text-xs text-text-muted mt-0.5">
                Heuristic score computed from semantic embeddings and deterministic entity matching.
              </p>
            </div>
            <span className="text-xs text-text-muted">
              {article.company_tags.length} {article.company_tags.length === 1 ? 'company tagged' : 'companies tagged'}
            </span>
          </div>

          {article.company_tags.length === 0 ? (
            <div className="p-4 rounded-lg bg-bg-elevated/40 border border-dashed border-bg-border text-center text-xs text-text-muted">
              <p>No company tags matched above the confidence threshold (Needs Review).</p>
              {canCategorize && (
                <button onClick={handleOpenAddModal} className="text-accent-light hover:underline font-medium mt-1">
                  Assign a company tag manually
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {article.company_tags.map((tag) => {
                const pct = Math.round(tag.confidence * 100);
                const isHigh = pct >= 80;
                const isMid = pct >= 65;

                return (
                  <div
                    key={tag.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg bg-bg-elevated/30 border border-bg-border hover:border-accent/20 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-16 font-mono font-bold text-accent-light text-sm">
                        {tag.company_symbol ?? tag.symbol}
                      </div>
                      <div className="flex flex-col">
                        <span className="text-xs font-medium text-text-primary">{tag.company_name}</span>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant={tag.is_manual ? 'yellow' : 'purple'} size="xs">
                            {tag.is_manual ? 'MANUAL CORRECTION' : tag.method.toUpperCase()}
                          </Badge>
                          {tag.is_manual && (
                            <span className="text-[10px] text-yellow-400/80 font-medium">
                              (Takes precedence over ML auto-categorizer)
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      {/* Confidence Progress Bar */}
                      <div className="flex items-center gap-2 min-w-36">
                        <div className="flex-1 h-2 bg-bg-elevated rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              isHigh ? 'bg-accent' : isMid ? 'bg-yellow-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono font-semibold text-text-primary w-10 text-right">
                          {pct}%
                        </span>
                      </div>

                      {/* Analyst Actions */}
{canCategorize && (
                        <div className="flex items-center gap-1 border-l border-bg-border pl-3">
                          <button
                            onClick={() => handleOpenUpdateModal(tag)}
                            className="p-1 text-text-muted hover:text-accent-light rounded hover:bg-bg-elevated transition-colors"
                            title="Edit Confidence / Reason"
                          >
                            <Edit3 size={13} />
                          </button>
                          <button
                            onClick={() => handleOpenRemoveModal(tag)}
                            className="p-1 text-text-muted hover:text-down rounded hover:bg-bg-elevated transition-colors"
                            title="Remove Company Tag"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Audit Trail of Corrections */}
        {corrections.length > 0 && (
          <div className="border-t border-bg-border pt-5 space-y-3">
            <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wide flex items-center gap-2">
              <History size={15} className="text-accent-light" />
              Correction Audit Trail
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="text-text-muted uppercase border-b border-bg-border">
                  <tr>
                    <th className="py-2 px-3">Action</th>
                    <th className="py-2 px-3">Company</th>
                    <th className="py-2 px-3">Prev Confidence</th>
                    <th className="py-2 px-3">Corrected By</th>
                    <th className="py-2 px-3">Reason</th>
                    <th className="py-2 px-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-bg-border">
                  {corrections.map((c) => (
                    <tr key={c.id} className="text-text-secondary hover:bg-bg-elevated/20">
                      <td className="py-2 px-3 font-semibold capitalize">
                        <span
                          className={
                            c.action === 'add'
                              ? 'text-up'
                              : c.action === 'remove'
                              ? 'text-down'
                              : 'text-yellow-400'
                          }
                        >
                          {c.action}
                        </span>
                      </td>
                      <td className="py-2 px-3 font-mono font-medium text-accent-light">
                        {c.company_symbol}
                      </td>
                      <td className="py-2 px-3 font-mono">
                        {c.previous_confidence !== null && c.previous_confidence !== undefined
                          ? `${(c.previous_confidence * 100).toFixed(0)}%`
                          : 'None'}
                      </td>
                      <td className="py-2 px-3 font-medium text-text-primary">
                        {c.corrected_by_username || 'Analyst'}
                      </td>
                      <td className="py-2 px-3 max-w-xs truncate" title={c.reason}>
                        {c.reason || '—'}
                      </td>
                      <td className="py-2 px-3 text-text-muted whitespace-nowrap">
                        {c.corrected_at ? format(new Date(c.corrected_at), 'MMM d, yyyy · HH:mm') : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Analyst Recategorization Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-bg-card border border-bg-border rounded-xl shadow-2xl max-w-md w-full p-6 space-y-5 animate-in fade-in duration-200">
            <div className="flex items-center justify-between border-b border-bg-border pb-3">
              <h3 className="font-bold text-text-primary text-base flex items-center gap-2">
                <Edit3 size={16} className="text-accent-light" />
                {modalAction === 'add'
                  ? 'Add Company Tag'
                  : modalAction === 'update'
                  ? 'Update Tag Confidence'
                  : 'Remove Company Tag'}
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-text-muted hover:text-text-primary p-1 rounded"
              >
                <X size={16} />
              </button>
            </div>

            {modalError && (
              <div className="p-2.5 rounded-lg text-xs bg-red-500/10 border border-red-500/30 text-down flex items-center gap-2">
                <AlertTriangle size={14} className="shrink-0" />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleSubmitCorrection} className="space-y-4 text-xs">
              {/* Company Selector */}
              <div>
                <label className="block text-text-secondary font-medium mb-1.5">Company</label>
                <select
                  value={selectedCompanyId}
                  disabled={modalAction !== 'add'}
                  onChange={(e) => setSelectedCompanyId(Number(e.target.value))}
                  className="w-full bg-bg-elevated border border-bg-border rounded-lg px-3 py-2 text-text-primary text-xs focus:border-accent focus:outline-none"
                >
                  <option value="" disabled>
                    Select a tracked company
                  </option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.symbol} — {c.name} ({c.sector})
                    </option>
                  ))}
                </select>
              </div>

              {/* Confidence Slider (only if not removing) */}
              {modalAction !== 'remove' && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-text-secondary font-medium">Confidence Score</label>
                    <span className="font-mono font-bold text-accent-light">
                      {(confidenceInput * 100).toFixed(0)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0.10"
                    max="1.0"
                    step="0.05"
                    value={confidenceInput}
                    onChange={(e) => setConfidenceInput(parseFloat(e.target.value))}
                    className="w-full accent-accent cursor-pointer"
                  />
                  <span className="text-[10px] text-text-muted">
                    Manual overrides will be set to source &quot;manual&quot; with 100% precedence over ML model.
                  </span>
                </div>
              )}

              {/* Mandatory Reason for Audit Log */}
              <div>
                <label className="block text-text-secondary font-medium mb-1.5">
                  Correction Reason <span className="text-down">*</span>
                </label>
                <textarea
                  required
                  rows={3}
                  value={reasonInput}
                  onChange={(e) => setReasonInput(e.target.value)}
                  placeholder="Explain why this tag is added, updated, or removed (e.g., 'Explicit mention in second paragraph of quarterly profit')."
                  className="w-full bg-bg-elevated border border-bg-border rounded-lg p-2.5 text-text-primary text-xs focus:border-accent focus:outline-none"
                />
              </div>

              {/* Modal Buttons */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-bg-border">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-3 py-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className={`px-4 py-2 rounded-lg font-medium text-white transition-colors disabled:opacity-50 ${
                    modalAction === 'remove' ? 'bg-down hover:bg-down/90' : 'bg-accent hover:bg-accent/90'
                  }`}
                >
                  {actionLoading ? 'Saving...' : modalAction === 'remove' ? 'Remove Tag' : 'Save Correction'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
