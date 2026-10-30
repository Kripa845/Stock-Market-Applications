// NEPSE day by day: a month x day-of-month heat grid of an index's daily change (NEPSE or a
// sub-index), in Nepali (BS) or English months, newest month on top.  Every tile is a stored
// session; holidays, weekends and missing days stay as dashed gaps.  Click or drag across tiles
// for the cumulative return over the selection.  Tiles share the Weekday Summary page's look.
import { useMemo, useState } from 'react';
import {
  AlertTriangle, CalendarDays, ChevronUp, CircleCheck, RefreshCw, SlidersHorizontal, TrendingDown, TrendingUp, X,
} from 'lucide-react';

import { formatPct, formatPrice, formatTradeDate, toNepaliDigits } from '../components/market/format';
import {
  HeatLegend, HeatViewTabs, IndexChips, MiniStat, Segmented, useDragSelect, useIndexParam,
} from '../components/market/heatGrid';
import { WEEKDAY_NAMES, heatClass, toneText } from '../components/market/weekday';
import {
  DAY_BY_DAY_MONTH_CHOICES, type DayByDayCalendar, type DayByDayDay, type DayByDayMonth, type DayByDayMonths,
  type DayByDaySummary,
} from '../api/marketCalendar';
import { useDayByDay } from '../hooks/useMarketCalendar';

const MONTH_COL = 168;
const TILE = 76;

// Short tile text for days without a session; weekends and future days stay blank.
const GAP_TEXT: Record<string, string> = { holiday: 'Holiday', pending: 'Awaiting', no_session: 'No session' };
const STATUS_TEXT: Record<string, string> = {
  holiday: 'Holiday', weekend: 'Not a trading day', pending: 'Awaiting the close', no_data: 'Before the stored index history',
  no_session: 'No session stored', future: 'Upcoming', traded: 'Traded',
};
type Hover = { day: DayByDayDay; x: number; y: number } | null;

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

function monthName(ref: { label: string; label_np: string }, calendar: DayByDayCalendar) {
  return calendar === 'bs' && ref.label_np ? <span className="font-devanagari">{ref.label_np}</span> : ref.label;
}

function Stats({ data }: { data: DayByDaySummary }) {
  const { stats, calendar } = data;
  const year = calendar === 'bs' ? toNepaliDigits(stats.year) : stats.year;
  const upShare = stats.sessions ? (stats.up_days / stats.sessions) * 100 : null;
  const best = stats.best_month;
  const worst = stats.worst_month;
  const strongest = stats.strongest_weekday;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1">
      <MiniStat label="Best month this year" icon={<TrendingUp size={14} />} iconClass="bg-up/10 text-up"
        value={formatPct(best?.change_pct)} valueClass={toneText(best?.change_pct)}
        sub={best ? <>{monthName(best, calendar)}{best.partial && '*'} · {best.up_days} of {best.sessions} days up</> : <>No month in {year} yet</>} />
      <MiniStat label="Worst month this year" icon={<TrendingDown size={14} />} iconClass="bg-down/10 text-down"
        value={formatPct(worst?.change_pct)} valueClass={toneText(worst?.change_pct)}
        sub={worst ? <>{monthName(worst, calendar)}{worst.partial && '*'} · {worst.up_days} of {worst.sessions} days up</> : 'Needs two months'} />
      <MiniStat label="Strongest day on average" icon={<CalendarDays size={14} />} iconClass="bg-accent/15 text-accent"
        value={formatPct(strongest?.average_pct)} valueClass={toneText(strongest?.average_pct)}
        sub={strongest ? `${WEEKDAY_NAMES[strongest.weekday]} · ${strongest.sessions} sessions` : 'Needs two sessions per weekday'} />
      <MiniStat label="Days that closed up" icon={<CircleCheck size={14} />} iconClass="bg-up/10 text-up"
        value={upShare == null ? '—' : `${Math.round(upShare)}%`}
        sub={<>
          {stats.up_days} of {stats.sessions} sessions
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-bg-border">
            <div className="h-full rounded-full bg-up" style={{ width: `${upShare ?? 0}%` }} />
          </div>
        </>} />
    </div>
  );
}

