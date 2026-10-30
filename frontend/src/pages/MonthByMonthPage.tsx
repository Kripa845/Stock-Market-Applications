// NEPSE month by month: a BS year x BS month heat grid of an index's monthly return (NEPSE or a
// sub-index), newest year on top, with each year's compounded return as a bar and a pinned AVG
// row.  Sibling of the day-by-day page: same sidebar, chips, legend and drag-select.
import { useMemo, useState } from 'react';
import {
  AlertTriangle, CalendarDays, CircleCheck, RefreshCw, SlidersHorizontal, TrendingDown, TrendingUp, X,
} from 'lucide-react';

import { formatPct, formatPrice, formatTradeDate, toNepaliDigits } from '../components/market/format';
import {
  HeatLegend, HeatViewTabs, IndexChips, MiniStat, Segmented, useDragSelect, useIndexParam,
} from '../components/market/heatGrid';
import { heatClass, toneText } from '../components/market/weekday';
import type { MonthlyCell, MonthlyMonthRef, MonthlyReturns, MonthlyYear } from '../api/marketCalendar';
import { useMonthlyReturns } from '../hooks/useMarketCalendar';

const SCALE = 12;              // legend and colour scale clamp at ±12%
const YEAR_COL = 104;
const TILE = 64;
const RETURN_COL = 120;
const HEADER_H = 56;

type Labels = 'np' | 'en';
// Only the position: the cell is read from the current data, so switching index never shows a stale tile.
type Hover = { year: number; month: number; x: number; y: number } | null;

const key = (year: number, month: number) => `${year}-${String(month).padStart(2, '0')}`;

function monthLabel(ref: MonthlyMonthRef, labels: Labels) {
  return labels === 'np' ? <span className="font-devanagari">{ref.label_np}</span> : ref.label;
}

const yearLabel = (year: number) => toNepaliDigits(year);

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

function Stats({ data, labels }: { data: MonthlyReturns; labels: Labels }) {
  const { best_year: best, worst_year: worst, strongest_month: strongest, months_up, months_counted } = data.stats;
  const upShare = months_counted ? (months_up / months_counted) * 100 : null;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1">
      <MiniStat label="Best year" icon={<TrendingUp size={14} />} iconClass="bg-up/10 text-up"
        value={formatPct(best?.year_return)} valueClass={toneText(best?.year_return)}
        sub={best ? <span className="font-devanagari">{yearLabel(best.year)}{best.partial && '*'}</span> : 'Needs a full year'} />
      <MiniStat label="Worst year" icon={<TrendingDown size={14} />} iconClass="bg-down/10 text-down"
        value={formatPct(worst?.year_return)} valueClass={toneText(worst?.year_return)}
        sub={worst ? <span className="font-devanagari">{yearLabel(worst.year)}{worst.partial && '*'}</span> : 'Needs two years'} />
      <MiniStat label="Strongest month on average" icon={<CalendarDays size={14} />} iconClass="bg-accent/15 text-accent"
        value={formatPct(strongest?.average_pct)} valueClass={toneText(strongest?.average_pct)}
        sub={strongest ? <>{monthLabel(strongest, labels)} · {strongest.years} year{strongest.years > 1 ? 's' : ''}</> : 'Needs a closed month'} />
      <MiniStat label="Months that closed up" icon={<CircleCheck size={14} />} iconClass="bg-up/10 text-up"
        value={upShare == null ? '—' : `${Math.round(upShare)}%`}
        sub={<>
          {months_up} of {months_counted} months
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-bg-border">
            <div className="h-full rounded-full bg-up" style={{ width: `${upShare ?? 0}%` }} />
          </div>
        </>} />
    </div>
  );
}

