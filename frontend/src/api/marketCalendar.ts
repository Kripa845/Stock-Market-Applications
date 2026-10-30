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

type Num = number | string | null;

/** One tracked company's session row (Backend market_data/services/movers.py). */
export interface MarketDayRow {
  symbol: string; name: string; logo_url: string | null;
  close: Num; change: Num; change_pct: Num;
  volume: number | null; turnover: Num;
  /** NULL until the day's trade count is derived; never 0 for "unknown". */
  transactions: number | null;
}

export interface MarketDayBroker {
  broker: string; name: string;
  buy_value: Num; sell_value: Num; net_value: Num; total_value: Num; trades: number;
}

/** ?include=market: the session for the tracked companies the user may access. */
export type MarketDay =
  | { scope: 'tracked_companies'; date: string; available: false; reason: string }
  | {
      scope: 'tracked_companies'; date: string; available: true;
      summary: {
        previous_trade_date: string | null; tracked_count: number;
        advanced: number; declined: number; unchanged: number;
        positive_circuit: number; negative_circuit: number;
        total_turnover: Num; total_traded_shares: Num; total_transactions: Num;
        transactions_reported: number; warning?: string | null;
      };
      gainers: MarketDayRow[]; losers: MarketDayRow[];
      top_volume: MarketDayRow[]; top_transactions: MarketDayRow[];
      /** Absent without view_analysis; null when no floorsheet is stored for the day. */
      brokers?: { transaction_count: number; broker_count: number; rows: MarketDayBroker[] } | null;
      floorsheet_from?: string | null;
    };

export interface CalendarDay extends CalendarDayBase {
  scope: 'tracked_companies';
  index_code: string;
  today: string;
  bs: { year: number; month: number; day: number; month_name: string; label_np: string; weekday_np: string };
  index: CalendarIndexRow | null;
  events: CalendarEvent[];
  market?: MarketDay;
}

export const WEEKDAY_WEEK_CHOICES = [4, 6, 13, 26] as const;
export type WeekdayWeeks = (typeof WEEKDAY_WEEK_CHOICES)[number];
export const WEEKDAY_WEEK_LABELS: Record<WeekdayWeeks, string> = { 4: '4W', 6: '6W', 13: '3M', 26: '6M' };

/** up / down / flat = a stored session; the rest have no session (pending = today or later). */
export type WeekdayDayStatus = 'up' | 'down' | 'flat' | 'holiday' | 'no_session' | 'pending';

export interface WeekdayDay {
  date: string;
  weekday: string;
  status: WeekdayDayStatus;
  /** Average of the companies' daily % changes, each counted equally; null without a session. */
  change_pct: number | null;
  holiday?: string;
  /** With a session: companies in the day's average, how many rose, and how many were left out. */
  companies?: number;
  companies_up?: number;
  excluded?: number;
  best?: { symbol: string; change_pct: number };
  worst?: { symbol: string; change_pct: number };
}

export interface WeekdayScopeOption {
  /** tracked or tracked:<sector>. */
  scope: string;
  label: string;
  companies: number;
}

export interface WeekdayScopes {
  tracked: WeekdayScopeOption[];
  tracked_sectors: WeekdayScopeOption[];
}

export const DEFAULT_WEEKDAY_SCOPE = 'tracked';

export interface WeekdayWeek {
  week_start: string;
  /** BS date of the week's first trading weekday, e.g. "9 Kartik". */
  label: string;
  days: WeekdayDay[];
  /** The week's daily averages compounded. */
  change_pct: number | null;
  sessions: number;
  up_days: number;
  partial: boolean;
  best: boolean;
  worst: boolean;
}

export interface WeekdayColumn {
  weekday: string;
  average_pct: number | null;
  sessions: number;
  up: number;
  down: number;
  /** One per week, oldest first. */
  dots: WeekdayDayStatus[];
}

export type WeekdayInsight =
  | { kind: 'best'; weekdays: string[]; average_pct: number; up: number; sessions: number }
  | { kind: 'always_up'; weekdays: string[]; sessions: number }
  | { kind: 'most_up'; weekdays: string[]; up: number; sessions: number }
  | { kind: 'negative'; weekdays: string[]; averages: number[] }
  /** Consecutive up closes back from the newest week. */
  | { kind: 'streak'; weekdays: string[]; sessions: number };

export interface WeekdaySummary {
  scope: string;
  /** "Tracked companies" or "Tracked <sector>". */
  scope_label: string;
  companies: number;
  symbols: string[];
  scopes: WeekdayScopes;
  weeks: number;
  /** Server's today (Asia/Kathmandu), for the TODAY column. */
  today: string;
  sessions_total: number;
  sessions_up: number;
  requested_weeks: number;
  from: string;
  to: string;
  trading_week: string[];
  columns: WeekdayColumn[];
  /** Newest week first. */
  week_rows: WeekdayWeek[];
  closed_weeks: { week_start: string; label: string }[];
  insights: WeekdayInsight[];
  notes: string[];
}

