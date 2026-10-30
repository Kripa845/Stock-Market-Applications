import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  DEFAULT_WEEKDAY_SCOPE, marketCalendarApi, type BsMonthRef, type DayByDayCalendar, type DayByDayMonths, type WeekdayWeeks,
} from '../api/marketCalendar';

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

export function useWeekdaySummary(weeks: WeekdayWeeks, scope: string = DEFAULT_WEEKDAY_SCOPE) {
  return useQuery({
    queryKey: ['market-calendar', 'weekdays', weeks, scope],
    queryFn: () => marketCalendarApi.weekdays(weeks, scope),
    placeholderData: keepPreviousData,
  });
}

/** Switching index or calendar keeps the old grid on screen until the new one arrives. */
export function useDayByDay(index: string, calendar: DayByDayCalendar, months: DayByDayMonths) {
  return useQuery({
    queryKey: ['market-calendar', 'months', index, calendar, months],
    queryFn: () => marketCalendarApi.months(index, calendar, months),
    placeholderData: keepPreviousData,
  });
}

export function useMonthlyReturns(index: string) {
  return useQuery({
    queryKey: ['market-calendar', 'monthly', index],
    queryFn: () => marketCalendarApi.monthly(index),
    placeholderData: keepPreviousData,
  });
}
