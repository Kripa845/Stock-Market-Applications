import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Loader2, X } from 'lucide-react';
import clsx from 'clsx';
import type { CalendarDay, CalendarIndexRow } from '../../api/marketCalendar';
import { useCalendarDay } from '../../hooks/useMarketCalendar';
import CompanyLogo from '../companies/CompanyLogo';
import { Skeleton } from '../common/LoadingSkeleton';
import { changeTone, formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from '../market/format';
import DayMarketSections from './DayMarketSections';
import { PanelCard } from './PanelCard';
import { EVENT_CHIP, EVENT_LABEL, STATUS_BADGE, STATUS_LABEL } from './calendarStyles';

// Right-hand panel for one calendar day (full screen on phones).  Esc, the backdrop or × close it;
// ‹ › and the arrow keys step a day.

interface DayDetailPanelProps {
  date: string;
  onClose: () => void;
  onStep: (days: number) => void;
}

const longAdDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

const toneText = (tone: string) => (tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-text-secondary');

/** Low-to-high bar of the session with the open -> close move highlighted. */
function DayRange({ index, tone }: { index: CalendarIndexRow; tone: string }) {
  const [low, high, open, close] = [index.low, index.high, index.open, index.close].map((v) => (v === null ? null : Number(v)));
  if (low === null || high === null || close === null || high <= low) return null;
  const at = (v: number) => `${((v - low) / (high - low)) * 100}%`;
  const from = open ?? close;
  return (
    <div className="space-y-1">
      <div className="relative h-1.5 rounded-full bg-bg-elevated">
        <span
          className={clsx('absolute inset-y-0 rounded-full', tone === 'down' ? 'bg-down' : tone === 'up' ? 'bg-up' : 'bg-text-muted')}
          style={{ left: at(Math.min(from, close)), right: `calc(100% - ${at(Math.max(from, close))})` }}
        />
        <span className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 rounded bg-text-primary" style={{ left: at(close) }} aria-hidden />
      </div>
      <div className="flex justify-between font-mono text-[11px] text-text-muted">
        <span>L {formatPrice(low)}</span>
        {open !== null && <span>O {formatPrice(open)}</span>}
        <span>H {formatPrice(high)}</span>
      </div>
    </div>
  );
}

function IndexCard({ day }: { day: CalendarDay }) {
  const index = day.index;
  if (!index) {
    const why = day.status === 'future' ? 'Upcoming day.'
      : day.status === 'pending' ? 'Shown after the session closes.'
      : day.status === 'no_data' ? 'No NEPSE index history stored this far back.'
      : 'No session this day.';
    return (
      <PanelCard title={`${day.index_code} index`}>
        <p className="px-3 py-4 text-sm text-text-muted">{why}</p>
      </PanelCard>
    );
  }
  const tone = changeTone(index.change_pct ?? index.change);
  return (
    <PanelCard title={`${day.index_code} index`} aside={index.previous_date && <>vs {formatTradeDate(index.previous_date)}</>}>
      <div className="space-y-3 p-3">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-mono text-3xl font-semibold text-text-primary">{formatPrice(index.close)}</span>
          <span className={clsx('rounded px-1.5 py-0.5 font-mono text-sm font-medium', tone === 'up' ? 'bg-up/15' : tone === 'down' ? 'bg-down/15' : 'bg-bg-elevated', toneText(tone))}>
            {index.change === null ? '—' : `${Number(index.change) > 0 ? '+' : ''}${formatPrice(index.change)}`} ({formatPct(index.change_pct)})
          </span>
        </div>
        <DayRange index={index} tone={tone} />
        <div className="grid grid-cols-3 gap-3 border-t border-bg-border pt-3">
          {[
            ['Turnover', formatNprCompact(index.turnover)],
            ['Volume', formatCount(index.volume)],
            ['Trades', formatCount(index.transactions)],
          ].map(([label, value]) => (
            <div key={label} className="min-w-0">
              <p className="text-[11px] text-text-muted">{label}</p>
              <p className="truncate font-mono text-sm font-semibold text-text-primary">{value}</p>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-text-muted">
          Whole market{index.source === 'sharesansar' && ' · from ShareSansar (NEPSE feed unavailable)'}
        </p>
      </div>
    </PanelCard>
  );
}

function EventsCard({ day }: { day: CalendarDay }) {
  return (
    <PanelCard title="Events" aside={day.events.length > 0 && day.events.length}>
      {day.events.length === 0 ? (
        <p className="px-3 py-4 text-sm text-text-muted">No dividend or issue events.</p>
      ) : (
        <ul>
          {day.events.map((event) => (
            <li key={event.label} className="flex items-start gap-3 border-t border-bg-border px-3 py-2.5 first:border-t-0">
              <CompanyLogo symbol={event.symbol || '?'} name={event.company_name} logoUrl={event.logo_url} size="sm" />
              <div className="min-w-0 flex-1 space-y-0.5">
                <div className="flex flex-wrap items-center gap-2">
                  {event.category === 'dividend' ? (
                    <Link to={`/companies/${event.symbol}`} className="text-sm font-semibold text-text-primary hover:text-accent-light">{event.symbol}</Link>
                  ) : (
                    <span className="text-sm font-semibold text-text-primary">{event.symbol || '—'}</span>
                  )}
                  <span className={clsx('rounded px-1.5 text-[11px] font-medium', EVENT_CHIP[event.type])}>{EVENT_LABEL[event.type]}</span>
                </div>
                <p className="truncate text-xs text-text-muted">{event.company_name}</p>
                {event.category === 'dividend' ? (
                  <p className="font-mono text-xs text-text-secondary">
                    FY {event.fiscal_year || '—'} · Bonus {formatPct(event.bonus_pct).replace('+', '')} · Cash {formatPct(event.cash_pct).replace('+', '')}
                  </p>
                ) : (
                  <div className="text-xs text-text-secondary">
                    <p>
                      {event.issue_type_label} · <span className="font-mono">{formatCount(event.units)}</span> units
                      {event.price && <> @ <span className="font-mono">{formatPrice(event.price)}</span></>}
                      {event.ratio && <> · ratio {event.ratio}</>}
                    </p>
                    <p>
                      {formatTradeDate(event.open_date)} → {formatTradeDate(event.close_date)}
                      {event.final_date && event.final_date !== event.close_date && <> (latest {formatTradeDate(event.final_date)})</>}
                    </p>
                    {event.issue_manager && <p className="text-text-muted">{event.issue_manager}</p>}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="border-t border-bg-border px-3 py-2 text-[11px] text-text-muted">
        Dividends: tracked companies you can access · Issues: whole market
      </p>
    </PanelCard>
  );
}

export default function DayDetailPanel({ date, onClose, onStep }: DayDetailPanelProps) {
  const { data: day, isLoading, isFetching, isError } = useCalendarDay(date);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      else if (event.key === 'ArrowLeft') onStep(-1);
      else if (event.key === 'ArrowRight') onStep(1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, onStep]);

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/40 motion-safe:animate-fade-in" onClick={onClose} aria-hidden />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`Market details for ${date}`}
        className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-bg-border bg-bg-card shadow-2xl motion-safe:animate-panel-in sm:w-[460px]"
      >
        <header className="border-b border-bg-border px-4 pb-3 pt-4">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h2 className="truncate font-devanagari text-xl font-semibold text-text-primary">
                {day ? `${day.bs.label_np}, ${day.bs.weekday_np}` : '…'}
              </h2>
              <p className="text-xs text-text-muted">{longAdDate(date)}</p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {isFetching && !isLoading && <Loader2 size={14} className="mr-1 animate-spin text-text-muted" aria-label="Loading" />}
              <button type="button" className="btn-ghost rounded-md p-1.5" onClick={() => onStep(-1)} aria-label="Previous day" title="Previous day (←)">
                <ChevronLeft size={18} />
              </button>
              <button type="button" className="btn-ghost rounded-md p-1.5" onClick={() => onStep(1)} aria-label="Next day" title="Next day (→)">
                <ChevronRight size={18} />
              </button>
              <button type="button" className="btn-ghost rounded-md p-1.5" onClick={onClose} aria-label="Close" title="Close (Esc)">
                <X size={18} />
              </button>
            </div>
          </div>
          {day && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className={clsx('rounded px-2 py-0.5 text-[11px] font-medium', STATUS_BADGE[day.status])}>{STATUS_LABEL[day.status]}</span>
              {day.is_today && <span className="rounded bg-accent px-2 py-0.5 text-[11px] font-semibold text-white">Today</span>}
              {day.holiday && <span className="rounded bg-down/15 px-2 py-0.5 text-[11px] font-medium text-down">{day.holiday}</span>}
            </div>
          )}
        </header>

        <div className={clsx('flex-1 space-y-3 overflow-y-auto p-4 transition-opacity', isFetching && !isLoading && 'opacity-60')}>
          {isLoading && (
            <div className="space-y-3">
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-64 w-full" />
            </div>
          )}
          {isError && <p className="text-sm text-down">Could not load this day.</p>}
          {day && (
            <>
              <IndexCard day={day} />
              {day.events.length > 0 && <EventsCard day={day} />}
              {/* Past sessions only: a future day has no prices yet. */}
              {day.market && day.status !== 'future' && <DayMarketSections market={day.market} />}
              {day.events.length === 0 && <EventsCard day={day} />}
            </>
          )}
        </div>
      </aside>
    </>
  );
}