export const DAY_BY_DAY_MONTH_CHOICES = [6, 12, 24] as const;
export type DayByDayMonths = (typeof DAY_BY_DAY_MONTH_CHOICES)[number];
/** bs = Bikram Sambat months (नेपाली महिना), ad = English months. */
export type DayByDayCalendar = 'bs' | 'ad';

export interface DayByDayDay {
  /** Day of the month, 1-based, in the chosen calendar. */
  day: number;
  date: string;
  bs_label_np: string;
  bs_label: string;
  weekday: string;
  status: CalendarDayStatus;
  holiday: string | null;
  close: number | null;
  previous_close: number | null;
  previous_date: string | null;
  /** NEPSE's own change against the previous trading day's close. */
  change_pct: number | null;
}

export interface DayByDayMonth {
  year: number;
  month: number;
  label: string;
  /** Empty for English months. */
  label_np: string;
  ad_start: string;
  ad_end: string;
  is_current: boolean;
  /** Still running, or the index history starts inside it. */
  partial: boolean;
  /** Last close against the last close before the month began. */
  change_pct: number | null;
  sessions: number;
  up_days: number;
  days: DayByDayDay[];
}

export interface DayByDayMonthRef {
  label: string; label_np: string; change_pct: number; partial: boolean; sessions: number; up_days: number;
}

export interface DayByDaySummary {
  scope: 'whole_market';
  index: { code: string; name: string };
  calendar: DayByDayCalendar;
  today: string;
  /** Today's day of the month, for the TODAY column. */
  today_day: number;
  max_days: number;
  history_from: string;
  requested_months: number;
  /** Newest month first. */
  months: DayByDayMonth[];
  stats: {
    year: number;
    best_month: DayByDayMonthRef | null;
    worst_month: DayByDayMonthRef | null;
    strongest_weekday: { weekday: string; average_pct: number; sessions: number } | null;
    sessions: number;
    up_days: number;
  };
  /** NEPSE, then the sub-indices. */
  indices: { code: string; label: string }[];
  notes: string[];
}

/** One BS month's tile on the month-by-month page; null = no data (future or pre-history). */
export interface MonthlyCell {
  month: number;
  /** Last close in the month (to today for the running month) and its date. */
  close: number | null;
  close_date: string | null;
  /** Last close before the month began. */
  previous_close: number | null;
  /** null when the month had no session or no earlier close (history starts inside it). */
  return_pct: number | null;
  is_current: boolean;
  partial: boolean;
}

export interface MonthlyYear {
  year: number;
  months: (MonthlyCell | null)[];
  close: number | null;
  /** Last close of the year against the last close before it; compounded, never summed. */
  year_return: number | null;
  partial: boolean;
}

export interface MonthlyMonthRef { month: number; label: string; label_np: string }

export interface MonthlyReturns {
  scope: 'whole_market';
  index: { code: string; name: string };
  today: string;
  history_from: string;
  current: { year: number; month: number };
  months: MonthlyMonthRef[];
  /** Newest BS year first. */
  years: MonthlyYear[];
  /** Mean of each month's closed returns across years; blanks and the running month skipped. */
  avg_row: ({ average_pct: number; years: number } | null)[];
  stats: {
    best_year: { year: number; year_return: number; partial: boolean } | null;
    worst_year: { year: number; year_return: number; partial: boolean } | null;
    strongest_month: (MonthlyMonthRef & { average_pct: number; years: number }) | null;
    months_up: number;
    months_counted: number;
  };
  indices: { code: string; label: string }[];
  notes: string[];
}

export const marketCalendarApi = {
  /** One row per BS year, one tile per BS month (services/monthly_returns.py).  Whole market. */
  monthly: (index: string) =>
    apiClient.get<MonthlyReturns>('/market-calendar/monthly/', { params: { index } }).then((r) => r.data),
  /** One row per month, one tile per day (services/month_summary.py).  Whole market. */
  months: (index: string, calendar: DayByDayCalendar, months: DayByDayMonths) =>
    apiClient.get<DayByDaySummary>('/market-calendar/months/', { params: { index, calendar, months } }).then((r) => r.data),
  /** Tracked companies' move by weekday over the last `weeks` trading weeks (services/weekday_summary.py). */
  weekdays: (weeks: WeekdayWeeks, scope: string = DEFAULT_WEEKDAY_SCOPE) =>
    apiClient.get<WeekdaySummary>('/market-calendar/weekdays/', { params: { weeks, scope } }).then((r) => r.data),
  /** No argument: today's BS month. */
  month: (ref?: BsMonthRef | null) =>
    apiClient.get<CalendarMonth>('/market-calendar/month/', { params: ref ?? {} }).then((r) => r.data),
  /** Always with the session's market sections (include=market). */
  day: (date: string) =>
    apiClient.get<CalendarDay>('/market-calendar/day/', { params: { date, include: 'market' } }).then((r) => r.data),
};
