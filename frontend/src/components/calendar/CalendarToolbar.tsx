import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import type { CalendarMonth } from '../../api/marketCalendar';
import { formatTradeDate } from '../market/format';

interface CalendarToolbarProps {
  month: CalendarMonth;
  loading: boolean;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
}

const navButton =
  'flex h-8 items-center justify-center rounded-md border border-bg-border text-text-secondary transition ' +
  'hover:border-accent-light hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40 ' +
  'disabled:hover:border-bg-border disabled:hover:text-text-secondary';

export default function CalendarToolbar({ month, loading, onPrev, onNext, onToday }: CalendarToolbarProps) {
  const showingToday = month.today >= month.ad_start && month.today <= month.ad_end;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0">
        <h2 className="flex flex-wrap items-baseline gap-x-2 text-text-primary">
          <span className="font-devanagari text-2xl font-semibold leading-tight">
            {month.month_name_np} {month.bs_year_np}
          </span>
          <span className="text-sm text-text-muted">{month.month_name} {month.bs_year}</span>
          {loading && <Loader2 size={14} className="animate-spin self-center text-text-muted" aria-label="Loading" />}
        </h2>
        <p className="text-xs text-text-muted">
          {formatTradeDate(month.ad_start)} – {formatTradeDate(month.ad_end)}
        </p>
      </div>
      <div className="flex items-center gap-1.5">
        <button type="button" className={`${navButton} w-8`} onClick={onPrev} disabled={!month.prev} aria-label="Previous month">
          <ChevronLeft size={16} />
        </button>
        <button
          type="button"
          className={`${navButton} px-3 text-sm font-medium`}
          onClick={onToday}
          disabled={showingToday}
          title={showingToday ? 'Showing the current month' : 'Back to the current month'}
        >
          Today
        </button>
        <button type="button" className={`${navButton} w-8`} onClick={onNext} disabled={!month.next} aria-label="Next month">
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
