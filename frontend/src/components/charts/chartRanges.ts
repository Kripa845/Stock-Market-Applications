// Date ranges measured against the data itself, never against "today".
//
// 1D / 5D count real trading sessions (the dates that have a price), so 5D is always the last five
// sessions however many holidays or weekends fall in between. 1M / 3M / 6M / 1Y go back that many
// calendar months from the latest session; YTD starts on 1 January of the latest session's year.
// A range is only offered when the data actually reaches back that far.

export type RangeId = '1D' | '5D' | '1M' | '3M' | '6M' | 'YTD' | '1Y' | 'All';

export const RANGE_IDS: RangeId[] = ['1D', '5D', '1M', '3M', '6M', 'YTD', '1Y', 'All'];

const SESSIONS: Partial<Record<RangeId, number>> = { '1D': 1, '5D': 5 };
const MONTHS: Partial<Record<RangeId, number>> = { '1M': 1, '3M': 3, '6M': 6, '1Y': 12 };

export const RANGE_TITLES: Record<RangeId, string> = {
  '1D': 'Latest trading session',
  '5D': 'Last 5 trading sessions',
  '1M': '1 month back from the latest session',
  '3M': '3 months back from the latest session',
  '6M': '6 months back from the latest session',
  'YTD': 'From 1 January of the latest session’s year',
  '1Y': '1 year back from the latest session',
  'All': 'All available data',
};

const DAY_MS = 864e5;
const toMs = (iso: string) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
const toIso = (ms: number) => new Date(ms).toISOString().slice(0, 10);

/** The same day `months` months earlier, clamped to the end of a shorter month (31 Mar -> 28/29 Feb). */
function monthsBefore(iso: string, months: number) {
  const y = +iso.slice(0, 4), m = +iso.slice(5, 7) - 1, d = +iso.slice(8, 10);
  const target = new Date(Date.UTC(y, m - months, 1));
  const lastDay = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  return toIso(Date.UTC(target.getUTCFullYear(), target.getUTCMonth(), Math.min(d, lastDay)));
}

/** First date (inclusive, YYYY-MM-DD) of the range, given trading dates sorted oldest first. */
export function rangeStart(dates: string[], id: RangeId): string | null {
  if (!dates.length) return null;
  const last = dates[dates.length - 1];
  const sessions = SESSIONS[id];
  if (sessions) return dates[Math.max(0, dates.length - sessions)];
  if (id === 'All') return dates[0];
  if (id === 'YTD') return `${last.slice(0, 4)}-01-01`;
  // Exactly n months: 1 Oct -> 2 Sep .. 1 Oct, so the window never holds the same date twice.
  return toIso(toMs(monthsBefore(last, MONTHS[id]!)) + DAY_MS);
}

/** Whether the data reaches back far enough for the range to mean what its label says. */
export function rangeAvailable(dates: string[], id: RangeId): boolean {
  if (!dates.length) return false;
  const sessions = SESSIONS[id];
  if (sessions) return dates.length >= sessions;
  if (id === 'All') return true;
  const first = dates[0];
  const last = dates[dates.length - 1];
  if (id === 'YTD') return first < `${last.slice(0, 4)}-01-01` || first.slice(0, 7) === `${last.slice(0, 4)}-01`;
  return first <= monthsBefore(last, MONTHS[id]!);
}

/** Every date in the window, inclusive. */
export function filterRange<T extends { date: string }>(rows: T[], start: string | null) {
  return start ? rows.filter((r) => r.date >= start) : rows;
}

/** Calendar days from `start` to the latest date, inclusive (for APIs that take a day count). */
export function rangeCalendarDays(dates: string[], start: string | null) {
  if (!dates.length || !start) return 0;
  return Math.round((toMs(dates[dates.length - 1]) - toMs(start)) / DAY_MS) + 1;
}

const fmt = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
export const formatDay = (iso: string) => fmt.format(new Date(toMs(iso)));

/** Default view: 6 months when the data covers it, otherwise everything there is. */
export const defaultRange = (dates: string[]): RangeId => (rangeAvailable(dates, '6M') ? '6M' : 'All');

/** Tooltip for a range the data cannot fill. */
export function unavailableReason(dates: string[], id: RangeId) {
  if (!dates.length) return 'No price data yet';
  const span = `${formatDay(dates[0])} – ${formatDay(dates[dates.length - 1])}`;
  return `Not enough data: only ${dates.length} trading session${dates.length === 1 ? '' : 's'} (${span}) for ${RANGE_TITLES[id].toLowerCase()}`;
}
