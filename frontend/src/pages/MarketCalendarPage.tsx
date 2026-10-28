import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CalendarX, Info } from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import EmptyState from '../components/common/EmptyState';
import { Skeleton } from '../components/common/LoadingSkeleton';
import CalendarToolbar from '../components/calendar/CalendarToolbar';
import CalendarGrid from '../components/calendar/CalendarGrid';
import DayDetailPanel from '../components/calendar/DayDetailPanel';
import CalendarLegend from '../components/calendar/CalendarLegend';
import { useCalendarMonth } from '../hooks/useMarketCalendar';
import type { BsMonthRef } from '../api/marketCalendar';

// Market -> Calendar (/market/calendar): a Bikram Sambat month of NEPSE sessions and the
// tracked companies' corporate actions.  ?y=&m= pick the BS month (default: today's),
// ?d=YYYY-MM-DD opens a day in the side panel.

export default function MarketCalendarPage() {
  const [params, setParams] = useSearchParams();
  const y = Number(params.get('y'));
  const m = Number(params.get('m'));
  const ref: BsMonthRef | null = y && m ? { bs_year: y, bs_month: m } : null;
  const selectedDate = params.get('d');

  const { data: month, isLoading, isFetching, isError } = useCalendarMonth(ref);

  const update = useCallback((changes: Record<string, string | null>) => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      Object.entries(changes).forEach(([key, value]) => (value === null ? next.delete(key) : next.set(key, value)));
      return next;
    });
  }, [setParams]);

  const goTo = (target: BsMonthRef | null) =>
    update(target ? { y: String(target.bs_year), m: String(target.bs_month) } : { y: null, m: null });
  const closePanel = useCallback(() => update({ d: null }), [update]);

  const noHistory = month && (!month.index_history_from || month.index_history_from > month.ad_end) && month.ad_start <= month.today;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Market Calendar"
        subtitle="NEPSE close per session, holidays, dividends and public issues, by Bikram Sambat month"
      />

      <div className="card space-y-4 p-2 sm:p-4">
        {isLoading && <Skeleton className="h-[520px] w-full" />}
        {isError && !month && (
          <EmptyState icon={<CalendarX size={36} />} title="Calendar unavailable" description="The calendar could not be loaded. Try again shortly." />
        )}
        {month && (
          <>
            <CalendarToolbar
              month={month}
              loading={isFetching}
              onPrev={() => goTo(month.prev)}
              onNext={() => goTo(month.next)}
              onToday={() => goTo(null)}
            />
            <CalendarGrid month={month} selectedDate={selectedDate} onSelect={(date) => update({ d: date })} />
            <CalendarLegend />
          </>
        )}
      </div>

      {month && (
        <div className="space-y-1 text-xs text-text-muted">
          {noHistory && (
            <p className="flex items-center gap-1.5"><Info size={13} /> No NEPSE index history is stored for this month.</p>
          )}
          {month.data_notes.includes('ipo_not_crawled') && (
            <p className="flex items-center gap-1.5"><Info size={13} /> IPO open / close dates are not crawled yet.</p>
          )}
          <p>
            “No session” means a trading weekday with no stored index and no holiday entered. Book closure (BC), bonus listing,
            cash distribution and dividend announcements cover tracked companies you can access; IPO, FPO, right share,
            mutual fund and debenture open / close dates cover the whole market.
          </p>
        </div>
      )}

      {selectedDate && <DayDetailPanel date={selectedDate} onClose={closePanel} />}
    </div>
  );
}
