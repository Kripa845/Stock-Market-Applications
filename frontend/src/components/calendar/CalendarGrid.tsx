import clsx from 'clsx';
import type { CalendarMonth } from '../../api/marketCalendar';
import CalendarDayCell from './CalendarDayCell';

// Sunday-first, as on Nepali calendars.  Weekday names are fixed labels, not date data.
const WEEKDAYS = [
  ['आइत', 'Sun'], ['सोम', 'Mon'], ['मंगल', 'Tue'], ['बुध', 'Wed'], ['बिही', 'Thu'], ['शुक्र', 'Fri'], ['शनि', 'Sat'],
];

interface CalendarGridProps {
  month: CalendarMonth;
  selectedDate: string | null;
  onSelect: (date: string) => void;
}

export default function CalendarGrid({ month, selectedDate, onSelect }: CalendarGridProps) {
  return (
    <div className="space-y-1">
      <div className="grid grid-cols-7 gap-0.5 sm:gap-1.5">
        {WEEKDAYS.map(([np, en], i) => (
          <div
            key={en}
            className={clsx(
              'flex flex-col items-center rounded py-1 text-[10px] sm:flex-row sm:justify-center sm:gap-1.5 sm:text-xs',
              i === 6 ? 'text-down' : 'text-text-secondary',
            )}
          >
            <span className="font-devanagari font-semibold">{np}</span>
            <span className="hidden text-text-muted sm:inline">{en}</span>
          </div>
        ))}
      </div>
      {/* auto-rows-fr: every week row as tall as the tallest, so the grid stays even. */}
      <div className="grid auto-rows-fr grid-cols-7 gap-0.5 sm:gap-1.5">
        {Array.from({ length: month.leading_blanks }, (_, i) => (
          <div key={`blank-${i}`} aria-hidden className="rounded-md border border-dashed border-bg-border/50" />
        ))}
        {month.days.map((day) => (
          <CalendarDayCell key={day.date} day={day} selected={day.date === selectedDate} onSelect={onSelect} />
        ))}
      </div>
    </div>
  );
}