function SidebarBody({ data, index, onIndex, calendar, onCalendar, months, onMonths }: {
  data: DayByDaySummary | undefined; index: string; onIndex: (code: string) => void;
  calendar: DayByDayCalendar; onCalendar: (c: DayByDayCalendar) => void;
  months: DayByDayMonths; onMonths: (m: DayByDayMonths) => void;
}) {
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Segmented label="Calendar" value={calendar} onChange={onCalendar} options={[
          { value: 'bs', label: 'नेपाली महिना', className: 'font-devanagari' },
          { value: 'ad', label: 'English months' },
        ]} />
        <Segmented label="Months shown" value={months} onChange={onMonths}
          options={DAY_BY_DAY_MONTH_CHOICES.map((m) => ({ value: m, label: `${m}M`, className: 'font-mono' }))} />
      </div>

      {data && <Stats data={data} />}

      <IndexChips indices={data?.indices} index={index} onIndex={onIndex} />

      <HeatLegend />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Grid
// ---------------------------------------------------------------------------

function Tooltip({ hover, indexName }: { hover: Hover; indexName: string }) {
  if (!hover) return null;
  const { day } = hover;
  const left = Math.min(hover.x + 14, window.innerWidth - 240);
  const top = hover.y + 16 + 150 > window.innerHeight ? hover.y - 150 : hover.y + 16;
  return (
    <div className="pointer-events-none fixed z-50 w-[224px] rounded-xl border border-bg-border bg-bg-card p-3 text-xs shadow-xl"
      style={{ left, top }}>
      <p className="font-devanagari text-sm font-semibold text-text-primary">{day.bs_label_np}</p>
      <p className="text-text-secondary">{WEEKDAY_NAMES[day.weekday]}, {formatTradeDate(day.date)} · {day.bs_label}</p>
      {day.close != null ? (
        <div className="mt-2 space-y-0.5 font-mono">
          <p className="flex justify-between"><span className="font-sans text-text-secondary">{indexName} close</span>
            <span className="font-semibold text-text-primary">{formatPrice(day.close)}</span></p>
          <p className="flex justify-between"><span className="font-sans text-text-secondary">Change</span>
            <span className={`font-semibold ${toneText(day.change_pct)}`}>{formatPct(day.change_pct)}</span></p>
          {day.previous_close != null && (
            <p className="flex justify-between text-text-secondary"><span className="font-sans">Prev. {formatTradeDate(day.previous_date)}</span>
              <span>{formatPrice(day.previous_close)}</span></p>
          )}
        </div>
      ) : (
        <p className="mt-2 text-text-secondary">{STATUS_TEXT[day.status]}{day.holiday ? `: ${day.holiday}` : ''}</p>
      )}
    </div>
  );
}

function Tile({ day, isToday, selected, onHover, onDown }: {
  day: DayByDayDay; isToday: boolean; selected: boolean;
  onHover: (h: Hover) => void; onDown: (e: React.PointerEvent, date: string) => void;
}) {
  const pct = day.status === 'traded' ? day.change_pct : null;
  // Gaps reuse heatClass's dashed box; weekends, future days and pre-history days fade out.
  const faded = day.status === 'weekend' || day.status === 'future' || day.status === 'no_data';
  return (
    <button type="button" data-sel={day.date}
      onPointerDown={(e) => onDown(e, day.date)}
      onPointerEnter={(e) => onHover({ day, x: e.clientX, y: e.clientY })}
      onPointerMove={(e) => onHover({ day, x: e.clientX, y: e.clientY })}
      onPointerLeave={() => onHover(null)}
      aria-label={`${day.bs_label}, ${formatTradeDate(day.date)}: ${pct != null ? formatPct(pct) : STATUS_TEXT[day.status]}`}
      className={`flex h-14 items-center justify-center rounded-xl transition-transform duration-150 hover:z-20 hover:scale-105 ${
        heatClass(pct)} ${faded ? 'opacity-40' : ''} ${
        selected ? 'z-10 ring-2 ring-accent ring-offset-2 ring-offset-bg-card'
          : isToday ? 'ring-2 ring-accent/60 ring-offset-2 ring-offset-bg-card' : ''
      }`}>
      {pct != null ? (
        <span className="flex items-center gap-1 font-mono text-[12.5px] font-semibold">
          <span className="text-[9px]">{pct > 0 ? '▲' : pct < 0 ? '▼' : '■'}</span>
          {formatPct(pct)}
        </span>
      ) : (
        <span className="text-[10.5px]">{GAP_TEXT[day.status] ?? ''}</span>
      )}
    </button>
  );
}

function badge(month: DayByDayMonth, data: DayByDaySummary) {
  const { best_month: best, worst_month: worst } = data.stats;
  if (month.is_current) return { text: 'Current month', cls: 'bg-accent/15 text-accent' };
  if (best && best.label === month.label) return { text: 'Best month', cls: 'bg-up/15 text-up' };
  if (worst && worst.label === month.label) return { text: 'Worst month', cls: 'bg-down/15 text-down' };
  return null;
}

function MonthLabel({ month, data }: { month: DayByDayMonth; data: DayByDaySummary }) {
  const tag = badge(month, data);
  return (
    <div className="sticky left-0 z-30 flex h-14 items-center gap-2 bg-bg-card pr-3" style={{ width: MONTH_COL }}>
      <div className="min-w-0">
        <p className={`truncate text-[15px] font-semibold text-text-primary ${data.calendar === 'bs' ? 'font-devanagari' : ''}`}>
          {data.calendar === 'bs' ? month.label_np : month.label}
        </p>
        <div className="flex items-center gap-1.5">
          <span className={`font-mono text-xs font-semibold ${toneText(month.change_pct)}`}>
            {formatPct(month.change_pct)}{month.partial && month.change_pct != null && <span title="Partial month">*</span>}
          </span>
          {tag && <span className={`truncate rounded-full px-2 py-px text-[10px] font-semibold ${tag.cls}`}>{tag.text}</span>}
        </div>
      </div>
      {/* Dotted lead-in towards the row's tiles. */}
      <span className="flex flex-1 items-center text-text-muted/50">
        <span className="flex-1 border-t-2 border-dotted border-current" />
        <span className="-ml-1 text-[9px]">▶</span>
      </span>
    </div>
  );
}

function Grid({ data, selected, onDown, onHover }: {
  data: DayByDaySummary; selected: Set<string>;
  onDown: (e: React.PointerEvent, date: string) => void; onHover: (h: Hover) => void;
}) {
  const cols = data.max_days;
  const digit = (n: number) => (data.calendar === 'bs' ? toNepaliDigits(n) : String(n));
  const todayDay = data.months[0]?.is_current ? data.today_day : null;
  return (
    <div className="grid gap-2" style={{ gridTemplateColumns: `${MONTH_COL}px repeat(${cols}, ${TILE}px)` }}>
      <div className="sticky left-0 z-30 flex items-end gap-1 bg-bg-card pb-3 text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
        <ChevronUp size={13} /> Month
      </div>
      {Array.from({ length: cols }, (_, i) => i + 1).map((n) => (
        <div key={n}
          className={`flex flex-col items-center justify-center rounded-xl py-2 ${n === todayDay ? 'border border-accent/50 bg-accent/10' : ''}`}>
          {n === todayDay && <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-accent">Today</span>}
          <span className={`text-sm font-semibold ${data.calendar === 'bs' ? 'font-devanagari' : 'font-mono'} ${
            n === todayDay ? 'text-text-primary' : 'text-text-secondary'
          }`}>{digit(n)}</span>
        </div>
      ))}

      {data.months.map((month, row) => (
        <MonthRow key={`${month.year}-${month.month}`} month={month} data={data} cols={cols}
          todayDay={row === 0 ? todayDay : null} selected={selected} onDown={onDown} onHover={onHover} />
      ))}
    </div>
  );
}

function MonthRow({ month, data, cols, todayDay, selected, onDown, onHover }: {
  month: DayByDayMonth; data: DayByDaySummary; cols: number; todayDay: number | null; selected: Set<string>;
  onDown: (e: React.PointerEvent, date: string) => void; onHover: (h: Hover) => void;
}) {
  return (
    <>
      <MonthLabel month={month} data={data} />
      {Array.from({ length: cols }, (_, i) => {
        const day = month.days[i];
        return day
          ? <Tile key={day.date} day={day} isToday={day.day === todayDay} selected={selected.has(day.date)}
              onDown={onDown} onHover={onHover} />
          : <div key={`pad-${i}`} />;
      })}
    </>
  );
}

// ---------------------------------------------------------------------------
// Selection detail
// ---------------------------------------------------------------------------

function SelectionCard({ data, from, to, onClose }: {
  data: DayByDaySummary; from: string; to: string; onClose: () => void;
}) {
  const all = data.months.flatMap((m) => m.days).filter((d) => d.date >= from && d.date <= to)
    .sort((a, b) => a.date.localeCompare(b.date));
  const traded = all.filter((d) => d.status === 'traded' && d.change_pct != null);
  const first = traded[0];
  const last = traded[traded.length - 1];
  // Exact from closes when the first session's previous close is known; otherwise compounded.
  const cumulative = !traded.length ? null
    : first.previous_close != null && last.close != null
      ? (last.close / first.previous_close - 1) * 100
      : (traded.reduce((g, d) => g * (1 + (d.change_pct as number) / 100), 1) - 1) * 100;
  const best = traded.reduce<DayByDayDay | null>((b, d) => (!b || (d.change_pct as number) > (b.change_pct as number) ? d : b), null);
  const worst = traded.reduce<DayByDayDay | null>((w, d) => (!w || (d.change_pct as number) < (w.change_pct as number) ? d : w), null);
  const up = traded.filter((d) => (d.change_pct as number) > 0).length;
  const startDay = all[0];
  const endDay = all[all.length - 1];
  return (
    <div className="card fixed inset-x-3 bottom-3 z-40 animate-fade-in !rounded-2xl !p-5 shadow-2xl sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-[320px]">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-secondary">{data.index.name} · selection</p>
          <p className="mt-1 font-devanagari text-sm font-semibold text-text-primary">
            {startDay?.bs_label_np}{from !== to && <> → {endDay?.bs_label_np}</>}
          </p>
          <p className="text-[11px] text-text-secondary">
            {formatTradeDate(from)}{from !== to && <> → {formatTradeDate(to)}</>}
          </p>
        </div>
        <button type="button" onClick={onClose} aria-label="Clear selection"
          className="rounded-md p-1 text-text-secondary hover:text-text-primary"><X size={16} /></button>
      </div>
      {traded.length ? (
        <>
          <p className={`mt-3 font-mono text-3xl font-semibold ${toneText(cumulative)}`}>{formatPct(cumulative)}</p>
          <p className="text-[11px] text-text-secondary">
            Cumulative over {traded.length} session{traded.length > 1 ? 's' : ''} · {up} up, {traded.length - up} down or flat
          </p>
          <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <span className="text-text-secondary">Start (prev. close)</span>
            <span className="text-right font-mono text-text-primary">{formatPrice(first.previous_close)}</span>
            <span className="text-text-secondary">End close</span>
            <span className="text-right font-mono text-text-primary">{formatPrice(last.close)}</span>
            {traded.length > 1 && best && worst && (
              <>
                <span className="text-text-secondary">Best day</span>
                <span className="text-right"><span className="text-text-secondary">{formatTradeDate(best.date)}</span>{' '}
                  <span className={`font-mono ${toneText(best.change_pct)}`}>{formatPct(best.change_pct)}</span></span>
                <span className="text-text-secondary">Worst day</span>
                <span className="text-right"><span className="text-text-secondary">{formatTradeDate(worst.date)}</span>{' '}
                  <span className={`font-mono ${toneText(worst.change_pct)}`}>{formatPct(worst.change_pct)}</span></span>
              </>
            )}
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm text-text-secondary">No stored sessions in this selection.</p>
      )}
      <p className="mt-3 text-[10px] text-text-muted">Drag across tiles or shift-click to extend · Esc to clear</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DayByDayPage() {
  const [index, setIndex] = useIndexParam();
  const [calendar, setCalendar] = useState<DayByDayCalendar>('bs');
  const [months, setMonths] = useState<DayByDayMonths>(12);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [hover, setHover] = useState<Hover>(null);
  const { range, onDown, onGridMove, dragging, clear } = useDragSelect();

  const { data, isLoading, isFetching, error, refetch } = useDayByDay(index, calendar, months);
  const detail = (error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;

  const [from, to] = range ?? [null, null];
  const selected = useMemo(() => {
    const set = new Set<string>();
    if (!data || !from || !to) return set;
    for (const m of data.months) for (const d of m.days) if (d.date >= from && d.date <= to) set.add(d.date);
    return set;
  }, [data, from, to]);

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <aside className="shrink-0 lg:w-[220px]">
        <HeatViewTabs index={index} />
        <div className="mt-5 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-text-muted">{data?.index.code ?? index} · whole market</p>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-text-primary">NEPSE day by day</h1>
            <p className="mt-2 text-xs leading-snug text-text-secondary">
              Each day = its close against the previous trading day's close. * = partial
            </p>
          </div>
          <button type="button" onClick={() => setDrawerOpen((o) => !o)} aria-expanded={drawerOpen}
            className="flex items-center gap-1.5 rounded-xl border border-bg-border bg-bg-card px-3 py-2 text-xs font-semibold text-text-primary lg:hidden">
            <SlidersHorizontal size={14} /> {drawerOpen ? 'Hide' : 'Options'}
          </button>
        </div>
        <div className={`mt-5 ${drawerOpen ? 'block animate-fade-in' : 'hidden'} lg:block`}>
          <SidebarBody data={data} index={index} onIndex={setIndex} calendar={calendar} onCalendar={setCalendar}
            months={months} onMonths={setMonths} />
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
            <section className={`card overflow-x-auto !rounded-2xl !p-6 transition-opacity ${isFetching ? 'opacity-70' : ''}`}
              onPointerMove={onGridMove} onPointerLeave={() => setHover(null)}>
              <div className="w-max">
                <Grid data={data} selected={selected} onDown={onDown} onHover={setHover} />
              </div>
            </section>
            {data.notes.map((note) => <p key={note} className="text-xs text-text-muted">{note}</p>)}
          </>
        )}
      </main>

      <Tooltip hover={dragging.current ? null : hover} indexName={data?.index.code ?? index} />
      {data && from && to && <SelectionCard data={data} from={from} to={to} onClose={clear} />}
    </div>
  );
}
