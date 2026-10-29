// Floor Sheet Summary: every tracked company's trades for one session as a symbol x time-bucket
// grid (quantity, trades, turnover, close, VWAP, change per cell), with an OHLC view and the
// server's validation checks.  The grid is windowed in both directions: a full market day
// (279 stocks x 240 one-minute buckets) would otherwise be ~67k cells in the DOM.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, CheckCircle2, ChevronsLeft, ChevronsRight, MinusCircle, RefreshCw, Search, ShieldCheck, X, XCircle,
} from 'lucide-react';

import PageHeader from '../components/common/PageHeader';
import { changeTone, formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from '../components/market/format';
import { BUCKET_MINUTES, type BucketMinutes, type GridCell, type GridCheck, type GridCompany } from '../api/floorsheetGrid';
import { useFloorsheetGrid } from '../hooks/useFloorsheetGrid';

type Tab = 'floorsheet' | 'ohlc';
type Density = 'detailed' | 'compact';
type SortKey = 'symbol' | 'day_desc' | 'day_asc' | 'turnover' | 'trades';

const SIZES = {
  detailed: { row: 76, col: 118 },
  compact: { row: 42, col: 88 },
} as const;
const HEAD_H = 34;
const OVERSCAN = 3;
// NEPSE's daily circuit; the DAY % bar is full at ±10%.
const CIRCUIT_PCT = 10;
// Room left under the grid for the app footer.
const BOTTOM_GAP = 48;

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'symbol', label: 'Symbol A–Z' },
  { key: 'day_desc', label: 'DAY % high → low' },
  { key: 'day_asc', label: 'DAY % low → high' },
  { key: 'turnover', label: 'Turnover' },
  { key: 'trades', label: 'Trades' },
];

const fieldClass =
  'rounded-md border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary outline-none transition focus:border-accent';

const toneClass = {
  up: 'bg-up/10 text-up',
  down: 'bg-down/10 text-down',
  flat: 'text-text-secondary',
} as const;

const toneText = { up: 'text-up', down: 'text-down', flat: 'text-text-secondary' } as const;

function bucketEnd(start: string, minutes: number) {
  const [h, m] = start.split(':').map(Number);
  // The 45M grid's last bucket stops at the 15:00 close.
  const end = Math.min(h * 60 + m + minutes, 15 * 60);
  return `${String(Math.floor(end / 60)).padStart(2, '0')}:${String(end % 60).padStart(2, '0')}`;
}

function cellTitle(company: GridCompany, cell: GridCell, label: string) {
  return [
    `${company.symbol}  ${label} NPT`,
    `Open ${formatPrice(cell.open)}   High ${formatPrice(cell.high)}   Low ${formatPrice(cell.low)}   Close ${formatPrice(cell.close)}`,
    `VWAP ${formatPrice(cell.vwap)}   Change ${formatPct(cell.change_pct)}`,
    `Quantity ${formatCount(cell.quantity)}   Trades ${formatCount(cell.trades)}   Turnover Rs ${formatCount(cell.turnover)}`,
  ].join('\n');
}

