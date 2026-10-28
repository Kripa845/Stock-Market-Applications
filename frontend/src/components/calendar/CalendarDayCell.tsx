import clsx from 'clsx';
import type { CalendarMonthDay } from '../../api/marketCalendar';
import { changeTone, formatPct, formatPrice } from '../market/format';
import { EVENT_CHIP, EVENT_DOT, STATUS_NOTE } from './calendarStyles';

const MAX_CHIPS = 2;
const SATURDAY = 6;

const signed = (value: string | null) => {
  if (value === null) return '—';
  const n = Number(value);
  return `${n > 0 ? '+' : ''}${formatPrice(n)}`;
};

const adLabel = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });

interface CalendarDayCellProps {
  day: CalendarMonthDay;
  selected: boolean;
  onSelect: (date: string) => void;
}

export default function CalendarDayCell({ day, selected, onSelect }: CalendarDayCellProps) {
  const index = day.index;
  const tone = index ? changeTone(index.change_pct ?? index.change) : 'flat';
  const closed = day.status === 'weekend' || day.status === 'holiday';
  // Nepali calendars print Saturdays and public holidays in red.
  const redDate = day.weekday === SATURDAY || Boolean(day.holiday);
  const note = STATUS_NOTE[day.status];
  const toneText = tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-text-secondary';

  return (
    <button
      type="button"
      onClick={() => onSelect(day.date)}
      aria-pressed={selected}
      aria-label={`${day.date}${day.holiday ? `, ${day.holiday}` : ''}${day.is_today ? ', today' : ''}`}
      className={clsx(
        'group relative flex h-full min-h-[64px] min-w-0 flex-col overflow-hidden rounded-md border border-l-[3px] p-1 text-left transition',
        'hover:border-accent-light/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent sm:min-h-[118px] sm:p-2',
        tone === 'up' && 'border-l-up bg-up/[0.07]',
        tone === 'down' && 'border-l-down bg-down/[0.07]',
        tone === 'flat' && (closed ? 'bg-bg-secondary/70' : 'bg-bg-card'),
        tone === 'flat' && (index ? 'border-l-text-muted/40' : 'border-l-transparent'),
        selected ? 'border-accent ring-2 ring-accent' : day.is_today ? 'border-accent-light ring-1 ring-accent-light' : 'border-bg-border',
      )}
    >
      <div className="flex items-start justify-between gap-1">
        <span
          className={clsx(
            'font-devanagari text-base font-semibold leading-none sm:text-[26px]',
            redDate ? 'text-down' : closed ? 'text-text-muted' : 'text-text-primary',
          )}
        >
          {day.bs_day_np}
        </span>
        <span className="flex flex-col items-end gap-0.5">
          <span className="hidden text-[11px] leading-none text-text-muted sm:block">{adLabel(day.date)}</span>
          {day.is_today && (
            <span className="rounded bg-accent px-1 text-[9px] font-semibold uppercase leading-4 tracking-wide text-white">Today</span>
          )}
        </span>
      </div>

      {day.holiday && (
        <p className="mt-1 truncate text-[9px] font-medium text-down sm:text-[11px]" title={day.holiday}>{day.holiday}</p>
      )}

      <div className="mt-auto space-y-1 pt-1">
        {index ? (
          <div className="font-mono leading-tight">
            <p className="hidden text-sm font-semibold text-text-primary sm:block">{formatPrice(index.close)}</p>
            <p className={clsx('text-[9px] sm:text-[11px]', toneText)}>
              <span className="hidden sm:inline">{signed(index.change)} </span>
              <span className="sm:hidden">{formatPct(index.change_pct, 1)}</span>
              <span className="hidden sm:inline">({formatPct(index.change_pct)})</span>
            </p>
          </div>
        ) : (
          note && <p className="hidden text-[11px] italic text-text-muted sm:block">{note}</p>
        )}

        {day.events.length > 0 && (
          <div className="flex min-w-0 flex-wrap gap-0.5">
            {day.events.slice(0, MAX_CHIPS).map((event) => (
              <span
                key={event.label}
                title={event.label}
                className={clsx('hidden max-w-full truncate rounded px-1 text-[10px] font-medium leading-4 sm:block', EVENT_CHIP[event.type])}
              >
                {event.label}
              </span>
            ))}
            {day.events.length > MAX_CHIPS && (
              <span className="hidden rounded bg-bg-elevated px-1 text-[10px] leading-4 text-text-secondary sm:block">
                +{day.events.length - MAX_CHIPS} more
              </span>
            )}
            {/* Phones show one dot per event type; the panel lists them. */}
            <span className="flex gap-0.5 sm:hidden">
              {[...new Set(day.events.map((event) => event.type))].map((type) => (
                <span key={type} className={clsx('h-1.5 w-1.5 rounded-full', EVENT_DOT[type])} />
              ))}
            </span>
          </div>
        )}
      </div>
    </button>
  );
}
