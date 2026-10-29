// Floor Sheet Summary: every tracked company's trades for one session as a symbol x time-bucket
// grid (quantity, trades, turnover, close, VWAP, change per cell), with an OHLC view and the
// server's validation checks.  The grid is windowed in both directions: a full market day
// (279 stocks x 240 one-minute buckets) would otherwise be ~67k cells in the DOM.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, MinusCircle, RefreshCw, Search, XCircle } from 'lucide-react';

import PageHeader from '../components/common/PageHeader';
import { changeTone, formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from '../components/market/format';
import { BUCKET_MINUTES, type BucketMinutes, type GridCell, type GridCheck, type GridCompany } from '../api/floorsheetGrid';
import { useFloorsheetGrid } from '../hooks/useFloorsheetGrid';

type Tab = 'floorsheet' | 'ohlc';

const ROW_H = 76;
const COL_W = 118;
const HEAD_H = 34;
const SN_W = 40;
const SYMBOL_W = 86;
const DAY_W = 96;
const LEFT_W = SN_W + SYMBOL_W + DAY_W;
const OVERSCAN = 3;
// NEPSE's daily circuit; the DAY % bar is full at ±10%.
const CIRCUIT_PCT = 10;

const toneClass = {
  up: 'bg-up/10 text-up',
  down: 'bg-down/10 text-down',
  flat: 'text-text-secondary',
} as const;

function bucketEnd(start: string, minutes: number) {
  const [h, m] = start.split(':').map(Number);
  // The 45M grid's last bucket stops at the 15:00 close.
  const end = Math.min(h * 60 + m + minutes, 15 * 60);
  return `${String(Math.floor(end / 60)).padStart(2, '0')}:${String(end % 60).padStart(2, '0')}`;
}

function cellTitle(company: GridCompany, cell: GridCell, label: string) {
  return [
    `${company.symbol} ${label}`,
    `Open ${formatPrice(cell.open)}  High ${formatPrice(cell.high)}  Low ${formatPrice(cell.low)}  Close ${formatPrice(cell.close)}`,
    `VWAP ${formatPrice(cell.vwap)}  Change ${formatPct(cell.change_pct)}`,
    `Quantity ${formatCount(cell.quantity)}  Trades ${formatCount(cell.trades)}  Turnover Rs ${formatCount(cell.turnover)}`,
  ].join('\n');
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card">
      <p className="text-xs text-text-secondary">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-text-primary">{value}</p>
      {hint && <p className="text-[11px] text-text-muted">{hint}</p>}
    </div>
  );
}

function DayChange({ company }: { company: GridCompany }) {
  const pct = company.day_change_pct;
  const tone = changeTone(pct);
  const width = pct == null ? 0 : Math.min(Math.abs(pct) / CIRCUIT_PCT, 1) * 100;
  const title = [
    `Close ${formatPrice(company.session_close)} vs previous ${formatPrice(company.prev_close)}`,
    company.published_change_pct != null ? `Published ${formatPct(company.published_change_pct)}` : 'Not yet published',
  ].join('\n');
  return (
    <div className="flex h-full flex-col justify-center gap-1 px-2" title={title}>
      <span className={`font-mono text-xs font-semibold ${tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-text-secondary'}`}>
        {formatPct(pct)}
      </span>
      <span className="relative block h-1.5 w-full rounded-full bg-bg-border">
        <span
          className={`absolute top-0 h-full rounded-full ${tone === 'down' ? 'right-1/2 bg-down' : 'left-1/2 bg-up'}`}
          style={{ width: `${width / 2}%` }}
        />
      </span>
    </div>
  );
}

function FloorCell({ cell }: { cell: GridCell }) {
  return (
    <>
      <div className="flex items-baseline justify-between gap-1">
        <span className="font-mono text-xs font-semibold">{formatPrice(cell.close)}</span>
        <span className="font-mono text-[10px]">{formatPct(cell.change_pct)}</span>
      </div>
      <div className="font-mono text-[10px] text-text-muted">VWAP {formatPrice(cell.vwap)}</div>
      <div className="font-mono text-[10px] text-text-secondary">{formatCount(cell.quantity)} · {cell.trades}t</div>
      <div className="font-mono text-[10px] text-text-muted">Rs {formatNprCompact(cell.turnover)}</div>
    </>
  );
}

