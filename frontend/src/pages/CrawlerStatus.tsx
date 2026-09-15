import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CalendarClock, CheckCircle, Clock3, Eye, Loader, Play, RefreshCw, RotateCcw, StopCircle, XCircle } from 'lucide-react';
import { format } from 'date-fns';
import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import { cancelCrawl, getCrawlRuns, retryCrawl, triggerCrawl } from '../api/crawler';
import type { CrawlRun, CrawlStatus, CrawlType } from '../types/crawl';

const manualCrawls: { type: CrawlType; label: string; description: string }[] = [
  { type: 'news', label: 'News crawl', description: 'Collect and categorize configured news sources.' },
  { type: 'trading', label: 'Trading crawl', description: 'Collect daily OHLCV and turnover data.' },
  { type: 'floorsheet', label: 'Floorsheet crawl', description: 'Collect the latest broker transactions.' },
  { type: 'all', label: 'Full crawl', description: 'Run news, trading, and floorsheet crawlers.' },
];

const schedules = [
  { label: 'News sources', timing: 'Every 5 minutes', task: 'crawl_all_news' },
  { label: 'Daily prices', timing: 'Every day at 18:00', task: 'crawl_daily_prices' },
  { label: 'Floorsheet', timing: 'Every day at 18:15', task: 'crawl_floorsheet' },
];

function StatusIcon({ status }: { status: CrawlStatus }) {
  if (status === 'success') return <CheckCircle size={15} className="text-up" />;
  if (status === 'failed') return <XCircle size={15} className="text-down" />;
  if (status === 'running') return <Loader size={15} className="animate-spin text-accent-light" />;
  if (status === 'cancelled') return <StopCircle size={15} className="text-yellow-400" />;
  return <Clock3 size={15} className="text-text-muted" />;
}

function StatusBadge({ status }: { status: CrawlStatus }) {
  const variants = { success: 'green', failed: 'red', running: 'purple', pending: 'gray', cancelled: 'yellow' } as const;
  return <Badge variant={variants[status]}>{status}</Badge>;
}

function dateLabel(value: string | null) {
  return value ? format(new Date(value), 'MMM d, yyyy, h:mm a') : 'Not started';
}

function sourceLabel(source: string) {
  const labels: Record<string, string> = {
    trading_data: 'Trading Data',
    floorsheet: 'Floorsheet',
    sharesansar: 'ShareSansar',
    arthakhabar: 'Arthakhabar',
    fiscalnepal: 'Fiscal Nepal',
    merolagani: 'MeroLagani',
    nepsealpha: 'NepseAlpha',
    bizmandu: 'Bizmandu',
  };
  return labels[source] || source;
}

