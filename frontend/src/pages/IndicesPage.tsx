import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, ArrowDown, ArrowUp, CheckCircle2, ChevronDown, ChevronsUpDown, ChevronUp, Clock,
  DownloadCloud, Minus, RefreshCw, XCircle,
} from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import { changeTone, formatNprArab, formatNprCompact, formatTradeDate } from '../components/market/format';
import {
  getIndices, getSubIndices, resyncIndices, verifyIndices,
  type IndexDataStatus, type IndexRow, type IndexTable, type IndexVerification, type IndexVerificationRow,
} from '../api/marketIndices';
import { useAuth } from '../contexts/AuthContext';

// NEPSE main indices and sub-indices, as on NEPSE data sites: OHLC, change and the session's
// turnover / volume / transactions with their change vs the previous session.  Every value comes
// from IndexDaily (GET /market-indices/indices/ and sub-indices/).  Each row is also checked against
// NEPSE's own feed (GET /market-indices/verify/): Scraped, Missing or Mismatch.

type SortKey =
  | 'code' | 'open' | 'high' | 'low' | 'close' | 'ch' | 'ch_pct' | 'turnover' | 'tu_ch' | 'tu_ch_pct'
  | 'volume' | 'vol_ch' | 'vol_ch_pct' | 'transactions' | 'trans_ch' | 'trans_ch_pct' | 'status';
type StatusFilter = 'all' | 'issues' | IndexDataStatus;

/** A table row: the stored values (null when the index was never scraped) plus its check. */
interface Line {
  code: string;
  name: string;
  data: IndexRow | null;
  check: IndexVerificationRow | null;
}

const num = (value: number | string | null | undefined) => (value == null || value === '' ? null : Number(value));
const toneText = { up: 'text-up', down: 'text-down', flat: 'text-text-muted' };
const toneChip = { up: 'bg-up/10 text-up', down: 'bg-down/10 text-down', flat: 'bg-bg-elevated text-text-muted' };
const ToneArrow = { up: ArrowUp, down: ArrowDown, flat: Minus };

// Verification field -> the table column that shows it.
const FIELD_COLUMN: Record<string, SortKey> = {
  open: 'open', high: 'high', low: 'low', close: 'close', turnover: 'turnover',
  volume: 'volume', transactions: 'transactions', source_change_pct: 'ch_pct',
};
const FIELD_LABEL: Record<string, string> = {
  open: 'Open', high: 'High', low: 'Low', close: 'Close', turnover: 'Turnover', volume: 'Volume',
  transactions: 'Transactions', source_change_pct: 'Change %', previous_session: 'Previous session',
};

/** 38.8 K / 1.2 K / 742. */
const formatThousands = (value: number | string | null | undefined) => {
  const n = num(value);
  if (n === null) return '—';
  return Math.abs(n) >= 1000 ? `${(n / 1000).toFixed(1)} K` : n.toLocaleString('en-IN');
};
const signed = (value: number | string | null | undefined, format: (v: number) => string) => {
  const n = num(value);
  return n === null ? '—' : `${n > 0 ? '+' : ''}${format(n)}`;
};
const points = (value: number) => value.toLocaleString('en-IN', { maximumFractionDigits: 2 });
const plain = (value: number | string | null | undefined) => {
  const n = num(value);
  return n === null ? '—' : points(n);
};

function PctPill({ value }: { value: number | string | null }) {
  const n = num(value);
  const tone = changeTone(n);
  const Arrow = ToneArrow[tone];
  if (n === null) return <span className="text-text-muted">—</span>;
  return (
    <span className={`inline-flex min-w-[66px] items-center justify-center gap-1 rounded-full px-2 py-0.5 font-mono text-[11px] tabular-nums ${toneChip[tone]}`}>
      {tone !== 'flat' && <Arrow size={10} strokeWidth={2.5} />}{Math.abs(n).toFixed(2)}%
    </span>
  );
}

function Delta({ value, format }: { value: number | string | null; format: (v: number) => string }) {
  return <span className={toneText[changeTone(value)]}>{signed(value, format)}</span>;
}