function OhlcCell({ cell }: { cell: GridCell }) {
  return (
    <div className="grid grid-cols-[auto_1fr] gap-x-1.5 font-mono text-[10px] leading-[15px]">
      <span className="text-text-muted">O</span><span className="text-right text-text-secondary">{formatPrice(cell.open)}</span>
      <span className="text-text-muted">H</span><span className="text-right text-text-secondary">{formatPrice(cell.high)}</span>
      <span className="text-text-muted">L</span><span className="text-right text-text-secondary">{formatPrice(cell.low)}</span>
      <span className="text-text-muted">C</span><span className="text-right font-semibold">{formatPrice(cell.close)}</span>
    </div>
  );
}

interface GridProps {
  companies: GridCompany[];
  buckets: string[];
  minutes: number;
  tab: Tab;
}

function SessionGrid({ companies, buckets, minutes, tab }: GridProps) {
  const scroller = useRef<HTMLDivElement>(null);
  const frame = useRef(0);
  const [view, setView] = useState({ top: 0, left: 0, width: 0, height: 0 });

  const measure = useCallback(() => {
    const el = scroller.current;
    if (!el) return;
    setView({ top: el.scrollTop, left: el.scrollLeft, width: el.clientWidth, height: el.clientHeight });
  }, []);

  useLayoutEffect(() => {
    measure();
    const el = scroller.current;
    if (!el) return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [measure]);

  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  const onScroll = () => {
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(measure);
  };

  const cellMaps = useMemo(
    () => companies.map((c) => new Map(c.cells.map((cell) => [cell.i, cell]))),
    [companies],
  );

  const firstRow = Math.max(0, Math.floor(view.top / ROW_H) - OVERSCAN);
  const lastRow = Math.min(companies.length, Math.ceil((view.top + view.height) / ROW_H) + OVERSCAN);
  const firstCol = Math.max(0, Math.floor(view.left / COL_W) - OVERSCAN);
  const lastCol = Math.min(buckets.length, Math.ceil((view.left + view.width - LEFT_W) / COL_W) + OVERSCAN);
  const cols: number[] = [];
  for (let c = firstCol; c < lastCol; c += 1) cols.push(c);

  const width = LEFT_W + buckets.length * COL_W;
  const stickyLeft = 'sticky left-0 z-[2] flex shrink-0 bg-bg-card';

  return (
    <div
      ref={scroller}
      onScroll={onScroll}
      className="relative h-[calc(100vh-330px)] min-h-[420px] overflow-auto rounded-md border border-bg-border bg-bg-card"
    >
      <div style={{ width, height: HEAD_H + companies.length * ROW_H }} className="relative">
        {/* Header row: sticky to the top; its first block also sticks to the left. */}
        <div className="sticky top-0 z-[3] border-b border-bg-border bg-bg-elevated" style={{ height: HEAD_H, width }}>
          <div className={`${stickyLeft} h-full items-center bg-bg-elevated text-[11px] font-medium text-text-muted`} style={{ width: LEFT_W }}>
            <span className="px-2 text-right" style={{ width: SN_W }}>S.N</span>
            <span className="px-2" style={{ width: SYMBOL_W }}>Symbol</span>
            <span className="border-r border-bg-border px-2" style={{ width: DAY_W }}>DAY %</span>
          </div>
          {cols.map((c) => (
            <div
              key={c}
              className="absolute top-0 flex h-full items-center justify-center border-l border-bg-border font-mono text-[11px] text-text-secondary"
              style={{ left: LEFT_W + c * COL_W, width: COL_W }}
              title={`${buckets[c]}–${bucketEnd(buckets[c], minutes)} NPT`}
            >
              {buckets[c]}
            </div>
          ))}
        </div>

        {companies.slice(firstRow, lastRow).map((company, offset) => {
          const r = firstRow + offset;
          const cells = cellMaps[r];
          return (
            <div
              key={company.company_id}
              className="absolute left-0 border-b border-bg-border"
              style={{ top: HEAD_H + r * ROW_H, height: ROW_H, width }}
            >
              <div className={stickyLeft} style={{ width: LEFT_W, height: ROW_H }}>
                <span className="self-center px-2 text-right font-mono text-[11px] text-text-muted" style={{ width: SN_W }}>{r + 1}</span>
                <span className="flex flex-col justify-center px-2" style={{ width: SYMBOL_W }}>
                  <Link to={`/companies/${company.symbol}`} className="truncate text-xs font-semibold text-text-primary hover:underline" title={company.name}>
                    {company.symbol}
                  </Link>
                  <span className="font-mono text-[10px] text-text-muted">{formatPrice(company.session_close)}</span>
                </span>
                <span className="border-r border-bg-border" style={{ width: DAY_W }}>
                  <DayChange company={company} />
                </span>
              </div>
              {cols.map((c) => {
                const cell = cells.get(c);
                if (!cell) return null;
                return (
                  <div
                    key={c}
                    className={`absolute top-0 flex flex-col justify-center gap-0.5 border-l border-bg-border px-2 ${toneClass[changeTone(cell.change_pct)]}`}
                    style={{ left: LEFT_W + c * COL_W, width: COL_W, height: ROW_H }}
                    title={cellTitle(company, cell, `${buckets[c]}–${bucketEnd(buckets[c], minutes)}`)}
                  >
                    {tab === 'floorsheet' ? <FloorCell cell={cell} /> : <OhlcCell cell={cell} />}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const checkIcon = {
  pass: <CheckCircle2 size={14} className="text-up" />,
  fail: <XCircle size={14} className="text-down" />,
  'n/a': <MinusCircle size={14} className="text-text-muted" />,
} as const;

function ChecksPanel({ checks }: { checks: GridCheck[] }) {
  const [open, setOpen] = useState(false);
  const failed = checks.filter((c) => c.status === 'fail');
  const passed = checks.filter((c) => c.status === 'pass').length;
  return (
    <div className="card">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 text-left text-sm">
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="font-semibold text-text-primary">Validation</span>
        <span className="text-xs text-text-secondary">
          {passed}/{checks.length} pass{failed.length ? ` · ${failed.length} failing` : ''}
        </span>
        <span className="ml-auto flex gap-1">{checks.map((c) => <span key={c.key} title={c.label}>{checkIcon[c.status]}</span>)}</span>
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          {checks.map((check) => (
            <div key={check.key} className="border-t border-bg-border pt-2">
              <div className="flex items-center gap-2 text-xs">
                {checkIcon[check.status]}
                <span className="text-text-primary">{check.label}</span>
                <span className="ml-auto font-mono text-text-muted">{formatCount(check.compared)} compared</span>
              </div>
              {check.note && <p className="mt-1 pl-6 text-[11px] text-text-muted">{check.note}</p>}
              {check.mismatches.length > 0 && (
                <table className="mt-2 ml-6 text-[11px]">
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
              )}
              {check.mismatch_count > check.mismatches.length && (
                <p className="mt-1 pl-6 text-[11px] text-text-muted">
                  Showing {check.mismatches.length} of {check.mismatch_count}. Run <code>manage.py validate_floorsheet_grid</code> for all.
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function FloorsheetSummaryPage() {
  const [date, setDate] = useState('');
  const [minutes, setMinutes] = useState<BucketMinutes>(1);
  const [tab, setTab] = useState<Tab>('floorsheet');
  const [search, setSearch] = useState('');
  const { data, loading, error, reload } = useFloorsheetGrid(date, minutes);

  const companies = useMemo(() => {
    const query = search.trim().toUpperCase();
    const all = data?.companies ?? [];
    return query ? all.filter((c) => c.symbol.includes(query) || c.name.toUpperCase().includes(query)) : all;
  }, [data, search]);

  const traded = data?.companies.filter((c) => c.trades > 0).length ?? 0;
  const totals = useMemo(() => (data?.companies ?? []).reduce(
    (acc, c) => ({ trades: acc.trades + c.trades, turnover: acc.turnover + c.turnover }),
    { trades: 0, turnover: 0 },
  ), [data]);
  const selectedDate = date || data?.date || '';

  return (
    <div className="space-y-4">
      <PageHeader
        title="Floor Sheet Summary"
        subtitle="Tracked companies' trades for one session in time buckets from the 11:00 open."
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

      <div className="card flex flex-wrap items-end gap-3">
        <label className="block">
          <span className="mb-1 block text-xs text-text-secondary">Session</span>
          <span className="flex items-center gap-2">
            <select value={selectedDate} onChange={(e) => setDate(e.target.value)} className="input w-44" disabled={!data?.dates.length}>
              {!selectedDate && <option value="">{loading ? 'Loading…' : 'No sessions'}</option>}
              {(data?.dates ?? []).map((d) => (
                <option key={d} value={d}>{formatTradeDate(d)}{d === data?.dates[0] ? ' (latest)' : ''}</option>
              ))}
            </select>
            {data?.date && (
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                data.status === 'live' ? 'bg-up/15 text-up' : 'bg-bg-elevated text-text-secondary'
              }`}>
                {data.status === 'live' ? 'Live' : 'Stored'}
              </span>
            )}
          </span>
        </label>
        <div>
          <span className="mb-1 block text-xs text-text-secondary">Bucket</span>
          <div className="flex overflow-hidden rounded-md border border-bg-border">
            {BUCKET_MINUTES.map((m) => (
              <button key={m} type="button" onClick={() => setMinutes(m)}
                className={`px-2.5 py-1.5 font-mono text-xs ${m === minutes ? 'bg-bg-elevated text-text-primary' : 'text-text-secondary hover:text-text-primary'}`}>
                {m}M
              </button>
            ))}
          </div>
        </div>
        <label className="block min-w-[200px] flex-1">
          <span className="mb-1 block text-xs text-text-secondary">Search</span>
          <span className="relative block">
            <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Symbol or company" className="input w-full pl-9" />
          </span>
        </label>
        <div className="flex overflow-hidden rounded-md border border-bg-border">
          {([['floorsheet', 'Floor Sheet'], ['ohlc', 'OHLC_DATA']] as const).map(([key, label]) => (
            <button key={key} type="button" onClick={() => setTab(key)}
              className={`px-3 py-1.5 text-xs ${tab === key ? 'bg-bg-elevated text-text-primary' : 'text-text-secondary hover:text-text-primary'}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Stocks" value={data ? `${traded} / ${data.companies.length}` : '—'} hint="traded / tracked companies" />
        <Stat label="Buckets" value={data ? formatCount(data.buckets.length) : '—'} hint={data ? `${data.minutes}M from 11:00` : undefined} />
        <Stat label="Trades" value={data ? formatCount(totals.trades) : '—'}
          hint={data?.pre_open_trades ? `${data.pre_open_trades} pre-open fill(s) counted at 11:00` : undefined} />
        <Stat label="Turnover" value={data ? `Rs ${formatNprCompact(totals.turnover)}` : '—'} hint="tracked companies" />
      </div>

      {data && data.checks.length > 0 && <ChecksPanel checks={data.checks} />}

      {!data && loading ? (
        <div className="skeleton h-[420px]" />
      ) : !data?.date ? (
        <div className="card py-10 text-center text-sm text-text-muted">No sessions with trade times are stored yet.</div>
      ) : companies.length === 0 ? (
        <div className="card py-10 text-center text-sm text-text-muted">No tracked company matches “{search}”.</div>
      ) : (
        <SessionGrid companies={companies} buckets={data.buckets} minutes={data.minutes} tab={tab} />
      )}
    </div>
  );
}
