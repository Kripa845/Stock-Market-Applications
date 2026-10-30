// Weekday by weekday: the tracked companies' average daily move (all of them, or one sector) as a
// week x weekday heat table, with best / worst week, strongest weekday, the share of up days and
// each weekday's average.  Every figure comes from crawled prices; days without one show as dashed gaps.
import { Link } from 'react-router-dom';
import { useState } from 'react';
import {
  AlertTriangle, ArrowRight, CalendarDays, CircleCheck, Info, Lightbulb, RefreshCw, TrendingDown, TrendingUp,
} from 'lucide-react';

import { formatPct, formatTradeDate } from '../components/market/format';
import { WEEKDAY_NAMES, gapLabel, heatClass, toneText } from '../components/market/weekday';
import {
  DEFAULT_WEEKDAY_SCOPE, WEEKDAY_WEEK_CHOICES, WEEKDAY_WEEK_LABELS, type WeekdayDay, type WeekdayInsight, type WeekdayScopeOption,
  type WeekdayScopes, type WeekdaySummary, type WeekdayWeek, type WeekdayWeeks,
} from '../api/marketCalendar';
import { useWeekdaySummary } from '../hooks/useMarketCalendar';

function find<K extends WeekdayInsight['kind']>(insights: WeekdayInsight[], kind: K) {
  return insights.find((i): i is Extract<WeekdayInsight, { kind: K }> => i.kind === kind);
}