function SidebarBody({ data, index, onIndex, labels, onLabels }: {
  data: MonthlyReturns | undefined; index: string; onIndex: (code: string) => void;
  labels: Labels; onLabels: (l: Labels) => void;
}) {
  return (
    <div className="space-y-5">
      <Segmented label="Month names" value={labels} onChange={onLabels} options={[
        { value: 'np', label: 'नेपाली महिना', className: 'font-devanagari' },
        { value: 'en', label: 'English months' },
      ]} />

      {data && <Stats data={data} labels={labels} />}

      <IndexChips indices={data?.indices} index={index} onIndex={onIndex} />

      <HeatLegend scale={SCALE} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Grid
// ---------------------------------------------------------------------------

function Tooltip({ hover, data, labels }: { hover: Hover; data: MonthlyReturns; labels: Labels }) {
  if (!hover) return null;
  const cell = data.years.find((y) => y.year === hover.year)?.months[hover.month - 1] ?? null;
  const ref = data.months[hover.month - 1];
  const left = Math.min(hover.x + 14, window.innerWidth - 240);
  const top = hover.y + 16 + 140 > window.innerHeight ? hover.y - 140 : hover.y + 16;
  return (
    <div className="pointer-events-none fixed z-50 w-[224px] rounded-xl border border-bg-border bg-bg-card p-3 text-xs shadow-xl"
      style={{ left, top }}>
      <p className="text-sm font-semibold text-text-primary">
        {monthLabel(ref, labels)} <span className="font-devanagari">{yearLabel(hover.year)}</span>
      </p>
      <p className="text-text-secondary">{ref.label} {hover.year}{cell?.partial ? ' · partial' : ''}</p>
      {cell?.close != null ? (
        <div className="mt-2 space-y-0.5 font-mono">
          <p className="flex justify-between"><span className="font-sans text-text-secondary">Close {formatTradeDate(cell.close_date)}</span>
            <span className="font-semibold text-text-primary">{formatPrice(cell.close)}</span></p>
          <p className="flex justify-between"><span className="font-sans text-text-secondary">Return</span>
            <span className={`font-semibold ${toneText(cell.return_pct)}`}>{formatPct(cell.return_pct)}</span></p>
          {cell.previous_close != null && (
            <p className="flex justify-between text-text-secondary"><span className="font-sans">Prev. month close</span>
              <span>{formatPrice(cell.previous_close)}</span></p>
          )}
        </div>
      ) : (
        <p className="mt-2 text-text-secondary">
          {!cell ? (hover.year > data.current.year || (hover.year === data.current.year && hover.month > data.current.month)
            ? 'Upcoming' : 'Before the stored index history') : 'No session stored'}
        </p>
      )}
    </div>
  );
}

function Tile({ year, month, cell, selected, onHover, onDown }: {
  year: number; month: number; cell: MonthlyCell | null; selected: boolean;
  onHover: (h: Hover) => void; onDown: (e: React.PointerEvent, key: string) => void;
}) {
  const pct = cell?.return_pct ?? null;
  const hover = (e: React.PointerEvent) => onHover({ year, month, x: e.clientX, y: e.clientY });
  return (
    <button type="button" data-sel={pct != null ? key(year, month) : undefined}
      onPointerDown={(e) => pct != null && onDown(e, key(year, month))}
      onPointerEnter={hover} onPointerMove={hover} onPointerLeave={() => onHover(null)}
      aria-label={`${year}-${month}: ${pct != null ? formatPct(pct) : 'no data'}`}
      className={`flex h-12 items-center justify-center rounded-xl transition-transform duration-150 hover:z-20 hover:scale-105 ${
        heatClass(pct, SCALE)} ${!cell ? 'opacity-40' : ''} ${selected ? 'z-10 ring-2 ring-accent ring-offset-2 ring-offset-bg-card' : ''}`}>
      {pct != null && (
        <span className="font-mono text-[11.5px] font-semibold">
          {formatPct(pct)}{cell?.partial && <span title="Partial month">*</span>}
        </span>
      )}
    </button>
  );
}

function YearLabel({ row }: { row: MonthlyYear }) {
  const tone = row.year_return == null ? 'text-text-muted/50' : row.year_return > 0 ? 'text-up' : row.year_return < 0 ? 'text-down' : 'text-text-muted';
  return (
    <div className="sticky left-0 z-30 flex h-12 items-center gap-2 bg-bg-card pr-2" style={{ width: YEAR_COL }}>
      <p className="font-devanagari text-[15px] font-semibold text-text-primary">
        {yearLabel(row.year)}{row.partial && <span className="text-text-muted" title="Partial year">*</span>}
      </p>
      <span className={`flex flex-1 items-center ${tone}`}>
        <span className="flex-1 border-t-2 border-dotted border-current" />
        <span className="-ml-1 text-[9px]">▶</span>
      </span>
    </div>
  );
}

function YearReturn({ row, maxAbs }: { row: MonthlyYear; maxAbs: number }) {
  const pct = row.year_return;
  const width = pct == null || !maxAbs ? 0 : (Math.abs(pct) / maxAbs) * 100;
  return (
    <div className="flex h-12 flex-col justify-center gap-1 pl-2" style={{ width: RETURN_COL }}>
      <span className={`font-mono text-[12.5px] font-semibold ${toneText(pct)}`}>
        {formatPct(pct)}{row.partial && pct != null && <span title="Partial year">*</span>}
      </span>
      <div className="h-1.5 w-full rounded-full bg-bg-border/50">
        <div className={`h-full rounded-full ${pct != null && pct < 0 ? 'bg-down' : 'bg-up'}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function Grid({ data, labels, selected, onDown, onHover }: {
  data: MonthlyReturns; labels: Labels; selected: Set<string>;
  onDown: (e: React.PointerEvent, key: string) => void; onHover: (h: Hover) => void;
}) {
  const maxAbs = Math.max(0, ...data.years.map((y) => Math.abs(y.year_return ?? 0)));
  const currentCol = data.current.month;
  const sticky = 'sticky z-20 bg-bg-card';
  return (
    <div className="relative grid gap-x-2 gap-y-2"
      style={{
        gridTemplateColumns: `${YEAR_COL}px repeat(12, ${TILE}px) ${RETURN_COL}px`,
        gridTemplateRows: `${HEADER_H}px auto repeat(${data.years.length}, auto)`,
      }}>
      {/* Current month column outline: absolute, so it takes no grid cells; above the pinned rows,
          below the sticky year labels. */}
      <div className="pointer-events-none absolute -inset-1 z-[25] rounded-2xl border-2 border-up/60"
        style={{ gridColumn: `${currentCol + 1} / span 1`, gridRow: '1 / -1' }} />

      <div className={`${sticky} left-0 top-0 z-40 flex items-end pb-3 text-xs font-semibold uppercase tracking-[0.14em] text-text-muted`}>
        Year
      </div>
      {data.months.map((m) => (
        <div key={m.month} className={`${sticky} top-0 flex flex-col items-center justify-end pb-2`}>
          {m.month === currentCol && (
            <span className="mb-0.5 rounded-full bg-up/15 px-1.5 text-[8.5px] font-semibold uppercase tracking-[0.1em] text-up">
              Current month
            </span>
          )}
          <span className={`text-sm font-semibold ${m.month === currentCol ? 'text-text-primary' : 'text-text-secondary'}`}>
            {monthLabel(m, labels)}
          </span>
        </div>
      ))}
      <div className={`${sticky} top-0 flex items-end pb-3 pl-2 text-xs font-semibold uppercase tracking-[0.14em] text-text-muted`}>
        Year return
      </div>

      {/* Pinned AVG row; the padding covers the row gap while scrolled. */}
      <div className={`${sticky} left-0 z-40 -mt-2 flex items-center pt-2 text-xs font-semibold uppercase tracking-[0.14em] text-text-muted`}
        style={{ top: HEADER_H }}>
        Avg
      </div>
      {data.avg_row.map((avg, i) => (
        <div key={i} className={`${sticky} -mt-2 pb-1 pt-2`} style={{ top: HEADER_H }}
          title={avg ? `${data.months[i].label}: average of ${avg.years} closed month${avg.years > 1 ? 's' : ''}` : 'No closed month yet'}>
          <div className={`flex h-7 items-center justify-center rounded-lg font-mono text-[11px] font-semibold ${heatClass(avg?.average_pct ?? null, SCALE)}`}>
            {avg ? formatPct(avg.average_pct) : ''}
          </div>
        </div>
      ))}
      <div className={`${sticky} -mt-2 pt-2`} style={{ top: HEADER_H }} />

      {data.years.map((row) => (
        <YearRow key={row.year} row={row} maxAbs={maxAbs} selected={selected} onDown={onDown} onHover={onHover} />
      ))}
    </div>
  );
}

function YearRow({ row, maxAbs, selected, onDown, onHover }: {
  row: MonthlyYear; maxAbs: number; selected: Set<string>;
  onDown: (e: React.PointerEvent, key: string) => void; onHover: (h: Hover) => void;
}) {
  return (
    <>
      <YearLabel row={row} />
      {row.months.map((cell, i) => (
        <Tile key={i} year={row.year} month={i + 1} cell={cell} selected={selected.has(key(row.year, i + 1))}
          onDown={onDown} onHover={onHover} />
      ))}
      <YearReturn row={row} maxAbs={maxAbs} />
    </>
  );
}

// ---------------------------------------------------------------------------
// Selection detail
// ---------------------------------------------------------------------------

type Picked = MonthlyCell & { year: number; key: string };

function SelectionCard({ data, from, to, labels, onClose }: {
  data: MonthlyReturns; from: string; to: string; labels: Labels; onClose: () => void;
}) {
  const picked: Picked[] = data.years
    .flatMap((y) => y.months.map((c) => (c ? { ...c, year: y.year, key: key(y.year, c.month) } : null)))
    .filter((c): c is Picked => c != null && c.return_pct != null && c.key >= from && c.key <= to)
    .sort((a, b) => a.key.localeCompare(b.key));
  const first = picked[0];
  const last = picked[picked.length - 1];
  // Exact from closes when the first month's opening close is known; otherwise compounded.
  const cumulative = !picked.length ? null
    : first.previous_close != null && last.close != null
      ? (last.close / first.previous_close - 1) * 100
      : (picked.reduce((g, c) => g * (1 + (c.return_pct as number) / 100), 1) - 1) * 100;
  const best = picked.reduce<Picked | null>((b, c) => (!b || (c.return_pct as number) > (b.return_pct as number) ? c : b), null);
  const worst = picked.reduce<Picked | null>((w, c) => (!w || (c.return_pct as number) < (w.return_pct as number) ? c : w), null);
  const up = picked.filter((c) => (c.return_pct as number) > 0).length;
  const name = (c: Picked) => <>{monthLabel(data.months[c.month - 1], labels)} <span className="font-devanagari">{yearLabel(c.year)}</span></>;
  return (
    <div className="card fixed inset-x-3 bottom-3 z-40 animate-fade-in !rounded-2xl !p-5 shadow-2xl sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-[320px]">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-secondary">{data.index.name} · selection</p>
          {first && (
            <p className="mt-1 text-sm font-semibold text-text-primary">
              {name(first)}{first !== last && <> → {name(last)}</>}
            </p>
          )}
        </div>
        <button type="button" onClick={onClose} aria-label="Clear selection"
          className="rounded-md p-1 text-text-secondary hover:text-text-primary"><X size={16} /></button>
      </div>
      {picked.length ? (
        <>
          <p className={`mt-3 font-mono text-3xl font-semibold ${toneText(cumulative)}`}>{formatPct(cumulative)}</p>
          <p className="text-[11px] text-text-secondary">
            Compounded over {picked.length} month{picked.length > 1 ? 's' : ''} · {up} up, {picked.length - up} down or flat
          </p>
          <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <span className="text-text-secondary">Start (prev. close)</span>
            <span className="text-right font-mono text-text-primary">{formatPrice(first.previous_close)}</span>
            <span className="text-text-secondary">End close</span>
            <span className="text-right font-mono text-text-primary">{formatPrice(last.close)}</span>
            {picked.length > 1 && best && worst && (
              <>
                <span className="text-text-secondary">Best month</span>
                <span className="text-right"><span className="text-text-secondary">{name(best)}</span>{' '}
                  <span className={`font-mono ${toneText(best.return_pct)}`}>{formatPct(best.return_pct)}</span></span>
                <span className="text-text-secondary">Worst month</span>
                <span className="text-right"><span className="text-text-secondary">{name(worst)}</span>{' '}
                  <span className={`font-mono ${toneText(worst.return_pct)}`}>{formatPct(worst.return_pct)}</span></span>
              </>
            )}
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm text-text-secondary">No stored months in this selection.</p>
      )}
      <p className="mt-3 text-[10px] text-text-muted">Drag across tiles or shift-click to extend · Esc to clear</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function MonthByMonthPage() {
  const [index, setIndex] = useIndexParam();
  const [labels, setLabels] = useState<Labels>('np');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [hover, setHover] = useState<Hover>(null);
  const { range, onDown, onGridMove, dragging, clear } = useDragSelect();

  const { data, isLoading, isFetching, error, refetch } = useMonthlyReturns(index);
  const detail = (error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;

  const [from, to] = range ?? [null, null];
  const selected = useMemo(() => {
    const set = new Set<string>();
    if (!data || !from || !to) return set;
    for (const y of data.years) for (const c of y.months) {
      const k = c && c.return_pct != null ? key(y.year, c.month) : null;
      if (k && k >= from && k <= to) set.add(k);
    }
    return set;
  }, [data, from, to]);

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <aside className="shrink-0 lg:w-[220px]">
        <HeatViewTabs index={index} />
        <div className="mt-5 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-text-muted">{data?.index.code ?? index} · whole market</p>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-text-primary">NEPSE month by month</h1>
            <p className="mt-2 text-xs leading-snug text-text-secondary">
              Each month = its last close against the previous month's last close. * partial
            </p>
          </div>
          <button type="button" onClick={() => setDrawerOpen((o) => !o)} aria-expanded={drawerOpen}
            className="flex items-center gap-1.5 rounded-xl border border-bg-border bg-bg-card px-3 py-2 text-xs font-semibold text-text-primary lg:hidden">
            <SlidersHorizontal size={14} /> {drawerOpen ? 'Hide' : 'Options'}
          </button>
        </div>
        <div className={`mt-5 ${drawerOpen ? 'block animate-fade-in' : 'hidden'} lg:block`}>
          <SidebarBody data={data} index={index} onIndex={setIndex} labels={labels} onLabels={setLabels} />
        </div>
      </aside>

      <main className="min-w-0 flex-1 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-text-secondary">
          <span>{data ? <>{data.index.name} · sessions stored since {formatTradeDate(data.history_from)}</> : ' '}</span>
          <button type="button" onClick={() => refetch()}
            className="flex items-center gap-2 rounded-xl border border-bg-border bg-bg-card px-4 py-2 text-sm font-semibold text-text-primary hover:bg-bg-elevated">
            <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>

        {error ? (
          <div role="alert" className="flex items-center gap-2 rounded-md border border-down/30 bg-down/10 px-4 py-3 text-sm text-down">
            <AlertTriangle size={15} /> {detail ?? 'Could not load the index history.'}
          </div>
        ) : isLoading || !data ? (
          <div className="skeleton h-[520px] rounded-2xl" />
        ) : (
          <>
            {/* Scrolls both ways inside the card so the header and AVG rows can stay pinned. */}
            <section className={`card max-h-[calc(100vh-170px)] overflow-auto !rounded-2xl !p-6 !pt-0 transition-opacity ${isFetching ? 'opacity-70' : ''}`}
              onPointerMove={onGridMove} onPointerLeave={() => setHover(null)}>
              <div className="w-max pt-4">
                <Grid data={data} labels={labels} selected={selected} onDown={onDown} onHover={setHover} />
              </div>
            </section>
            {data.notes.map((note) => <p key={note} className="text-xs text-text-muted">{note}</p>)}
          </>
        )}
      </main>

      {data && <Tooltip hover={dragging.current ? null : hover} data={data} labels={labels} />}
      {data && from && to && <SelectionCard data={data} from={from} to={to} labels={labels} onClose={clear} />}
    </div>
  );
}