function Segmented<T extends string | number>({ options, value, onChange, label }: {
  options: readonly { key: T; label: string }[];
  value: T;
  onChange: (key: T) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="flex overflow-hidden rounded-md border border-bg-border">
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          aria-pressed={option.key === value}
          onClick={() => onChange(option.key)}
          className={`px-2.5 py-2 text-xs transition ${
            option.key === value ? 'bg-accent/20 font-semibold text-text-primary' : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function SummaryItem({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0" title={hint}>
      <p className="text-[11px] uppercase tracking-wide text-text-muted">{label}</p>
      <p className="font-mono text-sm font-semibold text-text-primary">{value}</p>
    </div>
  );
}

function DayChange({ company, compact }: { company: GridCompany; compact: boolean }) {
  const pct = company.day_change_pct;
  const tone = changeTone(pct);
  const width = pct == null ? 0 : Math.min(Math.abs(pct) / CIRCUIT_PCT, 1) * 50;
  const title = [
    `Close ${formatPrice(company.session_close)} vs previous ${formatPrice(company.prev_close)}`,
    company.published_change_pct != null ? `Exchange published ${formatPct(company.published_change_pct)}` : 'Not yet published by the exchange',
  ].join('\n');
  return (
    <div className={`flex h-full flex-col justify-center px-2 ${compact ? 'gap-0.5' : 'gap-1.5'}`} title={title}>
      <span className={`font-mono text-xs font-semibold ${toneText[tone]}`}>{formatPct(pct)}</span>
      <span className="relative block h-1.5 w-full rounded-full bg-bg-border">
        <span className="absolute left-1/2 top-[-2px] h-[10px] w-px bg-text-muted/50" />
        <span
          className={`absolute top-0 h-full ${tone === 'down' ? 'rounded-l-full bg-down' : 'rounded-r-full bg-up'}`}
          style={tone === 'down' ? { right: '50%', width: `${width}%` } : { left: '50%', width: `${width}%` }}
        />
      </span>
    </div>
  );
}

function FloorCell({ cell, compact }: { cell: GridCell; compact: boolean }) {
  if (compact) {
    return (
      <>
        <span className="font-mono text-xs font-semibold leading-4">{formatPrice(cell.close)}</span>
        <span className="font-mono text-[10px] leading-3 opacity-80">{formatPct(cell.change_pct)}</span>
      </>
    );
  }
  return (
    <>
      <div className="flex items-baseline justify-between gap-1">
        <span className="font-mono text-[13px] font-semibold">{formatPrice(cell.close)}</span>
        <span className="font-mono text-[10px]">{formatPct(cell.change_pct)}</span>
      </div>
      <div className="font-mono text-[10px] text-text-secondary">VWAP {formatPrice(cell.vwap)}</div>
      <div className="font-mono text-[10px] text-text-secondary">
        {formatCount(cell.quantity)} <span className="text-text-muted">sh ·</span> {cell.trades} <span className="text-text-muted">tr</span>
      </div>
      <div className="font-mono text-[10px] text-text-muted">Rs {formatNprCompact(cell.turnover)}</div>
    </>
  );
}

function OhlcCell({ cell, compact }: { cell: GridCell; compact: boolean }) {
  if (compact) {
    return (
      <>
        <span className="font-mono text-xs font-semibold leading-4">{formatPrice(cell.close)}</span>
        <span className="font-mono text-[10px] leading-3 text-text-muted">{formatPrice(cell.low)}–{formatPrice(cell.high)}</span>
      </>
    );
  }
  const rows: [string, number, string][] = [
    ['O', cell.open, 'text-text-secondary'],
    ['H', cell.high, 'text-text-secondary'],
    ['L', cell.low, 'text-text-secondary'],
    ['C', cell.close, 'font-semibold'],
  ];
  return (
    <div className="space-y-px">
      {rows.map(([label, value, cls]) => (
        <div key={label} className="flex items-baseline gap-2 font-mono text-[10px] leading-[15px]">
          <span className="w-2 text-text-muted">{label}</span>
          <span className={cls}>{formatPrice(value)}</span>
        </div>
      ))}
    </div>
  );
}

interface GridProps {
  companies: GridCompany[];
  buckets: string[];
  minutes: number;
  tab: Tab;
  density: Density;
  loading: boolean;
  jumpToLatest: boolean;
  session: string;
}

function SessionGrid({ companies, buckets, minutes, tab, density, loading, jumpToLatest, session }: GridProps) {
  const scroller = useRef<HTMLDivElement>(null);
  const frame = useRef(0);
  // Minutes after 11:00 at the left edge, so a new bucket size or density keeps the same time in view.
  const leftTime = useRef(0);
  const [view, setView] = useState({ top: 0, left: 0, width: 0, height: 0 });
  const [gridHeight, setGridHeight] = useState(520);

  const { row: ROW_H, col: COL_W } = SIZES[density];
  const compact = density === 'compact';
  // Narrow screens drop S.N and slim the sticky block so the buckets stay visible.
  const narrow = view.width > 0 && view.width < 560;
  const SN_W = narrow ? 0 : 40;
  const SYMBOL_W = narrow ? 70 : 86;
  const DAY_W = narrow ? 72 : 96;
  const LEFT_W = SN_W + SYMBOL_W + DAY_W;

  const measure = useCallback(() => {
    const el = scroller.current;
    if (!el) return;
    setView({ top: el.scrollTop, left: el.scrollLeft, width: el.clientWidth, height: el.clientHeight });
  }, []);

  // Fill the viewport below the grid's top edge.
  const fit = useCallback(() => {
    const el = scroller.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY;
    setGridHeight(Math.max(380, window.innerHeight - top - BOTTOM_GAP));
  }, []);

  useLayoutEffect(() => {
    fit();
    measure();
    const el = scroller.current;
    if (!el) return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    window.addEventListener('resize', fit);
    return () => { observer.disconnect(); window.removeEventListener('resize', fit); };
  }, [fit, measure]);

  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  const onScroll = () => {
    const el = scroller.current;
    if (el) leftTime.current = (el.scrollLeft / COL_W) * minutes;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(measure);
  };

  useLayoutEffect(() => {
    const el = scroller.current;
    if (el) el.scrollLeft = (leftTime.current / minutes) * COL_W;
    measure();
  }, [minutes, COL_W, measure]);

  // A different session starts again at the open.
  useLayoutEffect(() => {
    leftTime.current = 0;
    scroller.current?.scrollTo({ left: 0, top: 0 });
    measure();
  }, [session, measure]);

  const cellMaps = useMemo(
    () => companies.map((c) => new Map(c.cells.map((cell) => [cell.i, cell]))),
    [companies],
  );
  const lastTraded = useMemo(
    () => companies.reduce((max, c) => Math.max(max, c.cells.length ? c.cells[c.cells.length - 1].i : -1), -1),
    [companies],
  );

  const scrollToCol = useCallback((col: number) => {
    const el = scroller.current;
    if (!el) return;
    const visibleCols = Math.max(1, Math.floor((el.clientWidth - LEFT_W) / COL_W));
    el.scrollTo({ left: Math.max(0, (col - visibleCols + 1) * COL_W), behavior: 'smooth' });
  }, [COL_W, LEFT_W]);

  // A live session opens on the newest bucket; stored sessions open at 11:00.
  useEffect(() => {
    if (jumpToLatest && lastTraded >= 0) scrollToCol(lastTraded);
  }, [jumpToLatest, lastTraded, scrollToCol]);

  const firstRow = Math.max(0, Math.floor(view.top / ROW_H) - OVERSCAN);
  const lastRow = Math.min(companies.length, Math.ceil((view.top + view.height) / ROW_H) + OVERSCAN);
  const firstCol = Math.max(0, Math.floor(view.left / COL_W) - OVERSCAN);
  const lastCol = Math.min(buckets.length, Math.ceil((view.left + view.width - LEFT_W) / COL_W) + OVERSCAN);
  const cols: number[] = [];
  for (let c = firstCol; c < lastCol; c += 1) cols.push(c);

  const width = LEFT_W + buckets.length * COL_W;
  const stickyLeft = 'sticky left-0 z-[2] flex shrink-0';

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-muted">
        {tab === 'floorsheet' && !compact && (
          <span>
            Each cell: <span className="text-text-secondary">close · change %</span> / VWAP / shares · trades / turnover
          </span>
        )}
        {tab === 'floorsheet' && compact && <span>Each cell: <span className="text-text-secondary">close</span> / change %</span>}
        {tab === 'ohlc' && !compact && <span>Each cell: open, high, low, close of the bucket</span>}
        {tab === 'ohlc' && compact && <span>Each cell: <span className="text-text-secondary">close</span> / low–high</span>}
        <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-up/40" /> up vs previous bucket</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-down/40" /> down</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm border border-bg-border" /> unchanged / no trades</span>
        <span className="ml-auto flex gap-1">
          <button type="button" onClick={() => scroller.current?.scrollTo({ left: 0, behavior: 'smooth' })}
            className="btn-ghost flex items-center gap-1 px-2 py-1 text-[11px]">
            <ChevronsLeft size={12} /> 11:00
          </button>
          <button type="button" onClick={() => scrollToCol(lastTraded)} disabled={lastTraded < 0}
            className="btn-ghost flex items-center gap-1 px-2 py-1 text-[11px]">
            Latest <ChevronsRight size={12} />
          </button>
        </span>
      </div>

      <div
        ref={scroller}
        onScroll={onScroll}
        style={{ height: gridHeight }}
        className={`relative overflow-auto rounded-md border border-bg-border bg-bg-card transition-opacity ${loading ? 'opacity-60' : ''}`}
      >
        <div style={{ width, height: HEAD_H + companies.length * ROW_H }} className="relative">
          {/* Header row: sticky to the top; its first block also sticks to the left. */}
          <div className="sticky top-0 z-[3] border-b border-bg-border bg-bg-elevated" style={{ height: HEAD_H, width }}>
            <div className={`${stickyLeft} h-full items-center bg-bg-elevated text-[11px] font-medium uppercase tracking-wide text-text-muted`} style={{ width: LEFT_W }}>
              {SN_W > 0 && <span className="px-2 text-right" style={{ width: SN_W }}>#</span>}
              <span className="px-2" style={{ width: SYMBOL_W }}>Symbol</span>
              <span className="border-r border-bg-border px-2" style={{ width: DAY_W }}>Day %</span>
            </div>
            {cols.map((c) => (
              <div
                key={c}
                className="absolute top-0 flex h-full items-center justify-center border-l border-bg-border font-mono text-[11px] text-text-secondary"
                style={{ left: LEFT_W + c * COL_W, width: COL_W }}
                title={`${buckets[c]}–${bucketEnd(buckets[c], minutes)} NPT`}
              >
                {minutes > 1 ? `${buckets[c]}–${bucketEnd(buckets[c], minutes)}` : buckets[c]}
              </div>
            ))}
          </div>

          {companies.slice(firstRow, lastRow).map((company, offset) => {
            const r = firstRow + offset;
            const cells = cellMaps[r];
            return (
              <div
                key={company.company_id}
                className="group absolute left-0 border-b border-bg-border hover:bg-bg-elevated/40"
                style={{ top: HEAD_H + r * ROW_H, height: ROW_H, width }}
              >
                <div className={`${stickyLeft} bg-bg-card group-hover:bg-bg-elevated`} style={{ width: LEFT_W, height: ROW_H }}>
                  {SN_W > 0 && (
                    <span className="self-center px-2 text-right font-mono text-[11px] text-text-muted" style={{ width: SN_W }}>{r + 1}</span>
                  )}
                  <span className="flex min-w-0 flex-col justify-center px-2" style={{ width: SYMBOL_W }}>
                    <Link to={`/companies/${company.symbol}`} className="truncate text-xs font-semibold text-text-primary hover:text-accent" title={company.name}>
                      {company.symbol}
                    </Link>
                    {!compact && <span className="font-mono text-[10px] text-text-muted">{formatPrice(company.session_close)}</span>}
                  </span>
                  <span className="border-r border-bg-border" style={{ width: DAY_W }}>
                    <DayChange company={company} compact={compact} />
                  </span>
                </div>
                {cols.map((c) => {
                  const cell = cells.get(c);
                  if (!cell) return null;
                  return (
                    <div
                      key={c}
                      className={`absolute top-0 flex flex-col justify-center border-l border-bg-border px-2 ${compact ? '' : 'gap-0.5'} ${toneClass[changeTone(cell.change_pct)]}`}
                      style={{ left: LEFT_W + c * COL_W, width: COL_W, height: ROW_H }}
                      title={cellTitle(company, cell, `${buckets[c]}–${bucketEnd(buckets[c], minutes)}`)}
                    >
                      {tab === 'floorsheet' ? <FloorCell cell={cell} compact={compact} /> : <OhlcCell cell={cell} compact={compact} />}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const checkIcon = {
  pass: <CheckCircle2 size={14} className="shrink-0 text-up" />,
  fail: <XCircle size={14} className="shrink-0 text-down" />,
  'n/a': <MinusCircle size={14} className="shrink-0 text-text-muted" />,
} as const;

function ChecksPopover({ checks, onClose }: { checks: GridCheck[]; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    const onClick = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    return () => { document.removeEventListener('keydown', onKey); document.removeEventListener('mousedown', onClick); };
  }, [onClose]);

  return (
    <div ref={box} role="dialog" aria-label="Validation checks"
      className="absolute right-0 top-full z-20 mt-2 max-h-[65vh] w-[min(760px,calc(100vw-2rem))] overflow-auto rounded-md border border-bg-border bg-bg-card p-4 shadow-2xl">
      <div className="mb-2 flex items-center gap-2">
        <h2 className="text-sm font-semibold text-text-primary">Validation checks</h2>
        <span className="text-[11px] text-text-muted">Grid recomputed from the raw trades and compared with the exchange's daily figures</span>
        <button type="button" onClick={onClose} aria-label="Close" className="ml-auto text-text-muted hover:text-text-primary"><X size={15} /></button>
      </div>
      <div className="divide-y divide-bg-border">
        {checks.map((check) => (
          <div key={check.key} className="py-2">
            <div className="flex items-center gap-2 text-xs">
              {checkIcon[check.status]}
              <span className="text-text-primary">{check.label}</span>
              <span className="ml-auto whitespace-nowrap font-mono text-[11px] text-text-muted">
                {check.status === 'n/a' ? 'not available yet' : `${formatCount(check.compared)} compared`}
              </span>
            </div>
            {check.note && <p className="mt-1 pl-6 text-[11px] text-text-muted">{check.note}</p>}
            {check.mismatches.length > 0 && (
              <div className="mt-2 overflow-x-auto pl-6">
                <table className="text-[11px]">
                  <thead>
                    <tr className="text-text-muted">
                      {['Symbol', 'Bucket', 'Field', 'Expected', 'Actual', 'Against'].map((h) => (
                        <th key={h} className="px-2 py-1 text-left font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {check.mismatches.map((m, i) => (
                      <tr key={i} className="font-mono text-text-secondary">
                        <td className="px-2 py-0.5 text-text-primary">{m.symbol}</td>
                        <td className="px-2 py-0.5">{m.bucket ?? '—'}</td>
                        <td className="px-2 py-0.5">{m.field}</td>
                        <td className="px-2 py-0.5">{m.expected ?? '—'}</td>
                        <td className="px-2 py-0.5 text-down">{m.actual ?? '—'}</td>
                        <td className="px-2 py-0.5">{m.source || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {check.mismatch_count > check.mismatches.length && (
              <p className="mt-1 pl-6 text-[11px] text-text-muted">
                Showing {check.mismatches.length} of {check.mismatch_count}. Run <code>manage.py validate_floorsheet_grid</code> for all.
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ChecksChip({ checks }: { checks: GridCheck[] }) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const failed = checks.filter((c) => c.status === 'fail').length;
  const passed = checks.filter((c) => c.status === 'pass').length;
  const counted = checks.filter((c) => c.status !== 'n/a').length;
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition ${
          failed ? 'border-down/40 bg-down/10 text-down' : 'border-up/40 bg-up/10 text-up'
        }`}
      >
        {failed ? <AlertTriangle size={13} /> : <ShieldCheck size={13} />}
        {failed ? `${failed} check${failed > 1 ? 's' : ''} failing` : `${passed}/${counted} checks pass`}
      </button>
      {open && <ChecksPopover checks={checks} onClose={close} />}
    </div>
  );
}

