// Shared by the Weekday Summary page and the dashboard's week-to-date card.
import type { WeekdayDay } from '../../api/marketCalendar';

export const WEEKDAY_NAMES: Record<string, string> = {
  Sun: 'Sunday', Mon: 'Monday', Tue: 'Tuesday', Wed: 'Wednesday', Thu: 'Thursday', Fri: 'Friday', Sat: 'Saturday',
};

export const toneText = (pct: number | null | undefined) =>
  pct == null || pct === 0 ? 'text-text-secondary' : pct > 0 ? 'text-up' : 'text-down';

/**
 * Cell fill for a daily move on the legend's ±1.5% scale (literal classes so Tailwind keeps
 * them).  The strongest step gets dark text for contrast.
 */
export function heatClass(pct: number | null) {
  if (pct == null) return 'border border-dashed border-bg-border text-text-muted';
  if (pct === 0) return 'bg-bg-elevated text-text-secondary';
  const size = Math.abs(pct);
  const step = size < 0.25 ? 0 : size < 0.5 ? 1 : size < 1 ? 2 : 3;
  if (pct > 0) return ['bg-up/15 text-up', 'bg-up/30 text-up', 'bg-up/50 text-up', 'bg-up/80 text-bg-primary'][step];
  return ['bg-down/15 text-down', 'bg-down/30 text-down', 'bg-down/50 text-down', 'bg-down/80 text-bg-primary'][step];
}

/** Text for a day without a session. */
export function gapLabel(day: WeekdayDay, today: string) {
  if (day.status === 'holiday') return 'Holiday';
  if (day.status === 'pending') return day.date === today ? 'Awaiting close' : 'Upcoming';
  return 'No session';
}