const STATUS_STYLE: Record<IndexDataStatus, { label: string; chip: string; icon: typeof CheckCircle2 }> = {
  scraped: { label: 'Scraped', chip: 'bg-up/10 text-up border-up/25', icon: CheckCircle2 },
  missing: { label: 'Missing', chip: 'bg-down/10 text-down border-down/25', icon: XCircle },
  mismatch: { label: 'Mismatch', chip: 'bg-amber-500/10 text-amber-400 border-amber-500/30', icon: AlertTriangle },
};

function StatusBadge({ check }: { check: IndexVerificationRow | null }) {
  if (!check) return <span className="text-[11px] text-text-muted">—</span>;
  const style = STATUS_STYLE[check.status];
  const Icon = style.icon;
  const title = check.note
    ?? (check.status === 'missing' ? `Missing: ${check.missing.map((f) => FIELD_LABEL[f] ?? f).join(', ')}`
      : check.status === 'mismatch' ? `${check.mismatches.length} value(s) differ from NEPSE` : 'Stored and matches NEPSE');
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${style.chip}`}>
      <Icon size={11} />{style.label}{!check.verified && check.status === 'scraped' ? '*' : ''}
    </span>
  );
}

const COLUMNS: { key: SortKey; label: string; align?: 'left' | 'center' }[] = [
  { key: 'code', label: 'Symbol', align: 'left' },
  { key: 'open', label: 'Open' }, { key: 'high', label: 'High' }, { key: 'low', label: 'Low' },
  { key: 'close', label: 'Close' }, { key: 'ch', label: 'CH' }, { key: 'ch_pct', label: 'CH %', align: 'center' },
  { key: 'turnover', label: 'Turnover' }, { key: 'tu_ch', label: 'TU. CH' }, { key: 'tu_ch_pct', label: 'TU. CH %', align: 'center' },
  { key: 'volume', label: 'Vol.' }, { key: 'vol_ch', label: 'Vol. CH' }, { key: 'vol_ch_pct', label: 'Vol. CH %', align: 'center' },
  { key: 'transactions', label: 'Trans' }, { key: 'trans_ch', label: 'Trans. CH' }, { key: 'trans_ch_pct', label: 'Trans. CH %', align: 'center' },
  { key: 'status', label: 'Data', align: 'center' },
];
const ALIGN = { left: 'text-left', center: 'text-center', right: 'text-right' } as const;
const STATUS_ORDER: Record<IndexDataStatus, number> = { mismatch: 0, missing: 1, scraped: 2 };

function sortValue(line: Line, key: SortKey): number | string | null {
  if (key === 'code') return line.code;
  if (key === 'status') return line.check ? STATUS_ORDER[line.check.status] : null;
  return line.data ? num(line.data[key as keyof IndexRow] as number | string | null) : null;
}

function IndexTableCard({ title, lines, emptyText }: { title: string; lines: Line[]; emptyText: string }) {
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean } | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const sorted = useMemo(() => {
    if (!sort) return lines;
    const factor = sort.desc ? -1 : 1;
    return [...lines].sort((a, b) => {
      const left = sortValue(a, sort.key);
      const right = sortValue(b, sort.key);
      if (left === null) return 1;
      if (right === null) return -1;
      return (typeof left === 'string' ? left.localeCompare(String(right)) : left - Number(right)) * factor;
    });
  }, [lines, sort]);

  const toggle = (key: SortKey) =>
    setSort((current) => (current?.key !== key ? { key, desc: key !== 'code' } : current.desc === (key !== 'code') ? { key, desc: !current.desc } : null));

  return (
    <section className="card space-y-3">
      <span className="inline-block rounded-md bg-bg-elevated px-3 py-1 text-sm font-semibold text-text-primary">{title}</span>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1320px] text-xs">
          <thead>
            <tr className="border-b border-bg-border text-[11px] uppercase text-text-secondary">
              {COLUMNS.map((column) => {
                const active = sort?.key === column.key;
                const Icon = !active ? ChevronsUpDown : sort?.desc ? ChevronDown : ChevronUp;
                return (
                  <th key={column.key} className={`whitespace-nowrap px-2 py-2.5 font-semibold first:pl-1 ${ALIGN[column.align ?? 'right']}`}>
                    <button type="button" onClick={() => toggle(column.key)} className={`inline-flex items-center gap-0.5 uppercase hover:text-text-primary ${active ? 'text-text-primary' : ''}`}>
                      {column.label}<Icon size={11} className={active ? '' : 'opacity-50'} />
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((line) => {
              const row = line.data;
              const check = line.check;
              const differs = new Set((check?.mismatches ?? []).map((m) => FIELD_COLUMN[m.field]));
              const empty = new Set((check?.missing ?? []).map((f) => FIELD_COLUMN[f]));
              const cell = (key: SortKey, extra = '') => {
                const flag = differs.has(key) ? 'bg-amber-500/10 ring-1 ring-inset ring-amber-500/40 rounded' : empty.has(key) ? 'bg-down/5' : '';
                return `whitespace-nowrap px-2 py-2.5 text-right font-mono tabular-nums ${flag} ${extra}`;
              };
              const mismatchTitle = (key: SortKey) => {
                const m = check?.mismatches.find((item) => FIELD_COLUMN[item.field] === key);
                return m ? `Stored ${plain(m.stored)} · NEPSE now ${plain(m.source)}` : undefined;
              };
              const expandable = Boolean(check && (check.mismatches.length || check.missing.length));
              return (
                <Fragment key={line.code}>
                  <tr className="border-b border-bg-border/70 last:border-0 hover:bg-blue-500/[0.06]">
                    <td className="py-2 pl-1 pr-2">
                      <div className="flex items-center gap-2.5">
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-900 text-[11px] font-bold text-white">
                          {line.code.charAt(0)}
                        </span>
                        <span className="leading-tight">
                          <span className="block font-semibold uppercase text-sky-400">{line.code.replace(/_/g, ' ')}</span>
                          <span className="block text-[10px] text-text-muted">{line.name}</span>
                        </span>
                      </div>
                    </td>
                    <td className={cell('open')} title={mismatchTitle('open')}>{plain(row?.open)}</td>
                    <td className={cell('high')} title={mismatchTitle('high')}>{plain(row?.high)}</td>
                    <td className={cell('low')} title={mismatchTitle('low')}>{plain(row?.low)}</td>
                    <td className={cell('close', 'font-semibold text-text-primary')} title={mismatchTitle('close')}>{plain(row?.close)}</td>
                    <td className={cell('ch')}><Delta value={row?.ch ?? null} format={points} /></td>
                    <td className={cell('ch_pct', 'text-center')} title={mismatchTitle('ch_pct')}><PctPill value={row?.ch_pct ?? null} /></td>
                    <td className={cell('turnover')} title={mismatchTitle('turnover')}>
                      {formatNprArab(row?.turnover)}
                      {num(row?.turnover_share_pct) !== null && (
                        <span className="ml-1 text-[10px] text-text-muted">({num(row?.turnover_share_pct)!.toFixed(2)}%)</span>
                      )}
                    </td>
                    <td className={cell('tu_ch')}><Delta value={row?.tu_ch ?? null} format={(v) => formatNprCompact(v)} /></td>
                    <td className={cell('tu_ch_pct', 'text-center')}><PctPill value={row?.tu_ch_pct ?? null} /></td>
                    <td className={cell('volume')} title={mismatchTitle('volume')}>{formatNprCompact(row?.volume)}</td>
                    <td className={cell('vol_ch')}><Delta value={row?.vol_ch ?? null} format={(v) => formatNprCompact(v)} /></td>
                    <td className={cell('vol_ch_pct', 'text-center')}><PctPill value={row?.vol_ch_pct ?? null} /></td>
                    <td className={cell('transactions')} title={mismatchTitle('transactions')}>{formatThousands(row?.transactions)}</td>
                    <td className={cell('trans_ch')}><Delta value={row?.trans_ch ?? null} format={(v) => v.toLocaleString('en-IN')} /></td>
                    <td className={cell('trans_ch_pct', 'text-center')}><PctPill value={row?.trans_ch_pct ?? null} /></td>
                    <td className="whitespace-nowrap px-2 py-2.5 text-center">
                      <button
                        type="button"
                        disabled={!expandable}
                        onClick={() => setOpen((current) => ({ ...current, [line.code]: !current[line.code] }))}
                        className="inline-flex items-center gap-1 disabled:cursor-default"
                        aria-expanded={expandable ? Boolean(open[line.code]) : undefined}
                      >
                        <StatusBadge check={check} />
                        {expandable && <ChevronDown size={12} className={`text-text-muted transition-transform ${open[line.code] ? 'rotate-180' : ''}`} />}
                      </button>
                    </td>
                  </tr>
                  {expandable && open[line.code] && check && (
                    <tr className="border-b border-bg-border/70 bg-bg-elevated/50">
                      <td colSpan={COLUMNS.length} className="px-4 py-2.5">
                        <div className="flex flex-wrap gap-x-6 gap-y-1.5 text-[11px]">
                          {check.mismatches.map((m) => (
                            <span key={m.field} className="font-mono">
                              <span className="font-sans font-semibold text-amber-400">{FIELD_LABEL[m.field] ?? m.field}:</span>{' '}
                              stored <span className="text-text-primary">{plain(m.stored)}</span>
                              {' · '}NEPSE <span className="text-text-primary">{plain(m.source)}</span>
                              {' '}<span className="text-text-muted">(Δ {signed(Number(m.source) - Number(m.stored), points)})</span>
                            </span>
                          ))}
                          {check.missing.length > 0 && (
                            <span>
                              <span className="font-semibold text-down">Missing:</span>{' '}
                              <span className="text-text-secondary">{check.missing.map((f) => FIELD_LABEL[f] ?? f).join(', ')}</span>
                              {check.missing.includes('previous_session') && (
                                <span className="text-text-muted"> (change columns need the previous session)</span>
                              )}
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {sorted.length === 0 && <p className="py-8 text-center text-sm text-text-muted">{emptyText}</p>}
      </div>
    </section>
  );
}

const FILTERS: { id: StatusFilter; label: string }[] = [
  { id: 'all', label: 'All rows' },
  { id: 'issues', label: 'Missing & mismatch' },
  { id: 'missing', label: 'Missing' },
  { id: 'mismatch', label: 'Mismatch' },
];

function buildLines(table: IndexTable | null, checks: IndexVerificationRow[], kind: 'main' | 'sub'): Line[] {
  const data = new Map((table?.rows ?? []).map((row) => [row.code, row]));
  const ofKind = checks.filter((check) => check.kind === kind);
  // Catalogue order from the check, so never-scraped indices still get a (Missing) row.
  if (ofKind.length) {
    return ofKind.map((check) => ({ code: check.code, name: data.get(check.code)?.name ?? check.name, data: data.get(check.code) ?? null, check }));
  }
  return (table?.rows ?? []).map((row) => ({ code: row.code, name: row.name, data: row, check: null }));
}

const formatDateTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';

export default function IndicesPage() {
  const { hasPermission } = useAuth();
  const canResync = hasPermission('run_crawler');
  const [main, setMain] = useState<IndexTable | null>(null);
  const [sub, setSub] = useState<IndexTable | null>(null);
  const [check, setCheck] = useState<IndexVerification | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [filter, setFilter] = useState<StatusFilter>('all');

  const load = useCallback(async () => {
    setLoading(true);
    setChecking(true);
    setError('');
    try {
      const [indices, subIndices] = await Promise.all([getIndices(), getSubIndices()]);
      setMain(indices);
      setSub(subIndices);
    } catch {
      setError('Unable to load index data.');
    } finally {
      setLoading(false);
    }
    try {
      setCheck(await verifyIndices());
    } catch {
      setCheck(null);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const resync = async () => {
    setSyncing(true);
    setNotice('');
    setError('');
    try {
      const result = await resyncIndices();
      setCheck(result);
      const [indices, subIndices] = await Promise.all([getIndices(), getSubIndices()]);
      setMain(indices);
      setSub(subIndices);
      setNotice(`Re-scraped from NEPSE: ${result.sync?.saved ?? 0} index rows saved (no duplicates).`);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? 'Re-sync failed.');
    } finally {
      setSyncing(false);
    }
  };

  const checks = check?.rows ?? [];
  const keep = (line: Line) => {
    if (filter === 'all') return true;
    const status = line.check?.status;
    return filter === 'issues' ? status === 'missing' || status === 'mismatch' : status === filter;
  };
  const mainLines = buildLines(main, checks, 'main').filter(keep);
  const subLines = buildLines(sub, checks, 'sub').filter(keep);
  const summary = check?.summary ?? {};
  const session = check?.session ?? main?.as_of ?? sub?.as_of ?? null;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Indices"
        subtitle="NEPSE main and sub-indices for the latest stored session, with a check of every row against NEPSE's own feed."
        actions={(
          <>
            <button onClick={load} className="btn-ghost flex items-center gap-2" disabled={loading || checking}>
              <RefreshCw size={14} className={loading || checking ? 'animate-spin' : ''} />Refresh
            </button>
            {canResync && (
              <button onClick={resync} disabled={syncing} className="btn-primary flex items-center gap-2" title="Fetch this session again from NEPSE and overwrite the stored rows">
                <DownloadCloud size={14} className={syncing ? 'animate-pulse' : ''} />{syncing ? 'Re-scraping…' : 'Re-sync from NEPSE'}
              </button>
            )}
          </>
        )}
      />

      {/* Session, last updated and the data check summary */}
      <div className="card flex flex-wrap items-center gap-x-6 gap-y-3 text-xs">
        <span className="flex items-center gap-1.5 text-text-secondary">
          Session <span className="font-semibold text-text-primary">{formatTradeDate(session)}</span>
          {(main?.market_open || sub?.market_open) && <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-amber-400">market open · totals not final</span>}
        </span>
        <span className="flex items-center gap-1.5 text-text-secondary">
          <Clock size={12} />Last updated <span className="font-semibold text-text-primary">{formatDateTime(check?.last_updated)}</span>
        </span>
        <span className="h-4 w-px bg-bg-border" aria-hidden />
        {checking ? (
          <span className="text-text-muted">Checking against NEPSE…</span>
        ) : check ? (
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-text-primary">
              <span className="font-semibold">{summary.scraped ?? 0} of {summary.total ?? 0}</span> rows scraped
            </span>
            <span className="rounded-full bg-down/10 px-2 py-0.5 text-down">{summary.missing ?? 0} missing</span>
            <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-400">{summary.mismatch ?? 0} mismatch</span>
            <span className="text-text-muted">
              {check.feed_ok
                ? `· checked against NEPSE ${formatDateTime(check.checked_at)}`
                : `· NEPSE feed unavailable, presence only* (${check.feed_error ?? 'no response'})`}
            </span>
          </span>
        ) : (
          <span className="text-text-muted">Data check unavailable.</span>
        )}
        <div className="ml-auto flex rounded-lg border border-bg-border bg-bg-primary p-0.5" role="tablist" aria-label="Filter rows by data status">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={filter === item.id}
              onClick={() => setFilter(item.id)}
              disabled={!check}
              className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors disabled:opacity-50 ${filter === item.id ? 'bg-accent/20 text-accent-light' : 'text-text-muted hover:text-text-primary'}`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="flex items-center gap-2 text-sm text-down"><AlertTriangle size={14} />{error}</div>}
      {notice && <div className="flex items-center gap-2 text-sm text-up"><CheckCircle2 size={14} />{notice}</div>}

      {loading && !main ? (
        <p className="text-sm text-text-secondary">Loading indices…</p>
      ) : (
        <>
          <IndexTableCard title="Index" lines={mainLines} emptyText={filter === 'all' ? 'No main index data stored.' : 'No main-index rows with this status.'} />
          <IndexTableCard title="Sub Index" lines={subLines} emptyText={filter === 'all' ? 'No sub-index data stored.' : 'No sub-index rows with this status.'} />
        </>
      )}
      <p className="text-[11px] text-text-muted">
        Mismatch = the stored value differs from what NEPSE's feed reports now (usually totals NEPSE revised after the
        15:45 sync; the 18:30 sync or “Re-sync from NEPSE” fixes them). Highlighted cells show which values; hover for both numbers.
        * = stored but not re-checked because the feed was unavailable.
      </p>
    </div>
  );
}