function sortCompanies(companies: GridCompany[], key: SortKey) {
  const byPct = (dir: 1 | -1) => (a: GridCompany, b: GridCompany) => {
    // Stocks without a DAY % go last either way.
    if (a.day_change_pct == null) return 1;
    if (b.day_change_pct == null) return -1;
    return dir * (a.day_change_pct - b.day_change_pct);
  };
  const sorted = [...companies];
  if (key === 'day_desc') sorted.sort(byPct(-1));
  else if (key === 'day_asc') sorted.sort(byPct(1));
  else if (key === 'turnover') sorted.sort((a, b) => b.turnover - a.turnover);
  else if (key === 'trades') sorted.sort((a, b) => b.trades - a.trades);
  return sorted;
}

export default function FloorsheetSummaryPage() {
  const [date, setDate] = useState('');
  const [minutes, setMinutes] = useState<BucketMinutes>(1);
  const [tab, setTab] = useState<Tab>('floorsheet');
  const [density, setDensity] = useState<Density>('detailed');
  const [sort, setSort] = useState<SortKey>('symbol');
  const [search, setSearch] = useState('');
  const { data, loading, error, reload } = useFloorsheetGrid(date, minutes);

  const companies = useMemo(() => {
    const query = search.trim().toUpperCase();
    const all = data?.companies ?? [];
    const matching = query ? all.filter((c) => c.symbol.includes(query) || c.name.toUpperCase().includes(query)) : all;
    return sortCompanies(matching, sort);
  }, [data, search, sort]);

  const traded = data?.companies.filter((c) => c.trades > 0).length ?? 0;
  const totals = useMemo(() => (data?.companies ?? []).reduce(
    (acc, c) => ({ trades: acc.trades + c.trades, quantity: acc.quantity + c.quantity, turnover: acc.turnover + c.turnover }),
    { trades: 0, quantity: 0, turnover: 0 },
  ), [data]);
  const selectedDate = date || data?.date || '';
  const live = data?.status === 'live';
  // Hundreds of stored sessions: group the picker by month.
  const datesByMonth = useMemo(() => {
    const groups = new Map<string, string[]>();
    for (const d of data?.dates ?? []) {
      const month = new Date(`${d}T00:00:00`).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
      groups.set(month, [...(groups.get(month) ?? []), d]);
    }
    return [...groups.entries()];
  }, [data]);

  return (
    <div className="space-y-3">
      <PageHeader
        title="Floor Sheet Summary"
        subtitle="Every trade of the tracked companies for one session, grouped into time buckets from the 11:00 open."
        actions={
          <button type="button" onClick={reload} className="btn-ghost flex items-center gap-2 text-xs">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        }
      />

      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-md border border-down/30 bg-down/10 px-4 py-3 text-sm text-down">
          <AlertTriangle size={15} /> {error}
        </div>
      )}

      {/* Controls */}
      <div className="card flex flex-wrap items-center gap-2 !p-3">
        <select
          value={selectedDate}
          onChange={(e) => setDate(e.target.value)}
          className={`${fieldClass} w-full sm:w-[200px]`}
          disabled={!data?.dates.length}
          aria-label="Session"
        >
          {!selectedDate && <option value="">{loading ? 'Loading…' : 'No sessions'}</option>}
          {datesByMonth.map(([month, dates]) => (
            <optgroup key={month} label={month}>
              {dates.map((d) => (
                <option key={d} value={d}>{formatTradeDate(d)}{d === data?.dates[0] ? '  · latest' : ''}</option>
              ))}
            </optgroup>
          ))}
        </select>
        <Segmented
          label="Bucket size"
          options={BUCKET_MINUTES.map((m) => ({ key: m, label: `${m}M` }))}
          value={minutes}
          onChange={setMinutes}
        />
        <Segmented
          label="View"
          options={[{ key: 'floorsheet', label: 'Floor Sheet' }, { key: 'ohlc', label: 'OHLC_DATA' }] as const}
          value={tab}
          onChange={setTab}
        />
        <Segmented
          label="Density"
          options={[{ key: 'detailed', label: 'Detailed' }, { key: 'compact', label: 'Compact' }] as const}
          value={density}
          onChange={setDensity}
        />
        <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className={`${fieldClass} w-full sm:w-[170px]`} aria-label="Sort">
          {SORTS.map((s) => <option key={s.key} value={s.key}>Sort: {s.label}</option>)}
        </select>
        <span className="relative min-w-[180px] flex-1">
          <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search symbol or company" aria-label="Search" className={`${fieldClass} w-full pl-9`} />
        </span>
      </div>

      {/* Session summary */}
      {data?.date && (
        // z-10 lifts the checks popover above the grid's sticky header.
        <div className="card relative z-10 flex flex-wrap items-center gap-x-8 gap-y-3 !py-3">
          <div className="flex items-center gap-2">
            <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
              live ? 'bg-up/15 text-up' : 'bg-bg-elevated text-text-secondary'
            }`}>
              {live && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" />}
              {live ? 'LIVE' : 'STORED'}
            </span>
            <span className="text-sm font-semibold text-text-primary">{formatTradeDate(data.date)}</span>
          </div>
          <SummaryItem label="Stocks" value={`${traded} / ${data.companies.length}`} hint="Traded / tracked companies" />
          <SummaryItem label="Buckets" value={`${formatCount(data.buckets.length)} × ${data.minutes}M`} />
          <SummaryItem label="Trades" value={formatCount(totals.trades)}
            hint={data.pre_open_trades ? `${data.pre_open_trades} pre-open fill(s) counted in the 11:00 bucket` : undefined} />
          <SummaryItem label="Shares" value={formatCount(totals.quantity)} />
          <SummaryItem label="Turnover" value={`Rs ${formatNprCompact(totals.turnover)}`} hint="Tracked companies only" />
          <div className="ml-auto">{data.checks.length > 0 && <ChecksChip checks={data.checks} />}</div>
        </div>
      )}

      {!data && loading ? (
        <div className="skeleton h-[420px]" />
      ) : !data?.date ? (
        <div className="card py-10 text-center text-sm text-text-muted">No sessions with trade times are stored yet.</div>
      ) : companies.length === 0 ? (
        <div className="card py-10 text-center text-sm text-text-muted">No tracked company matches “{search}”.</div>
      ) : (
        <SessionGrid
          companies={companies}
          buckets={data.buckets}
          minutes={data.minutes}
          tab={tab}
          density={density}
          loading={loading}
          jumpToLatest={live}
          session={data.date}
        />
      )}
    </div>
  );
}
