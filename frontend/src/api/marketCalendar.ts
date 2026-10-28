import { apiClient } from './client';

// /api/market-calendar/ (Backend market_calendar/services/calendar.py).  All Bikram Sambat
// conversion happens on the backend; the page only renders what it gets, including prev / next.

export type CalendarDayStatus =
  | 'traded' | 'holiday' | 'weekend' | 'pending' | 'no_data' | 'no_session' | 'future';

export type CalendarEventType =
  | 'book_closure' | 'bonus_listed' | 'cash_distributed' | 'dividend_announced' | 'ipo_open' | 'ipo_close';

/** Decimals arrive as strings; change = close minus the previous stored close, change_pct is NEPSE's own. */
export interface CalendarIndexSummary {
  close: string;
  change: string | null;
  change_pct: string | null;
  previous_date: string | null;
  /** "crawled" = NEPSE's feed; "sharesansar" = the fallback feed. */
  source: string;
}

export interface CalendarIndexRow extends CalendarIndexSummary {
  open: string | null; high: string | null; low: string | null;
  turnover: string | null; volume: number | null; transactions: number | null;
}

export interface CalendarEventSummary {
  type: CalendarEventType;
  symbol: string;
  /** Short cell label, e.g. "BC NABIL". */
  label: string;
}

/** Tracked companies only, narrowed by company access. */
export interface DividendCalendarEvent extends CalendarEventSummary {
  category: 'dividend';
  company_name: string;
  logo_url: string | null;
  fiscal_year: string;
  bonus_pct: string;
  cash_pct: string;
  status: string;
}

/** IPO / FPO / right share ... of any company (whole market). */
export interface IssueCalendarEvent extends CalendarEventSummary {
  category: 'issue';
  company_name: string;
  logo_url: string | null;
  issue_type: string;
  issue_type_label: string;
  units: number | null;
  price: string | null;
  /** Right shares, e.g. "1:1". */
  ratio: string;
  issue_manager: string;
  open_date: string | null;
  /** Earliest closing date; the issue can stay open until final_date. */
  close_date: string | null;
  final_date: string | null;
}

export type CalendarEvent = DividendCalendarEvent | IssueCalendarEvent;

interface CalendarDayBase {
  /** AD date, YYYY-MM-DD. */
  date: string;
  bs_day: number;
  bs_day_np: string;
  /** 0 = Sunday. */
  weekday: number;
  status: CalendarDayStatus;
  is_today: boolean;
  holiday: string | null;
}

export interface CalendarMonthDay extends CalendarDayBase {
  index: CalendarIndexSummary | null;
  events: CalendarEventSummary[];
}

export interface BsMonthRef { bs_year: number; bs_month: number }

export interface CalendarMonth {
  scope: 'tracked_companies';
  index_code: string;
  today: string;
  bs_year: number;
  bs_month: number;
  month_name: string;
  month_name_np: string;
  bs_year_np: string;
  ad_start: string;
  ad_end: string;
  prev: BsMonthRef | null;
  next: BsMonthRef | null;
  /** Empty cells before day 1 in a Sunday-first grid. */
  leading_blanks: number;
  index_history_from: string | null;
  days: CalendarMonthDay[];
  data_notes: string[];
}

export interface CalendarDay extends CalendarDayBase {
  scope: 'tracked_companies';
  index_code: string;
  today: string;
  bs: { year: number; month: number; day: number; month_name: string; label_np: string; weekday_np: string };
  index: CalendarIndexRow | null;
  events: CalendarEvent[];
}

export const marketCalendarApi = {
  /** No argument: today's BS month. */
  month: (ref?: BsMonthRef | null) =>
    apiClient.get<CalendarMonth>('/market-calendar/month/', { params: ref ?? {} }).then((r) => r.data),
  day: (date: string) =>
    apiClient.get<CalendarDay>('/market-calendar/day/', { params: { date } }).then((r) => r.data),
};
