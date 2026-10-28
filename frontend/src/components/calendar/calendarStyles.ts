import type { CalendarDayStatus, CalendarEventType } from '../../api/marketCalendar';

// Shared labels and colours for the calendar grid and the day panel.

export const EVENT_LABEL: Record<CalendarEventType, string> = {
  book_closure: 'Book closure',
  bonus_listed: 'Bonus listed',
  cash_distributed: 'Cash dividend distributed',
  dividend_announced: 'Dividend announced',
  ipo_open: 'Issue opens',
  ipo_close: 'Issue closes',
};

export const EVENT_CHIP: Record<CalendarEventType, string> = {
  book_closure: 'bg-yellow-400/15 text-yellow-400',
  ipo_open: 'bg-cyan/15 text-cyan',
  ipo_close: 'bg-orange-500/15 text-orange-400',
  bonus_listed: 'bg-violet-500/15 text-violet-400',
  cash_distributed: 'bg-up/15 text-up',
  dividend_announced: 'bg-blue-500/15 text-blue-400',
};

/** Solid swatches for the phone dots and the legend. */
export const EVENT_DOT: Record<CalendarEventType, string> = {
  book_closure: 'bg-yellow-400',
  ipo_open: 'bg-cyan',
  ipo_close: 'bg-orange-400',
  bonus_listed: 'bg-violet-400',
  cash_distributed: 'bg-up',
  dividend_announced: 'bg-blue-400',
};

/** Shown in a cell without index figures (holidays show their name instead). */
export const STATUS_NOTE: Partial<Record<CalendarDayStatus, string>> = {
  pending: 'Awaiting close',
  no_session: 'No session',
  no_data: '—',
};

export const STATUS_BADGE: Record<CalendarDayStatus, string> = {
  traded: 'bg-accent/15 text-accent-light',
  holiday: 'bg-down/15 text-down',
  weekend: 'bg-bg-elevated text-text-secondary',
  pending: 'bg-yellow-400/15 text-yellow-400',
  no_data: 'bg-bg-elevated text-text-muted',
  no_session: 'bg-bg-elevated text-text-secondary',
  future: 'bg-cyan/15 text-cyan',
};

export const STATUS_LABEL: Record<CalendarDayStatus, string> = {
  traded: 'Traded',
  holiday: 'Holiday',
  weekend: 'Weekend',
  pending: 'Session not closed yet',
  no_data: 'No index history stored',
  no_session: 'No session (no holiday recorded)',
  future: 'Upcoming',
};
