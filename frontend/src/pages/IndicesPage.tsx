import { Fragment, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Activity, AlertTriangle, ArrowDown, ArrowUp, BarChart3, CheckCircle2, ChevronDown, ChevronsUpDown, ChevronUp, Clock,
  DownloadCloud, Layers, Minus, RefreshCw, ShieldCheck, XCircle,
} from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import Section from '../components/common/Section';
import Sparkline from '../components/common/Sparkline';
import { changeTone, formatCount, formatNprArab, formatNprCompact, formatPct, formatTradeDate } from '../components/market/format';
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
type Tone = 'up' | 'down' | 'flat';

/** A table row: the stored values (null when the index was never scraped) plus its check. */
interface Line {
  code: string;
  name: string;
  data: IndexRow | null;
  check: IndexVerificationRow | null;
}

const num = (value: number | string | null | undefined) => (value == null || value === '' ? null : Number(value));
const toneText: Record<Tone, string> = { up: 'text-up', down: 'text-down', flat: 'text-text-muted' };
const toneChip: Record<Tone, string> = { up: 'bg-up/10 text-up', down: 'bg-down/10 text-down', flat: 'bg-bg-elevated text-text-muted' };
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
const points = (value: number) => value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const plain = (value: number | string | null | undefined) => {
  const n = num(value);
  return n === null ? '—' : points(n);
};
/** "Banking SubIndex" -> "Banking"; codes like SENSITIVE_FLOAT -> "Sensitive Float". */
const shortName = (line: { code: string; name: string }) =>
  (line.name || line.code.replace(/_/g, ' ')).replace(/\s*sub[- ]?index$/i, '').replace(/\s*index$/i, '').trim() || line.code;

function PctPill({ value }: { value: number | string | null }) {
  const n = num(value);
  const tone = changeTone(n);
  const Arrow = ToneArrow[tone];
  if (n === null) return <span className="text-text-muted">—</span>;
  return (
    <span className={`inline-flex min-w-[68px] items-center justify-center gap-1 rounded-md px-2 py-0.5 font-mono text-[11.5px] font-medium tabular-nums ${toneChip[tone]}`}>
      {tone !== 'flat' && <Arrow size={10} strokeWidth={2.75} />}{Math.abs(n).toFixed(2)}%
    </span>
  );
}

function Delta({ value, format }: { value: number | string | null; format: (v: number) => string }) {
  return <span className={toneText[changeTone(value)]}>{signed(value, format)}</span>;
}