export default function CrawlerStatusPage() {
  const [runs, setRuns] = useState<CrawlRun[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [busy, setBusy] = useState<CrawlType | number | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const loadRuns = useCallback(() => {
    getCrawlRuns()
      .then(data => { setRuns(data.results); setSelectedId(current => current ?? data.results[0]?.id ?? null); })
      .catch(() => setError('Unable to load crawl run history.'));
  }, []);

  useEffect(() => { loadRuns(); }, [loadRuns]);
  useEffect(() => {
    const active = runs.some(run => run.status === 'running' || run.status === 'pending');
    if (!active) return;
    const timer = window.setInterval(loadRuns, 2500);
    return () => window.clearInterval(timer);
  }, [runs, loadRuns]);

  const startCrawl = async (type: CrawlType) => {
    setBusy(type); setError(''); setNotice('');
    try {
      const response = await triggerCrawl({ crawl_type: type });
      const created = response.crawl_run as CrawlRun;
      setRuns(current => [created, ...current]);
      setSelectedId(created.id);
      setNotice('Crawl queued successfully.');
    } catch { setError('Unable to start crawl. Check Redis, Celery, and admin permissions.'); }
    finally { setBusy(null); }
  };

  const updateRun = async (run: CrawlRun, action: 'cancel' | 'retry') => {
    setBusy(run.id); setError(''); setNotice('');
    try {
      const response = action === 'cancel' ? await cancelCrawl(run.id) : await retryCrawl(run.id);
      const updated = (response.crawl_run ?? response) as CrawlRun;
      setRuns(current => current.map(item => item.id === updated.id ? updated : item));
      setNotice(action === 'cancel' ? 'Crawl cancelled.' : 'Crawl retry queued.');
    } catch { setError(`Unable to ${action} this crawl run.`); }
    finally { setBusy(null); }
  };

  const selected = runs.find(run => run.id === selectedId) ?? null;
  const activeCount = runs.filter(run => run.status === 'running' || run.status === 'pending').length;
  const successCount = runs.filter(run => run.status === 'success').length;
  const failedCount = runs.filter(run => run.status === 'failed').length;

  return <div className="space-y-6">
    <PageHeader title="Crawl Management" subtitle="Schedule, run, and monitor data collection pipelines." actions={<button onClick={loadRuns} className="btn-ghost flex items-center gap-2"><RefreshCw size={14} />Refresh</button>} />
    {(error || notice) && <div className={`flex items-center gap-2 text-sm ${error ? 'text-down' : 'text-up'}`}><AlertTriangle size={14} />{error || notice}</div>}

    <section className="space-y-3"><div className="flex items-center gap-2"><CalendarClock size={17} className="text-accent-light" /><h2 className="text-base font-semibold text-text-primary">Scheduled crawls</h2></div><div className="grid grid-cols-1 md:grid-cols-3 gap-4">{schedules.map(schedule => <div key={schedule.task} className="card"><div className="flex items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-text-primary">{schedule.label}</h3><p className="mt-1 text-xs text-text-secondary">{schedule.timing}</p></div><Badge variant="green">Enabled</Badge></div></div>)}</div></section>

    <section className="space-y-3"><div className="flex items-center gap-2"><Play size={17} className="text-accent-light" /><h2 className="text-base font-semibold text-text-primary">Manual crawls</h2></div><div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">{manualCrawls.map(crawl => <div key={crawl.type} className="card"><h3 className="text-sm font-semibold text-text-primary">{crawl.label}</h3><p className="mt-2 min-h-10 text-xs leading-relaxed text-text-secondary">{crawl.description}</p><button onClick={() => startCrawl(crawl.type)} disabled={busy !== null} className="btn-primary mt-4 flex w-full items-center justify-center gap-2"><Play size={13} />{busy === crawl.type ? 'Starting...' : 'Start crawl'}</button></div>)}</div></section>

    <section className="grid grid-cols-3 gap-3"><div className="card"><p className="text-xs text-text-muted">Active</p><p className="mt-1 text-xl font-semibold text-accent-light">{activeCount}</p></div><div className="card"><p className="text-xs text-text-muted">Successful</p><p className="mt-1 text-xl font-semibold text-up">{successCount}</p></div><div className="card"><p className="text-xs text-text-muted">Failed</p><p className="mt-1 text-xl font-semibold text-down">{failedCount}</p></div></section>

    <section className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,1fr)] gap-4">
      <div className="card overflow-x-auto"><div className="mb-4 flex items-center justify-between"><h2 className="text-base font-semibold text-text-primary">Crawl run history</h2><span className="text-xs text-text-muted">{runs.length} runs</span></div><table className="w-full min-w-[780px] text-xs"><thead><tr className="border-b border-bg-border text-text-muted"><th className="py-2 text-left font-medium">Run</th><th className="py-2 text-left font-medium">Type</th><th className="py-2 text-left font-medium">Status</th><th className="py-2 text-left font-medium">Started</th><th className="py-2 text-right font-medium">Duration</th><th className="py-2 text-right font-medium">Actions</th></tr></thead><tbody>{runs.map(run => <tr key={run.id} onClick={() => setSelectedId(run.id)} className={`table-row cursor-pointer ${run.id === selectedId ? 'bg-accent/5' : ''}`}><td className="py-3 font-mono text-text-muted">#{run.id}</td><td className="py-3 text-accent-light">{run.crawl_type}</td><td className="py-3"><span className="flex items-center gap-1.5"><StatusIcon status={run.status} /><StatusBadge status={run.status} /></span></td><td className="py-3 text-text-secondary">{dateLabel(run.started_at)}</td><td className="py-3 text-right font-mono text-text-muted">{run.duration_seconds ? `${run.duration_seconds}s` : '—'}</td><td className="py-3"><div className="flex justify-end items-center gap-2"><button onClick={(event) => { event.stopPropagation(); setSelectedId(run.id); }} className="text-accent-light" title="View crawl details"><Eye size={14} /></button>{(run.status === 'pending' || run.status === 'running') && <button onClick={(event) => { event.stopPropagation(); updateRun(run, 'cancel'); }} disabled={busy !== null} className="flex items-center gap-1 text-down hover:text-red-300 disabled:opacity-50" title="Stop crawling"><StopCircle size={14} />Stop</button>}</div></td></tr>)}</tbody></table>{runs.length === 0 && <p className="py-8 text-center text-sm text-text-muted">No crawl runs yet.</p>}</div>

      <div className="card"><div className="flex items-center justify-between gap-3"><div><h2 className="text-base font-semibold text-text-primary">Crawl details</h2><p className="text-xs text-text-muted">Monitoring selected run</p></div>{selected && <StatusBadge status={selected.status} />}</div>{selected ? <div className="mt-4 space-y-4 text-xs"><div className="grid grid-cols-2 gap-2"><div className="bg-bg-elevated rounded-lg p-3"><p className="text-text-muted">Run</p><p className="mt-1 font-mono text-text-primary">#{selected.id}</p></div><div className="bg-bg-elevated rounded-lg p-3"><p className="text-text-muted">Task ID</p><p className="mt-1 truncate font-mono text-text-primary">{selected.task_id || '—'}</p></div><div className="bg-bg-elevated rounded-lg p-3"><p className="text-text-muted">Started</p><p className="mt-1 text-text-primary">{dateLabel(selected.started_at)}</p></div><div className="bg-bg-elevated rounded-lg p-3"><p className="text-text-muted">Completed</p><p className="mt-1 text-text-primary">{dateLabel(selected.completed_at)}</p></div></div><div><p className="mb-1 text-text-muted">Sources</p><p className="rounded-lg bg-bg-elevated p-3 font-mono text-text-secondary">{selected.sources.map(sourceLabel).join(', ') || '—'}</p></div><div className="grid grid-cols-3 gap-2"><div><p className="text-text-muted">Articles</p><p className="mt-1 font-mono text-text-primary">{selected.articles_created}/{selected.articles_found}</p></div><div><p className="text-text-muted">Prices</p><p className="mt-1 font-mono text-text-primary">{selected.prices_created}/{selected.prices_found}</p></div><div><p className="text-text-muted">Floorsheet</p><p className="mt-1 font-mono text-text-primary">{selected.floorsheet_created}/{selected.floorsheet_found}</p></div></div>{selected.errors.length > 0 && <div className="rounded-lg border border-down/30 bg-down/5 p-3 text-down">{selected.errors.join(' ')}</div>}<div><p className="mb-1 text-text-muted">Logs</p><pre className="max-h-36 overflow-auto whitespace-pre-wrap rounded-lg bg-bg-elevated p-3 font-mono text-[11px] text-text-secondary">{selected.logs || 'No logs recorded yet.'}</pre></div><div className="flex gap-2">{(selected.status === 'pending' || selected.status === 'running') && <button onClick={() => updateRun(selected, 'cancel')} disabled={busy !== null} className="btn-ghost flex items-center gap-2 text-down"><StopCircle size={14} />{busy === selected.id ? 'Cancelling...' : 'Cancel'}</button>}{(selected.status === 'failed' || selected.status === 'cancelled') && <button onClick={() => updateRun(selected, 'retry')} disabled={busy !== null} className="btn-primary flex items-center gap-2"><RotateCcw size={14} />{busy === selected.id ? 'Retrying...' : 'Retry crawl'}</button>}</div></div> : <p className="mt-8 text-sm text-text-muted">Select a run to inspect its status, counters, logs, and controls.</p>}</div>
    </section>
  </div>;
}
