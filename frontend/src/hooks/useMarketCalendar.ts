import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { marketCalendarApi, type BsMonthRef, type WeekdayWeeks } from '../api/marketCalendar';

// Market calendar month grid and the selected day's detail.  The previous month stays on
// screen while the next one loads.

export function useCalendarMonth(ref: BsMonthRef | null) {
  return useQuery({
    queryKey: ['market-calendar', 'month', ref?.bs_year ?? null, ref?.bs_month ?? null],
    queryFn: () => marketCalendarApi.month(ref),
    placeholderData: keepPreviousData,
  });
}

export function useCalendarDay(date: string | null) {
  return useQuery({
    queryKey: ['market-calendar', 'day', date],
    queryFn: () => marketCalendarApi.day(date as string),
    enabled: date !== null,
    // Stepping through days keeps the last one (and the open tab) on screen while the next loads.
    placeholderData: keepPreviousData,
  });
}

export function useWeekdaySummary(weeks: WeekdayWeeks) {
  return useQuery({
    queryKey: ['market-calendar', 'weekdays', weeks],
    queryFn: () => marketCalendarApi.weekdays(weeks),
    placeholderData: keepPreviousData,
  });
}
