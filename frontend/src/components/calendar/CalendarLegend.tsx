import clsx from 'clsx';
import type { CalendarEventType } from '../../api/marketCalendar';
import { EVENT_DOT, EVENT_LABEL } from './calendarStyles';

const EVENT_ORDER: CalendarEventType[] = [
  'book_closure', 'ipo_open', 'ipo_close', 'bonus_listed', 'cash_distributed', 'dividend_announced',
];

function Swatch({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={clsx('h-2.5 w-2.5 shrink-0 rounded-sm', className)} />
      {label}
    </span>
  );
}

export default function CalendarLegend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 border-t border-bg-border pt-3 text-[11px] text-text-secondary">
      <Swatch className="bg-up" label="NEPSE up" />
      <Swatch className="bg-down" label="NEPSE down" />
      <Swatch className="border border-down bg-transparent" label="Saturday / holiday (red date)" />
      {EVENT_ORDER.map((type) => <Swatch key={type} className={EVENT_DOT[type]} label={EVENT_LABEL[type]} />)}
    </div>
  );
}