const STATUS_STYLE: Record<IndexDataStatus, { label: string; chip: string; icon: typeof CheckCircle2 }> = {
  scraped: { label: 'Scraped', chip: 'bg-up/10 text-up border-up/25', icon: CheckCircle2 },
  missing: { label: 'Missing', chip: 'bg-down/10 text-down border-down/25', icon: XCircle },
  mismatch: { label: 'Mismatch', chip: 'bg-amber-500/10 text-amber-500 border-amber-500/30', icon: AlertTriangle },
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

// Columns are grouped under a second header row (Price / Turnover / Volume / Transactions) so the
// 16 numeric columns read as four blocks instead of one long strip.
interface Column { key: SortKey; label: string; align?: 'left' | 'center' }
const GROUPS: { label: string; columns: Column[] }[] = [
  {
    label: 'Price',
    columns: [
      { key: 'open', label: 'Open' }, { key: 'high', label: 'High' }, { key: 'low', label: 'Low' },
      { key: 'close', label: 'Close' }, { key: 'ch', label: 'Chg' }, { key: 'ch_pct', label: 'Chg %', align: 'center' },
    ],
  },
  { label: 'Turnover', columns: [{ key: 'turnover', label: 'Value' }, { key: 'tu_ch', label: 'Chg' }, { key: 'tu_ch_pct', label: 'Chg %', align: 'center' }] },
  { label: 'Volume', columns: [{ key: 'volume', label: 'Shares' }, { key: 'vol_ch', label: 'Chg' }, { key: 'vol_ch_pct', label: 'Chg %', align: 'center' }] },
  { label: 'Transactions', columns: [{ key: 'transactions', label: 'Count' }, { key: 'trans_ch', label: 'Chg' }, { key: 'trans_ch_pct', label: 'Chg %', align: 'center' }] },
];
const DATA_COLUMNS = GROUPS.flatMap((group) => group.columns);
const COLUMN_COUNT = DATA_COLUMNS.length + 3; // index + trend + data status
const ALIGN = { left: 'text-left', center: 'text-center', right: 'text-right' } as const;
const STATUS_ORDER: Record<IndexDataStatus, number> = { mismatch: 0, missing: 1, scraped: 2 };

function sortValue(line: Line, key: SortKey): number | string | null {
  if (key === 'code') return line.code;
  if (key === 'status') return line.check ? STATUS_ORDER[line.check.status] : null;
  return line.data ? num(line.data[key as keyof IndexRow] as number | string | null) : null;
}

function SortHeader({ column, sort, onSort, className = '' }: {
  column: Column; sort: { key: SortKey; desc: boolean } | null; onSort: (key: SortKey) => void; className?: string;
}) {
  const active = sort?.key === column.key;
  const Icon = !active ? ChevronsUpDown : sort?.desc ? ChevronDown : ChevronUp;
  return (
    <th className={`whitespace-nowrap px-3 py-2 font-medium ${ALIGN[column.align ?? 'right']} ${className}`}>
      <button type="button" onClick={() => onSort(column.key)} className={`inline-flex items-center gap-0.5 transition-colors hover:text-text-primary ${active ? 'text-accent-light' : ''}`}>
        {column.label}<Icon size={11} className={active ? '' : 'opacity-40'} />
      </button>
    </th>
  );
}

function IndexTableCard({ lines, emptyText }: { lines: Line[]; emptyText: string }) {
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

  // The index column stays pinned while the numbers scroll sideways; it needs its own solid background.
  const sticky = 'sticky left-0 z-10 bg-bg-card';

  return (
    <div className="card overflow-hidden p-0 hover:!shadow-none">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1380px] text-[13px]">
          <thead>
            <tr className="text-[10.5px] font-semibold uppercase tracking-wider text-text-muted">
              <th colSpan={2} className={`${sticky} bg-bg-elevated px-4 py-2 text-left`}>Index</th>
              {GROUPS.map((group) => (
                <th key={group.label} colSpan={group.columns.length} className="bg-bg-elevated px-3 py-2 text-center">
                  {group.label}
                </th>
              ))}
              <th className="bg-bg-elevated px-3 py-2 text-center">Data</th>
            </tr>
            <tr className="border-b border-bg-border text-[11px] text-text-secondary">
              <SortHeader column={{ key: 'code', label: 'Symbol', align: 'left' }} sort={sort} onSort={toggle} className={`${sticky} pl-4`} />
              <th className="px-3 py-2 text-left font-medium">Trend</th>
              {DATA_COLUMNS.map((column) => (
                <SortHeader key={column.key} column={column} sort={sort} onSort={toggle} />
              ))}
              <SortHeader column={{ key: 'status', label: 'Status', align: 'center' }} sort={sort} onSort={toggle} />
            </tr>
          </thead>
          <tbody>
            {sorted.map((line) => {
              const row = line.data;
              const check = line.check;
              const tone = changeTone(row?.ch_pct);
              const differs = new Set((check?.mismatches ?? []).map((m) => FIELD_COLUMN[m.field]));
              const empty = new Set((check?.missing ?? []).map((f) => FIELD_COLUMN[f]));
              const cell = (key: SortKey, extra = '') => {
                const flag = differs.has(key) ? 'bg-amber-500/10 shadow-[inset_0_0_0_1px_rgba(245,158,11,0.45)]' : empty.has(key) ? 'bg-down/5' : '';
                return `whitespace-nowrap px-3 py-3 text-right font-mono tabular-nums text-text-secondary ${flag} ${extra}`;
              };
              const mismatchTitle = (key: SortKey) => {
                const m = check?.mismatches.find((item) => FIELD_COLUMN[item.field] === key);
                return m ? `Stored ${plain(m.stored)} · NEPSE now ${plain(m.source)}` : undefined;
              };
              const expandable = Boolean(check && (check.mismatches.length || check.missing.length));
              const spark = (row?.sparkline ?? []).map(Number).filter((v) => !Number.isNaN(v));
              return (
                <Fragment key={line.code}>
                  <tr className="table-row">
                    <td className={`${sticky} table-sticky py-2.5 pl-4 pr-3 transition-colors`}>
                      <div className="flex items-center gap-3">
                        <span className={`h-8 w-1 shrink-0 rounded-full ${tone === 'up' ? 'bg-up' : tone === 'down' ? 'bg-down' : 'bg-bg-border'}`} aria-hidden />
                        <span className="min-w-0 leading-tight">
                          <span className="block font-semibold tracking-wide text-text-primary">{line.code.replace(/_/g, ' ')}</span>
                          <span className="block max-w-[180px] truncate text-[11px] text-text-muted" title={line.name}>{line.name}</span>
                          {row?.source === 'sharesansar' && (
                            <span title="NEPSE's feed was unavailable: this row is from ShareSansar (no volume / transactions). The next NEPSE sync replaces it."
                              className="mt-1 inline-block rounded bg-amber-500/10 px-1.5 py-px text-[9.5px] font-semibold text-amber-500">
                              via ShareSansar
                            </span>
                          )}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      {spark.length > 1 ? <Sparkline data={spark} width={72} height={24} positive={spark[spark.length - 1] >= spark[0]} /> : <span className="text-text-muted">—</span>}
                    </td>
                    <td className={cell('open')} title={mismatchTitle('open')}>{plain(row?.open)}</td>
                    <td className={cell('high')} title={mismatchTitle('high')}>{plain(row?.high)}</td>
                    <td className={cell('low')} title={mismatchTitle('low')}>{plain(row?.low)}</td>
                    <td className={cell('close', '!text-text-primary font-semibold')} title={mismatchTitle('close')}>{plain(row?.close)}</td>
                    <td className={cell('ch')}><Delta value={row?.ch ?? null} format={points} /></td>
                    <td className={cell('ch_pct', '!text-center')} title={mismatchTitle('ch_pct')}><PctPill value={row?.ch_pct ?? null} /></td>
                    <td className={cell('turnover', '!text-text-primary')} title={mismatchTitle('turnover')}>
                      {formatNprArab(row?.turnover)}
                      {num(row?.turnover_share_pct) !== null && (
                        <span className="block text-[10px] text-text-muted">{num(row?.turnover_share_pct)!.toFixed(2)}% of mkt</span>
                      )}
                    </td>
                    <td className={cell('tu_ch')}><Delta value={row?.tu_ch ?? null} format={(v) => formatNprCompact(v)} /></td>
                    <td className={cell('tu_ch_pct', '!text-center')}><PctPill value={row?.tu_ch_pct ?? null} /></td>
                    <td className={cell('volume', '!text-text-primary')} title={mismatchTitle('volume')}>{formatNprCompact(row?.volume)}</td>
                    <td className={cell('vol_ch')}><Delta value={row?.vol_ch ?? null} format={(v) => formatNprCompact(v)} /></td>
                    <td className={cell('vol_ch_pct', '!text-center')}><PctPill value={row?.vol_ch_pct ?? null} /></td>
                    <td className={cell('transactions', '!text-text-primary')} title={mismatchTitle('transactions')}>{formatThousands(row?.transactions)}</td>
                    <td className={cell('trans_ch')}><Delta value={row?.trans_ch ?? null} format={(v) => v.toLocaleString('en-IN')} /></td>
                    <td className={cell('trans_ch_pct', '!text-center')}><PctPill value={row?.trans_ch_pct ?? null} /></td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-center">
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
                    <tr className="border-b border-bg-border bg-bg-elevated">
                      <td colSpan={COLUMN_COUNT} className="px-5 py-3">
                        <div className="flex flex-wrap gap-x-6 gap-y-1.5 text-[11.5px]">
                          {check.mismatches.map((m) => (
                            <span key={m.field} className="font-mono">
                              <span className="font-sans font-semibold text-amber-500">{FIELD_LABEL[m.field] ?? m.field}:</span>{' '}
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
        {sorted.length === 0 && <p className="py-10 text-center text-sm text-text-muted">{emptyText}</p>}
      </div>
    </div>
  );
}

function StatTile({ icon: Icon, label, children, footer }: { icon: typeof Activity; label: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="card flex min-w-0 flex-col gap-2">
      <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        <Icon size={13} className="text-accent-light" />{label}
      </span>
      <div className="min-w-0 flex-1">{children}</div>
      {footer && <div className="border-t border-bg-border pt-2 text-[11.5px] text-text-secondary">{footer}</div>}
    </div>
  );
}

function SummaryTiles({ nepse, subRows }: { nepse: IndexRow | undefined; subRows: IndexRow[] }) {
  const tone = changeTone(nepse?.ch_pct);
  const Arrow = ToneArrow[tone];
  const spark = (nepse?.sparkline ?? []).map(Number).filter((v) => !Number.isNaN(v));
  const breadth = subRows.reduce((acc, row) => ({ ...acc, [changeTone(row.ch_pct)]: acc[changeTone(row.ch_pct)] + 1 }), { up: 0, down: 0, flat: 0 } as Record<Tone, number>);
  const ranked = [...subRows].filter((row) => num(row.ch_pct) !== null).sort((a, b) => Number(b.ch_pct) - Number(a.ch_pct));
  const best = ranked[0];
  const worst = ranked[ranked.length - 1];
  const total = subRows.length || 1;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile
        icon={Activity}
        label="NEPSE Index"
        footer={nepse && (
          <span className="flex justify-between font-mono tabular-nums">
            <span>L <span className="text-text-primary">{plain(nepse.low)}</span></span>
            <span>H <span className="text-text-primary">{plain(nepse.high)}</span></span>
          </span>
        )}
      >
        <div className="flex items-end justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-2xl font-semibold tabular-nums text-text-primary">{plain(nepse?.close)}</div>
            <div className={`mt-0.5 flex items-center gap-1 font-mono text-[13px] tabular-nums ${toneText[tone]}`}>
              {tone !== 'flat' && <Arrow size={13} strokeWidth={2.5} />}
              {signed(nepse?.ch, points)} ({formatPct(nepse?.ch_pct)})
            </div>
          </div>
          {spark.length > 1 && <Sparkline data={spark} width={96} height={36} positive={tone !== 'down'} />}
        </div>
      </StatTile>

      <StatTile
        icon={BarChart3}
        label="Market turnover"
        footer={(
          <span className="flex justify-between">
            <span>Vol <span className="font-mono text-text-primary">{formatNprCompact(nepse?.volume)}</span></span>
            <span>Trans <span className="font-mono text-text-primary">{formatCount(nepse?.transactions)}</span></span>
          </span>
        )}
      >
        <div className="font-mono text-2xl font-semibold tabular-nums text-text-primary">Rs {formatNprArab(nepse?.turnover)}</div>
        <div className={`mt-0.5 font-mono text-[13px] tabular-nums ${toneText[changeTone(nepse?.tu_ch_pct)]}`}>
          {formatPct(nepse?.tu_ch_pct)} <span className="font-sans text-text-muted">vs previous session</span>
        </div>
      </StatTile>

      <StatTile
        icon={Layers}
        label="Sector breadth"
        footer={<span>{breadth.up} advancing · {breadth.down} declining · {breadth.flat} unchanged</span>}
      >
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-2xl font-semibold tabular-nums text-up">{breadth.up}</span>
          <span className="text-text-muted">/</span>
          <span className="font-mono text-2xl font-semibold tabular-nums text-down">{breadth.down}</span>
          <span className="text-[12px] text-text-muted">sub-indices up / down</span>
        </div>
        <div className="mt-2 flex h-1.5 overflow-hidden rounded-full bg-bg-elevated">
          <span className="bg-up" style={{ width: `${(breadth.up / total) * 100}%` }} />
          <span className="bg-text-muted/40" style={{ width: `${(breadth.flat / total) * 100}%` }} />
          <span className="bg-down" style={{ width: `${(breadth.down / total) * 100}%` }} />
        </div>
      </StatTile>

      <StatTile icon={ArrowUp} label="Sector leaders">
        <div className="space-y-2.5">
          {[{ label: 'Top gainer', row: best }, { label: 'Top loser', row: worst }].map(({ label, row }) => (
            <div key={label} className="flex items-center justify-between gap-3">
              <span className="min-w-0">
                <span className="block text-[10.5px] uppercase tracking-wider text-text-muted">{label}</span>
                <span className="block truncate font-medium text-text-primary">{row ? shortName(row) : '—'}</span>
              </span>
              <PctPill value={row?.ch_pct ?? null} />
            </div>
          ))}
        </div>
      </StatTile>
    </div>
  );
}

/** Every sub-index's % change as a bar diverging from zero, best first. */
function SectorPerformance({ rows }: { rows: IndexRow[] }) {
  const ranked = [...rows].filter((row) => num(row.ch_pct) !== null).sort((a, b) => Number(b.ch_pct) - Number(a.ch_pct));
  const max = Math.max(...ranked.map((row) => Math.abs(Number(row.ch_pct))), 0.01);
  if (!ranked.length) return null;
  return (
    <div className="card grid gap-x-10 gap-y-2.5 md:grid-cols-2">
      {ranked.map((row) => {
        const value = Number(row.ch_pct);
        const width = `${(Math.abs(value) / max) * 50}%`;
        return (
          <div key={row.code} className="grid grid-cols-[120px_minmax(0,1fr)_64px] items-center gap-3 text-[12.5px]">
            <span className="truncate text-text-secondary" title={row.name}>{shortName(row)}</span>
            <span className="relative h-2 rounded-full bg-bg-elevated">
              <span className="absolute inset-y-[-3px] left-1/2 w-px bg-bg-border" aria-hidden />
              <span
                className={`absolute inset-y-0 rounded-full ${value >= 0 ? 'left-1/2 bg-up' : 'right-1/2 bg-down'}`}
                style={{ width }}
              />
            </span>
            <span className={`text-right font-mono tabular-nums ${toneText[changeTone(value)]}`}>{formatPct(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

const FILTERS: { id: StatusFilter; label: string }[] = [
  { id: 'all', label: 'All rows' },
  { id: 'issues', label: 'Issues' },
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
      setNotice(result.sync?.fallback === 'sharesansar'
        ? `NEPSE was unavailable, so missing sessions were filled from ShareSansar: ${result.sync.saved} rows added (NEPSE rows are never overwritten).`
        : `Re-scraped from NEPSE: ${result.sync?.saved ?? 0} index rows saved (no duplicates).`);
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
  const marketOpen = Boolean(main?.market_open || sub?.market_open);
  const nepse = main?.rows.find((row) => row.code === 'NEPSE') ?? main?.rows[0];
  const subRows = sub?.rows ?? [];
  const scrapedPct = summary.total ? ((summary.scraped ?? 0) / summary.total) * 100 : 0;

  const filterTabs = (
    <div className="flex rounded-lg border border-bg-border bg-bg-secondary p-0.5" role="tablist" aria-label="Filter rows by data status">
      {FILTERS.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={filter === item.id}
          onClick={() => setFilter(item.id)}
          disabled={!check}
          className={`rounded-md px-3 py-1 text-[11.5px] font-medium transition-colors disabled:opacity-50 ${filter === item.id ? 'bg-accent text-white shadow-sm' : 'text-text-muted hover:text-text-primary'}`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="space-y-8">
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

      {/* Session status and the data check, one compact bar */}
      <div className="card flex flex-wrap items-center gap-x-8 gap-y-3 py-3 text-[12.5px] hover:!shadow-none">
        <div className="flex items-center gap-2.5">
          <span className={`h-2 w-2 rounded-full ${marketOpen ? 'animate-pulse bg-up' : 'bg-text-muted/60'}`} aria-hidden />
          <span className="text-text-muted">Session</span>
          <span className="font-semibold text-text-primary">{formatTradeDate(session)}</span>
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${marketOpen ? 'bg-amber-500/10 text-amber-500' : 'bg-bg-elevated text-text-secondary'}`}>
            {marketOpen ? 'Market open · totals not final' : 'Closed'}
          </span>
        </div>
        <div className="flex items-center gap-2 text-text-muted">
          <Clock size={13} />Last updated <span className="font-medium text-text-primary">{formatDateTime(check?.last_updated)}</span>
        </div>
        <div className="flex min-w-[260px] flex-1 items-center gap-3">
          <ShieldCheck size={15} className="shrink-0 text-accent-light" />
          {checking ? (
            <span className="text-text-muted">Checking against NEPSE…</span>
          ) : check ? (
            <div className="flex flex-1 flex-wrap items-center gap-x-3 gap-y-1.5">
              <span className="text-text-primary"><span className="font-semibold">{summary.scraped ?? 0}/{summary.total ?? 0}</span> verified</span>
              <span className="h-1.5 w-24 overflow-hidden rounded-full bg-bg-elevated">
                <span className="block h-full rounded-full bg-up" style={{ width: `${scrapedPct}%` }} />
              </span>
              {(summary.missing ?? 0) > 0 && <span className="rounded-full bg-down/10 px-2 py-0.5 text-[11px] font-medium text-down">{summary.missing} missing</span>}
              {(summary.mismatch ?? 0) > 0 && <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-500">{summary.mismatch} mismatch</span>}
              <span className="text-[11.5px] text-text-muted">
                {check.feed_ok
                  ? `checked ${formatDateTime(check.checked_at)}`
                  : `NEPSE feed unavailable, presence only* (${check.feed_error ?? 'no response'})`}
              </span>
            </div>
          ) : (
            <span className="text-text-muted">Data check unavailable.</span>
          )}
        </div>
      </div>

      {[...(main?.rows ?? []), ...(sub?.rows ?? [])].some((r) => r.source === 'sharesansar') && (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-500">
          <AlertTriangle size={14} className="mt-px shrink-0" />
          Some rows are from ShareSansar because NEPSE's feed was unavailable (marked “via ShareSansar”). Closes and % changes match
          NEPSE; turnover can differ slightly and volume / transactions are missing. The next successful NEPSE sync replaces them.
        </div>
      )}
      {error && <div className="flex items-center gap-2 rounded-md border border-down/30 bg-down/10 px-4 py-2.5 text-sm text-down"><AlertTriangle size={14} />{error}</div>}
      {notice && <div className="flex items-center gap-2 rounded-md border border-up/30 bg-up/10 px-4 py-2.5 text-sm text-up"><CheckCircle2 size={14} />{notice}</div>}

      {loading && !main ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-32 rounded-md" />)}
        </div>
      ) : (
        <>
          <SummaryTiles nepse={nepse} subRows={subRows} />

          {subRows.length > 0 && (
            <Section title="Sector performance" subtitle="Sub-index % change vs the previous session, best to worst">
              <SectorPerformance rows={subRows} />
            </Section>
          )}

          <Section title="Main indices" subtitle="NEPSE, Sensitive and Float indices" action={filterTabs}>
            <IndexTableCard lines={mainLines} emptyText={filter === 'all' ? 'No main index data stored.' : 'No main-index rows with this status.'} />
          </Section>

          <Section title="Sub-indices" subtitle="Sector indices with turnover share of the whole market · click a column to sort">
            <IndexTableCard lines={subLines} emptyText={filter === 'all' ? 'No sub-index data stored.' : 'No sub-index rows with this status.'} />
          </Section>
        </>
      )}

      <div className="card flex flex-wrap items-start gap-x-6 gap-y-2 text-[11.5px] text-text-muted hover:!shadow-none">
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm bg-amber-500/10 shadow-[inset_0_0_0_1px_rgba(245,158,11,0.45)]" />Mismatch: stored value differs from NEPSE's feed now (hover the cell for both numbers)</span>
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm bg-down/10" />Missing value</span>
        <span>* stored but not re-checked because the feed was unavailable</span>
        <span className="basis-full">
          Mismatches are usually totals NEPSE revised after the 15:45 sync; the 18:30 sync or “Re-sync from NEPSE” fixes them.
        </span>
      </div>
    </div>
  );
}