function StatCard({ label, icon, iconClass, children }: {
  label: string; icon: React.ReactNode; iconClass: string; children: React.ReactNode;
}) {
  return (
    <div className="card !rounded-2xl !p-6">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-secondary">{label}</p>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${iconClass}`}>{icon}</span>
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Stats({ data }: { data: WeekdaySummary }) {
  const best = data.week_rows.find((w) => w.best);
  const worst = data.week_rows.find((w) => w.worst);
  const strongest = find(data.insights, 'best');
  const upShare = data.sessions_total ? (data.sessions_up / data.sessions_total) * 100 : null;
  const weekLine = (w: WeekdayWeek) => `${w.label} · ${w.up_days} of ${w.sessions} days up`;
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Best week" icon={<TrendingUp size={17} />} iconClass="bg-up/10 text-up">
        <p className={`font-mono text-4xl font-semibold ${toneText(best?.change_pct)}`}>{formatPct(best?.change_pct)}</p>
        <p className="mt-3 text-sm text-text-secondary">{best ? weekLine(best) : 'No complete week yet'}</p>
      </StatCard>
      <StatCard label="Worst week" icon={<TrendingDown size={17} />} iconClass="bg-down/10 text-down">
        <p className={`font-mono text-4xl font-semibold ${toneText(worst?.change_pct)}`}>{formatPct(worst?.change_pct)}</p>
        <p className="mt-3 text-sm text-text-secondary">{worst ? weekLine(worst) : 'Needs two complete weeks'}</p>
      </StatCard>
      <StatCard label="Strongest weekday" icon={<CalendarDays size={17} />} iconClass="bg-accent/15 text-accent">
        <p className="font-mono text-4xl font-semibold text-text-primary">{formatPct(strongest?.average_pct)}</p>
        <p className="mt-3 text-sm text-text-secondary">
          {strongest
            ? `${WEEKDAY_NAMES[strongest.weekdays[0]]} average · ${strongest.up} of ${strongest.sessions} up`
            : 'No weekday averages above zero'}
        </p>
      </StatCard>
      <StatCard label="Days closed up" icon={<CircleCheck size={17} />} iconClass="bg-up/10 text-up">
        <p className="flex items-baseline gap-3">
          <span className="font-mono text-4xl font-semibold text-text-primary">{upShare == null ? '—' : `${Math.round(upShare)}%`}</span>
          <span className="text-sm text-text-secondary">{data.sessions_up} of {data.sessions_total} sessions</span>
        </p>
        <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-bg-border">
          <div className="h-full rounded-full bg-up" style={{ width: `${upShare ?? 0}%` }} />
        </div>
      </StatCard>
    </div>
  );
}

function DayCell({ day, today, isToday }: { day: WeekdayDay; today: string; isToday: boolean }) {
  const pct = day.change_pct;
  const when = `${WEEKDAY_NAMES[day.weekday] ?? day.weekday}, ${formatTradeDate(day.date)}`;
  const title = pct == null
    ? `${when}\n${gapLabel(day, today)}${day.holiday ? `: ${day.holiday}` : ''}`
    : [
      when,
      `Average ${formatPct(pct)} of ${day.companies} companies · ${day.companies_up} up`,
      day.best && `Best ${day.best.symbol} ${formatPct(day.best.change_pct)} · worst ${day.worst?.symbol} ${formatPct(day.worst?.change_pct)}`,
      day.excluded ? `${day.excluded} left out (no trade, no price or a corporate action)` : '',
    ].filter(Boolean).join('\n');
  return (
    <div title={title}
      className={`flex h-16 flex-col items-center justify-center rounded-xl ${heatClass(pct)} ${
        isToday ? 'ring-2 ring-accent ring-offset-2 ring-offset-bg-card' : ''
      }`}>
      {pct == null ? (
        <span className="text-sm">{gapLabel(day, today)}</span>
      ) : (
        <>
          <span className="flex items-center gap-2 font-mono text-[15px] font-semibold">
            <span className="text-[11px]">{pct > 0 ? '▲' : pct < 0 ? '▼' : '■'}</span>
            {formatPct(pct)}
          </span>
          <span className="text-[11px] opacity-80">{day.companies_up} of {day.companies} up</span>
        </>
      )}
    </div>
  );
}

function WeekChange({ week, scale }: { week: WeekdayWeek; scale: number }) {
  const pct = week.change_pct;
  const width = pct == null ? 0 : Math.min(Math.abs(pct) / scale, 1) * 50;
  return (
    <div className="pl-2">
      <p className={`font-mono text-lg font-semibold ${toneText(pct)}`}>
        {formatPct(pct)}{week.partial && <span title="Partial week, still updating">*</span>}
      </p>
      <div className="relative mt-2 h-1.5 w-full rounded-full bg-bg-border">
        <span className="absolute left-1/2 top-[-3px] h-3 w-px bg-text-muted/60" />
        <span
          className={`absolute top-0 h-full rounded-full ${pct != null && pct < 0 ? 'bg-down' : 'bg-up'}`}
          style={pct != null && pct < 0 ? { right: '50%', width: `${width}%` } : { left: '50%', width: `${Math.max(width, pct ? 1 : 0)}%` }}
        />
      </div>
    </div>
  );
}

function badge(week: WeekdayWeek) {
  if (week.partial) return { text: 'Current week', cls: 'bg-accent/15 text-accent' };
  if (week.best) return { text: 'Best week', cls: 'bg-up/15 text-up' };
  if (week.worst) return { text: 'Worst week', cls: 'bg-down/15 text-down' };
  return null;
}

function insightText(insight: WeekdayInsight | undefined, weeks: number) {
  if (!insight) return null;
  const name = WEEKDAY_NAMES[insight.weekdays[0]] ?? insight.weekdays[0];
  if (insight.kind === 'streak') return `${name} has closed up ${insight.sessions} week${insight.sessions > 1 ? 's' : ''} running.`;
  if (insight.kind === 'always_up') return `${name} closed up in all ${insight.sessions === weeks ? weeks : insight.sessions} weeks it traded.`;
  if (insight.kind === 'best') return `${name} has the best average, ${formatPct(insight.average_pct)}.`;
  return null;
}

function HeatTable({ data }: { data: WeekdaySummary }) {
  const columns = data.columns;
  const current = data.week_rows[0];
  const todayIndex = current ? current.days.findIndex((d) => d.date === data.today) : -1;
  const scale = Math.max(1, ...data.week_rows.map((w) => Math.abs(w.change_pct ?? 0)));
  const bestAvg = find(data.insights, 'best')?.weekdays[0];
  const steady = (find(data.insights, 'streak') ?? find(data.insights, 'always_up'))?.weekdays[0];
  const note = insightText(find(data.insights, 'streak') ?? find(data.insights, 'always_up') ?? find(data.insights, 'best'), data.weeks);
  const grid = { gridTemplateColumns: `minmax(130px,1.1fr) repeat(${columns.length}, minmax(96px,1fr)) minmax(170px,1.3fr)` };

  return (
    <section className="card overflow-x-auto !rounded-2xl !p-6 sm:!p-8">
      <div className="min-w-[860px] space-y-3">
        {/* Header */}
        <div className="grid items-end gap-3" style={grid}>
          <span className="pb-3 text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">Week of</span>
          {columns.map((column, i) => (
            <div key={column.weekday}
              className={`flex flex-col items-center justify-center rounded-xl py-3 ${i === todayIndex ? 'border border-accent/50 bg-accent/10' : ''}`}>
              {i === todayIndex && <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-accent">Today</span>}
              <span className={`text-sm font-semibold uppercase tracking-wider ${i === todayIndex ? 'text-text-primary' : 'text-text-secondary'}`}>
                {column.weekday}
              </span>
            </div>
          ))}
          <span className="pb-3 pl-2 text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">Week change</span>
        </div>

        {/* Weeks, newest first */}
        {data.week_rows.map((week, row) => {
          const tag = badge(week);
          return (
            <div key={week.week_start} className="grid items-center gap-3" style={grid}>
              <div title={`Week of ${formatTradeDate(week.week_start)}`}>
                <p className="text-base font-semibold text-text-primary">{week.label}</p>
                {tag && <span className={`mt-1 inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${tag.cls}`}>{tag.text}</span>}
              </div>
              {week.days.map((day, i) => (
                <DayCell key={day.date} day={day} today={data.today} isToday={row === 0 && i === todayIndex && day.change_pct != null} />
              ))}
              <WeekChange week={week} scale={scale} />
            </div>
          );
        })}

        {/* Averages */}
        <div className="grid items-center gap-3 border-t border-bg-border pt-5" style={grid}>
          <div>
            <p className="text-base font-semibold text-text-primary">Average</p>
            <p className="text-xs text-text-muted">all {data.weeks} weeks</p>
          </div>
          {columns.map((column) => {
            const outlined = column.weekday === bestAvg || column.weekday === steady;
            return (
              <div key={column.weekday}
                className={`flex flex-col items-center rounded-xl border py-3 ${outlined ? 'border-up/40 bg-up/5' : 'border-bg-border'}`}>
                <span className={`font-mono text-lg font-semibold ${toneText(column.average_pct)}`}>{formatPct(column.average_pct)}</span>
                <span className="text-xs text-text-secondary">{column.sessions ? `${column.up} of ${column.sessions} up` : 'no sessions'}</span>
              </div>
            );
          })}
          {note ? (
            <div className="flex items-start gap-3 pl-2">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent/15 text-accent"><Lightbulb size={15} /></span>
              <p className="text-sm text-text-primary">{note}</p>
            </div>
          ) : <span />}
        </div>
      </div>
    </section>
  );
}

function ScopePicker({ scopes, value, onChange }: { scopes?: WeekdayScopes; value: string; onChange: (scope: string) => void }) {
  const option = (o: WeekdayScopeOption) => (
    <option key={o.scope} value={o.scope}>
      {o.label} ({o.companies} {o.companies === 1 ? 'company' : 'companies'})
    </option>
  );
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label="What to show"
      className="rounded-xl border border-bg-border bg-bg-card px-3 py-2.5 text-sm font-medium text-text-primary outline-none focus:border-accent">
      {!scopes && <option value={value}>All tracked companies</option>}
      {scopes?.tracked.map(option)}
      {scopes && scopes.tracked_sectors.length > 0 && (
        <optgroup label="By sector">{scopes.tracked_sectors.map(option)}</optgroup>
      )}
    </select>
  );
}

// What the numbers mean, in plain words.
function HowToRead({ data }: { data: WeekdaySummary }) {
  const group = data.scope_label === 'Tracked companies' ? 'tracked companies' : `${data.scope_label.replace('Tracked ', '')} companies`;
  const example = Math.ceil(data.companies / 2);
  return (
    <div className="card flex items-start gap-3 !rounded-2xl !p-5">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/15 text-accent"><Info size={17} /></span>
      <div className="space-y-1.5 text-sm text-text-secondary">
        <p className="font-semibold text-text-primary">How to read this</p>
        <p>
          Each box is the <strong className="text-text-primary">average daily % change of your {data.companies} {group}</strong>,
          {' '}each stock counted equally (a Rs 300 stock and a Rs 5,000 stock weigh the same).
          {' '}"{example} of {data.companies} up" under a box means {example} of them rose that day.
        </p>
        <p>
          A stock's daily % is the same one the Top Gainers / Losers pages use (adjusted for bonus and right shares).
          Stocks that didn't trade, have no price yet, or show a suspected corporate action that day are left out of that day's average.
          A week's change compounds the daily averages. Today's box fills in after the evening price crawl.
        </p>
        <p className="font-mono text-xs text-text-muted">{data.symbols.join(' · ')}</p>
      </div>
    </div>
  );
}

export default function WeekdaySummaryPage() {
  const [weeks, setWeeks] = useState<WeekdayWeeks>(6);
  const [scope, setScope] = useState(DEFAULT_WEEKDAY_SCOPE);
  const { data, isLoading, isFetching, error, refetch } = useWeekdaySummary(weeks, scope);
  const detail = (error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;
  const subtitle = data
    ? `Each cell is the average daily % change of the ${data.companies} companies, each counted equally.`
    : 'Each cell is the average daily % change of your tracked companies.';

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-text-muted">
            {data?.scope_label ?? 'Tracked companies'} · last {data ? `${data.weeks} weeks` : WEEKDAY_WEEK_LABELS[weeks]}
          </p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">Weekday by weekday</h1>
          <p className="mt-2 text-sm text-text-secondary">{subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <ScopePicker scopes={data?.scopes} value={scope} onChange={setScope} />
          <div role="group" aria-label="Period" className="flex gap-1 rounded-xl border border-bg-border bg-bg-card p-1">
            {WEEKDAY_WEEK_CHOICES.map((w) => (
              <button key={w} type="button" aria-pressed={w === weeks} onClick={() => setWeeks(w)}
                className={`rounded-lg px-4 py-2 font-mono text-sm transition ${
                  w === weeks ? 'bg-accent/20 font-semibold text-accent' : 'text-text-secondary hover:text-text-primary'
                }`}>
                {WEEKDAY_WEEK_LABELS[w]}
              </button>
            ))}
          </div>
          <button type="button" onClick={() => refetch()}
            className="flex items-center gap-2 rounded-xl border border-bg-border bg-bg-card px-4 py-2.5 text-sm font-semibold text-text-primary hover:bg-bg-elevated">
            <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {error ? (
        <div role="alert" className="flex items-center gap-2 rounded-md border border-down/30 bg-down/10 px-4 py-3 text-sm text-down">
          <AlertTriangle size={15} /> {detail ?? 'Unable to load the weekday summary.'}
        </div>
      ) : isLoading || !data ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton h-[150px] rounded-2xl" />)}
          </div>
          <div className="skeleton h-[560px] rounded-2xl" />
        </div>
      ) : (
        <div className={`space-y-6 transition-opacity ${isFetching ? 'opacity-70' : ''}`}>
          <HowToRead data={data} />
          <Stats data={data} />
          <HeatTable data={data} />

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-text-secondary">
            <div className="flex items-center gap-3">
              <span>Daily move</span>
              <span className="font-mono text-down">-1.5%</span>
              <span className="h-2 w-48 rounded-full bg-gradient-to-r from-down via-bg-border to-up" />
              <span className="font-mono text-up">+1.5%</span>
            </div>
            <span>Arrows repeat the colour · * partial week, still updating</span>
          </div>
          <p className="text-xs text-text-muted">
            {data.scope_label} sessions {formatTradeDate(data.from)} – {formatTradeDate(data.to)}.{data.notes.map((note) => ` ${note}`)}{' '}
            <Link to="/market/calendar" className="inline-flex items-center gap-1 text-accent hover:underline">
              Market calendar <ArrowRight size={12} />
            </Link>
          </p>
        </div>
      )}
    </div>
  );
}
